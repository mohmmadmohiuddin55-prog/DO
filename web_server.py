"""Serve the Do desktop UI or its access-protected hosted web edition."""

import json
import hmac
import logging
import os
import sys
import threading
import urllib.parse
import uuid
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from language_filter import is_english_text


ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", ROOT))
FRONTEND = RESOURCE_ROOT / "frontend"
SYSTEM_PROMPT = (
    "You are Do, a capable, concise personal assistant. Be warm and direct. "
    "Understand and respond in English only. "
    "The user wants practical help. Do not claim to control the computer or perform "
    "an action unless an available tool confirms it. Explain briefly when a requested "
    "action is not available. Keep ordinary answers brief. When teaching a subject, "
    "teach one short lesson at a time, follow a clear sequence, and ask a single check-in. "
    "When the user says 'next', continue to the next lesson without asking them to choose again."
)

USER_CONFIG_ROOT = Path(os.getenv("APPDATA", str(Path.home() / ".config"))) / "Do"
load_dotenv(USER_CONFIG_ROOT / ".env")
load_dotenv(ROOT / ".env")
HOSTED_MODE = os.getenv("DO_HOSTED_MODE", "0").strip().lower() in {"1", "true", "yes"}
HOST = os.getenv("DO_HOST", "0.0.0.0" if HOSTED_MODE else "127.0.0.1")
PORT = int(os.getenv("PORT", os.getenv("DO_PORT", "8000")))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("do-web")
voice_stop_event = threading.Event()
voice_thread = None
voice_lock = threading.Lock()
voice_error = ""
voice_message = ""
voice_events = []
voice_events_lock = threading.Lock()
notes_lock = threading.Lock()
settings_lock = threading.Lock()
DEFAULT_PERMISSIONS = {
    "microphone": True,
    "desktopControl": True,
    "screenCapture": False,
    "fileActions": False,
    "powerActions": False,
    "emailAccess": False,
    "gemini": True,
}
access_attempts = {}
access_attempts_lock = threading.Lock()


def _notes_path():
    """Keep personal notes in the current Windows user's local app data."""
    local_data = os.getenv("LOCALAPPDATA")
    base = Path(local_data) if local_data else Path.home() / ".local" / "share"
    return base / "Do" / "notes.json"


def _settings_path():
    return USER_CONFIG_ROOT / "settings.json"


def _read_settings():
    settings = dict(DEFAULT_PERMISSIONS)
    try:
        stored = json.loads(_settings_path().read_text(encoding="utf-8"))
        if isinstance(stored, dict):
            for key in settings:
                if isinstance(stored.get(key), bool):
                    settings[key] = stored[key]
    except FileNotFoundError:
        pass
    except (OSError, json.JSONDecodeError):
        logger.exception("Could not read Do permissions")
    return settings


def _write_settings(settings):
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def _permission_for_command(text):
    clean = text.lower().strip()
    if any(term in clean for term in ("start voice", "turn on voice", "mic on", "start mic")):
        return "microphone"
    if any(term in clean for term in ("screenshot", "take a picture", "capture screen")):
        return "screenCapture"
    if any(term in clean for term in ("create a file", "make a file", "save to file", "write to file", "save internet data", "download data", "search internet for")):
        return "fileActions"
    if any(term in clean for term in ("sleep mode", "sleep pc", "system in sleep", "lock screen", "lock pc", "lock computer")):
        return "powerActions"
    if "email" in clean or "read mail" in clean:
        return "emailAccess"
    if any(term in clean for term in ("open ", "launch ", "close ", "play ", "volume ", "mute", "pause", "resume", "rewind", "fast forward", "fullscreen", "next video", "like video")):
        return "desktopControl"
    return None


def _voice_command_allowed(text):
    permission = _permission_for_command(text)
    return permission is None or bool(_read_settings().get(permission, False))


def _read_notes():
    try:
        path = _notes_path()
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except FileNotFoundError:
        return []
    except (OSError, json.JSONDecodeError):
        logger.exception("Could not read the local notes file")
        return []


def _write_notes(notes):
    path = _notes_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")


def _set_voice_message(message):
    global voice_message
    voice_message = message


def _record_voice_transcript(text):
    event = {
        "text": str(text)[:500],
        "createdAt": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    with voice_events_lock:
        voice_events.insert(0, event)
        del voice_events[10:]


def _run_voice_worker():
    global voice_error, voice_message
    try:
        # Import inside the listener thread so Windows speech/TTS initializes
        # on the same thread that owns the microphone loop.
        from do_assistant import run_voice_assistant

        run_voice_assistant(
            voice_stop_event,
            status_callback=_set_voice_message,
            transcript_callback=_record_voice_transcript,
            permission_callback=_voice_command_allowed,
        )
    except Exception as error:
        voice_error = str(error)
        voice_message = "Voice startup failed. Check microphone and audio device access."
        logger.exception("Native voice assistant failed")
    finally:
        if not voice_error:
            voice_message = "Voice listener stopped."


def start_voice_worker():
    global voice_thread, voice_error, voice_message
    if not _read_settings().get("microphone", False):
        voice_message = "Microphone use is turned off in Settings → Permissions."
        return False
    with voice_lock:
        if voice_thread is not None and voice_thread.is_alive():
            return False
        voice_error = ""
        voice_message = "Starting microphone and voice engine…"
        voice_stop_event.clear()
        voice_thread = threading.Thread(
            target=_run_voice_worker,
            name="do-microphone",
            daemon=True,
        )
        voice_thread.start()
        return True


def stop_voice_worker():
    global voice_message
    voice_stop_event.set()
    voice_message = "Stopping voice listener…"


def toggle_voice_worker():
    if voice_thread is not None and voice_thread.is_alive():
        stop_voice_worker()
        return False
    return start_voice_worker()


def handle_text_command(text: str):
    """Execute local system and media commands directly when typed in chat."""
    if not text:
        return None
    clean = text.lower().strip()
    permission = _permission_for_command(clean)
    if permission and not _read_settings().get(permission, False):
        label = {
            "desktopControl": "Desktop controls",
            "screenCapture": "Screen capture",
            "fileActions": "File actions",
            "powerActions": "Power controls",
            "emailAccess": "Email access",
            "microphone": "Microphone use",
        }.get(permission, "This action")
        return f"The {label} permission is turned off in Do Settings → Permissions. Enable it and try again."

    # Load the voice command normalizer only when the text resembles a command.
    command_terms = (
        "open", "launch", "start", "close", "play", "volume", "time", "youtube",
        "whatsapp", "github", "gmail", "chrome",
    )
    if any(term in clean for term in command_terms):
        try:
            from do_assistant import normalize_voice_command
            clean = normalize_voice_command(clean)
        except Exception:
            logger.exception("Could not normalize a natural-language command")

    if clean == "close youtube":
        try:
            from do_assistant import close_youtube_tab
            if close_youtube_tab():
                return "Closed the active YouTube tab."
            return "Bring the YouTube tab to the front first, then ask me to close it."
        except Exception:
            logger.exception("Could not close the active YouTube tab")
            return "I couldn't close the YouTube tab."

    # 1. Voice control
    if clean in ["start voice", "start voice assistant", "turn on voice", "mic on", "start mic"]:
        if not start_voice_worker() and not (voice_thread is not None and voice_thread.is_alive()):
            return "Microphone use is turned off in Do Settings → Permissions."
        return {"text": "Voice assistant started. Microphone is online.", "type": "voice_card", "state": "active"}
    if clean in ["stop voice", "stop voice assistant", "turn off voice", "mic off", "stop mic"]:
        stop_voice_worker()
        return {"text": "Voice assistant stopped.", "type": "voice_card", "state": "inactive"}

    # 2. YouTube & Music playback
    if clean == "open youtube and play":
        try:
            from do_assistant import open_system_app
            threading.Thread(target=open_system_app, args=("youtube",), daemon=True).start()
        except Exception:
            logger.exception("Could not open YouTube")
        return "What would you like me to play?"

    if clean.startswith("play ") or "play song" in clean or "play music" in clean:
        song = clean
        for prefix in ["play on youtube ", "play the song ", "play song ", "play music ", "play "]:
            if song.startswith(prefix):
                song = song.replace(prefix, "", 1).strip()
                break
        if song:
            def _play():
                try:
                    import pywhatkit
                    pywhatkit.playonyt(song)
                except Exception:
                    import urllib.parse
                    import webbrowser
                    webbrowser.open(f"https://www.youtube.com/results?search_query={urllib.parse.quote(song)}")
            threading.Thread(target=_play, daemon=True).start()
            import urllib.parse
            return {
                "text": f"Playing '{song.title()}' on YouTube.",
                "type": "media_card",
                "song": song.title(),
                "url": f"https://www.youtube.com/results?search_query={urllib.parse.quote(song)}",
            }
        else:
            return "What would you like me to play?"

    # 3. Application & Website Opener
    if clean.startswith("open ") or clean.startswith("launch ") or clean.startswith("start "):
        app = clean
        for prefix in ["open ", "launch ", "start "]:
            if app.startswith(prefix):
                app = app.replace(prefix, "", 1).strip()
                break
        if app:
            def _open():
                try:
                    from do_assistant import open_system_app
                    open_system_app(app)
                except Exception:
                    import webbrowser
                    if "." in app:
                        webbrowser.open(f"https://{app}")
                    else:
                        webbrowser.open(f"https://www.google.com/search?q={app}")
            threading.Thread(target=_open, daemon=True).start()
            return {
                "text": f"Opening {app.title()}...",
                "type": "app_card",
                "app": app.title(),
            }

    # 4. System status (Rich diagnostic gauges)
    if any(k in clean for k in ["system status", "gauges", "diagnostics", "hardware", "specs"]) or clean in ["cpu", "ram", "system info", "memory usage"]:
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            ram = psutil.virtual_memory()
            system_drive = (os.environ.get("SystemDrive", "C:") + "\\") if os.name == "nt" else "/"
            disk = psutil.disk_usage(system_drive)
            battery = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None

            ram_used = round(ram.used / (1024**3), 1)
            ram_total = round(ram.total / (1024**3), 1)
            disk_free = round(disk.free / (1024**3), 1)
            disk_total = round(disk.total / (1024**3), 1)

            return {
                "text": f"Diagnostic Report: CPU {cpu}%, RAM {ram.percent}% ({ram_used}/{ram_total} GB), Storage {disk.percent}% ({disk_free} GB Free).",
                "type": "system_card",
                "cpu": cpu,
                "ram_percent": ram.percent,
                "ram_used": ram_used,
                "ram_total": ram_total,
                "disk_percent": disk.percent,
                "disk_free": disk_free,
                "disk_total": disk_total,
                "battery_percent": round(battery.percent) if battery else None,
                "battery_plugged": battery.power_plugged if battery else None,
            }
        except Exception:
            logger.exception("System status check failed")

    # 5. Screenshot
    if "screenshot" in clean or "take a picture" in clean or "capture screen" in clean:
        try:
            import pyautogui
            import datetime
            filename = f"do_screenshot_{datetime.datetime.now():%Y%m%d_%H%M%S_%f}.png"
            filepath = Path(ROOT) / filename
            pyautogui.screenshot(str(filepath))
            return {
                "text": f"Screenshot captured successfully. Saved as {filename}.",
                "type": "screenshot_card",
                "filename": filename,
            }
        except Exception as e:
            return f"Failed to take screenshot: {e}"

    # 6. Volume controls
    if "volume up" in clean or "increase volume" in clean:
        try:
            import pyautogui
            pyautogui.press("volumeup", presses=5)
            return {"text": "Master volume increased by 10%.", "type": "volume_card", "action": "up"}
        except Exception:
            pass
    if "volume down" in clean or "decrease volume" in clean:
        try:
            import pyautogui
            pyautogui.press("volumedown", presses=5)
            return {"text": "Master volume decreased by 10%.", "type": "volume_card", "action": "down"}
        except Exception:
            pass
    if clean in ["mute", "unmute"]:
        try:
            import pyautogui
            pyautogui.press("volumemute")
            return {"text": "Master volume mute toggled.", "type": "volume_card", "action": "mute"}
        except Exception:
            pass

    # 7. Time
    if clean in ["what time is it", "time", "current time", "what is the time", "clock"]:
        import datetime
        now = datetime.datetime.now()
        return {
            "text": f"The local time is {now.strftime('%I:%M:%S %p')} on {now.strftime('%A, %B %d, %Y')}.",
            "type": "time_card",
            "time": now.strftime('%I:%M %p'),
            "date": now.strftime('%a, %d %b %Y'),
        }

    return None


class DoRequestHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND), **kwargs)

    def log_message(self, format, *args):
        # Windowed desktop builds have no console stream to write access logs to.
        return

    def _send_json(self, status, payload):
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def _begin_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-transform")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        self._stream_active = True

    def _write_stream_event(self, payload):
        encoded = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        self.wfile.write(f"{len(encoded):X}\r\n".encode("ascii") + encoded + b"\r\n")
        self.wfile.flush()

    def _end_stream(self):
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()
        self._stream_active = False

    def _same_origin_request(self):
        """Reject cross-origin writes; hosted instances must be served over HTTPS."""
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        if not origin or not host:
            return False
        parsed = urllib.parse.urlsplit(origin)
        expected_scheme = "https" if HOSTED_MODE else "http"
        return parsed.scheme == expected_scheme and parsed.netloc.lower() == host.lower()

    def _authorized_hosted_request(self):
        if not HOSTED_MODE:
            return True
        expected = os.getenv("DO_ACCESS_CODE", "")
        supplied = self.headers.get("X-Do-Access-Code", "")
        if not expected:
            self._send_json(503, {"error": "The site owner has not configured Do access."})
            return False
        if not supplied or not hmac.compare_digest(supplied, expected):
            self._send_json(401, {"error": "Enter the site access code to continue."})
            return False
        return True

    def do_GET(self):
        if self.path == "/api/settings":
            self._send_json(200, {"hostedMode": HOSTED_MODE, "settings": {} if HOSTED_MODE else _read_settings()})
            return
        if HOSTED_MODE and self.path == "/api/status":
            self._send_json(200, {"hostedMode": True, "aiConfigured": bool(os.getenv("GEMINI_API_KEY")),
                                  "voiceActive": False, "voiceAvailable": False, "voiceCommands": []})
            return
        if self.path == "/api/notes":
            if HOSTED_MODE:
                self._send_json(404, {"error": "Hosted notes are saved privately in your browser."})
                return
            with notes_lock:
                notes = _read_notes()
            self._send_json(200, {"notes": notes})
            return
        if self.path == "/api/status":
            voice_active = voice_thread is not None and voice_thread.is_alive() and not voice_stop_event.is_set()
            with voice_events_lock:
                recent_voice_commands = list(voice_events)
            self._send_json(200, {
                "aiConfigured": bool(os.getenv("GEMINI_API_KEY")),
                "voiceActive": voice_active,
                "voiceError": voice_error,
                "voiceMessage": voice_message,
                "voiceCommands": recent_voice_commands,
            })
            return
        super().do_GET()

    def do_POST(self):
        if not self._same_origin_request():
            self._send_json(403, {"error": "Request origin is not allowed."})
            return
        if self.path == "/api/access":
            expected = os.getenv("DO_ACCESS_CODE", "")
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length)) if 0 < length <= 2000 else {}
                supplied = str(payload.get("code", "")) if isinstance(payload, dict) else ""
            except (ValueError, json.JSONDecodeError):
                supplied = ""
            valid = bool(expected) and hmac.compare_digest(supplied, expected)
            if not valid:
                client_ip = self.client_address[0]
                now = datetime.now().timestamp()
                with access_attempts_lock:
                    attempts = [stamp for stamp in access_attempts.get(client_ip, []) if now - stamp < 300]
                    if len(attempts) >= 10:
                        self._send_json(429, {"error": "Too many attempts. Wait five minutes, then try again."})
                        return
                    attempts.append(now)
                    access_attempts[client_ip] = attempts
            else:
                with access_attempts_lock:
                    access_attempts.pop(self.client_address[0], None)
            self._send_json(200 if valid else 401, {"authorized": valid, **({} if valid else {"error": "That access code is not correct."})})
            return
        if not self._authorized_hosted_request():
            return
        if self.path == "/api/settings":
            if HOSTED_MODE:
                self._send_json(403, {"error": "Desktop permissions can only be changed in the local Do app."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 4_000:
                    self._send_json(413, {"error": "Settings request is empty or too large."})
                    return
                payload = json.loads(self.rfile.read(length))
                requested = payload.get("settings") if isinstance(payload, dict) else None
                if not isinstance(requested, dict):
                    self._send_json(400, {"error": "Settings could not be read."})
                    return
                settings = _read_settings()
                for key in DEFAULT_PERMISSIONS:
                    value = requested.get(key)
                    if isinstance(value, bool):
                        settings[key] = value
                with settings_lock:
                    _write_settings(settings)
                if not settings["microphone"]:
                    stop_voice_worker()
                self._send_json(200, {"settings": settings})
            except (json.JSONDecodeError, ValueError, AttributeError):
                self._send_json(400, {"error": "Settings could not be read."})
            except OSError:
                logger.exception("Could not save Do settings")
                self._send_json(500, {"error": "Could not save Do settings."})
            return
        if self.path == "/api/voice/start":
            if HOSTED_MODE:
                self._send_json(403, {"error": "Microphone control is only available in the desktop app."})
                return
            if not _read_settings().get("microphone", False):
                self._send_json(403, {"error": "Microphone use is turned off in Do Settings → Permissions."})
                return
            started = start_voice_worker()
            self._send_json(200, {"voiceActive": True, "started": started})
            return
        if self.path == "/api/voice/stop":
            if HOSTED_MODE:
                self._send_json(403, {"error": "Microphone control is only available in the desktop app."})
                return
            stop_voice_worker()
            self._send_json(200, {"voiceActive": False})
            return
        if self.path == "/api/notes":
            if HOSTED_MODE:
                self._send_json(404, {"error": "Hosted notes are saved privately in your browser."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 8_000:
                    self._send_json(413, {"error": "Note is empty or too large."})
                    return
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    self._send_json(400, {"error": "That note could not be read."})
                    return
                content = str(payload.get("content") or "").strip()
                if not content:
                    self._send_json(400, {"error": "Write a note before saving."})
                    return
                if len(content) > 4_000:
                    self._send_json(400, {"error": "Notes must be 4,000 characters or less."})
                    return
                note = {
                    "id": uuid.uuid4().hex,
                    "content": content,
                    "createdAt": datetime.now().astimezone().isoformat(timespec="minutes"),
                }
                with notes_lock:
                    notes = _read_notes()
                    notes.insert(0, note)
                    _write_notes(notes[:200])
                self._send_json(201, {"note": note})
            except (json.JSONDecodeError, ValueError, AttributeError):
                self._send_json(400, {"error": "That note could not be read."})
            except OSError:
                logger.exception("Could not save a local note")
                self._send_json(500, {"error": "Could not save the note on this computer."})
            return
        if self.path != "/api/chat":
            self._send_json(404, {"error": "Endpoint not found."})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 24_000:
                self._send_json(413, {"error": "Message is empty or too large."})
                return
            payload = json.loads(self.rfile.read(length))
            messages = payload.get("messages", [])
            if not isinstance(messages, list):
                raise ValueError("messages must be a list")
            messages = messages[-12:]
            contents = []
            for message in messages:
                if not isinstance(message, dict):
                    continue
                role = "model" if message.get("role") == "assistant" else "user"
                text = str(message.get("content", "")).strip()[:4000]
                if text:
                    contents.append(types.Content(role=role, parts=[types.Part(text=text)]))
            if not contents or contents[-1].role != "user":
                self._send_json(400, {"error": "Send a message to Do first."})
                return

            # Check for direct desktop actions (e.g. play songs, open apps, volume, mic toggle)
            last_user_query = ""
            for msg in reversed(messages):
                if isinstance(msg, dict) and msg.get("role") == "user":
                    last_user_query = str(msg.get("content", "")).strip()
                    break

            if not is_english_text(last_user_query):
                self._send_json(422, {"error": "Do only accepts English. Please rephrase in English."})
                return

            command_result = None if HOSTED_MODE else handle_text_command(last_user_query)
            if command_result:
                if isinstance(command_result, dict):
                    self._send_json(200, {
                        "reply": command_result.get("text", ""),
                        "card": command_result,
                    })
                else:
                    self._send_json(200, {"reply": str(command_result)})
                return

            if not HOSTED_MODE and not _read_settings().get("gemini", True):
                self._send_json(403, {"error": "Gemini access is turned off in Do Settings → Permissions."})
                return

            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                self._send_json(503, {"error": "Add GEMINI_API_KEY to the project .env file, then restart this server."})
                return

            client = genai.Client(api_key=api_key)
            last_err = None
            primary_model = os.getenv("DO_GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
            fallback_model = os.getenv("DO_GEMINI_FALLBACK_MODEL", "gemini-3.8-flash").strip()
            model_names = list(dict.fromkeys(name for name in (primary_model, fallback_model) if name))
            self._begin_stream()
            streamed_text = False
            stream_error = None
            for model_name in model_names:
                try:
                    thinking_level = "minimal" if "flash-lite" in model_name else "low"
                    for chunk in client.models.generate_content_stream(
                        model=model_name,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_PROMPT,
                            thinking_config=types.ThinkingConfig(thinking_level=thinking_level),
                            max_output_tokens=700,
                        ),
                    ):
                        text_chunk = getattr(chunk, "text", None)
                        if text_chunk:
                            self._write_stream_event({"type": "delta", "text": text_chunk})
                            streamed_text = True
                    if streamed_text:
                        break
                except Exception as err:
                    last_err = err
                    logger.warning("Gemini stream %s failed: %s", model_name, err)
                    if streamed_text:
                        stream_error = "The connection ended while Do was replying. Please try again."
                        break
            if stream_error:
                self._write_stream_event({"type": "error", "error": stream_error})
            elif not streamed_text:
                detail = str(last_err) if last_err else "The model returned an empty reply."
                logger.error("No Gemini text was streamed: %s", detail)
                self._write_stream_event({"type": "error", "error": "Gemini could not answer. Check the configured model and API key, then try again."})
            else:
                self._write_stream_event({"type": "done"})
            self._end_stream()
        except (json.JSONDecodeError, ValueError):
            self._send_json(400, {"error": "That message could not be read."})
        except Exception:
            logger.exception("Gemini chat request failed")
            if getattr(self, "_stream_active", False):
                try:
                    self._write_stream_event({"type": "error", "error": "I can't reach the AI service right now. Check the server and try again."})
                    self._end_stream()
                except OSError:
                    pass
            else:
                self._send_json(502, {"error": "I can't reach the AI service right now. Check the server window and try again."})

    def do_DELETE(self):
        if not self._same_origin_request():
            self._send_json(403, {"error": "Request origin is not allowed."})
            return
        if HOSTED_MODE:
            self._send_json(404, {"error": "Hosted notes are saved privately in your browser."})
            return
        prefix = "/api/notes/"
        if not self.path.startswith(prefix):
            self._send_json(404, {"error": "Endpoint not found."})
            return
        note_id = self.path[len(prefix):]
        with notes_lock:
            notes = _read_notes()
            remaining = [note for note in notes if note.get("id") != note_id]
            if len(remaining) == len(notes):
                self._send_json(404, {"error": "Note not found."})
                return
            try:
                _write_notes(remaining)
            except OSError:
                logger.exception("Could not update the local notes file")
                self._send_json(500, {"error": "Could not delete the note."})
                return
        self._send_json(200, {"deleted": True})


def create_server(port=PORT):
    """Create the local-only frontend and Gemini API server."""
    if HOSTED_MODE and not os.getenv("DO_ACCESS_CODE"):
        raise RuntimeError("DO_ACCESS_CODE is required when DO_HOSTED_MODE is enabled.")
    return ThreadingHTTPServer((HOST, port), DoRequestHandler)


if __name__ == "__main__":
    if not FRONTEND.is_dir():
        raise SystemExit(f"Frontend folder not found: {FRONTEND}")
    server = create_server()
    print(f"Do web interface: {'https' if HOSTED_MODE else 'http'}://{'0.0.0.0' if HOSTED_MODE else 'localhost'}:{PORT}")
    print("Local Gemini bridge ready. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDo web interface offline.")
    finally:
        server.server_close()
