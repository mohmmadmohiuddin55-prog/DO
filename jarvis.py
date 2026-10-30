import datetime
import email
from email.header import decode_header
import imaplib
import json
import logging
import os
from pathlib import Path
import re
import sys
import time
import urllib.parse
import urllib.request
import webbrowser
from dotenv import load_dotenv
from language_filter import is_english_text
from google import genai
from google.genai import types
import psutil
import pyautogui
import pyttsx3
import pywhatkit
import speech_recognition as sr

# 1. Load environment variables
load_dotenv()

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("do-assistant")
voice_status_callback = None


def set_voice_status(message):
    if voice_status_callback:
        voice_status_callback(message)


def console_print(text):
    """Print safely in both UTF-8 terminals and Windows GUI executables."""
    if sys.stdout is None:
        return
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        safe_text = str(text).encode(encoding, errors="replace").decode(
            encoding, errors="replace"
        )
        print(safe_text)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

# Initialize the AI session when credentials are available.
chat = None
MODELS = ["gemini-3.5-flash-lite", "gemini-flash-lite-latest", "gemini-3.7-flash", "gemini-3.5-flash", "gemini-3.8-flash"]
if client:
    for model_name in MODELS:
        try:
            chat = client.chats.create(
                model=model_name,
                config=types.GenerateContentConfig(
                    system_instruction=(
                        "You are Do, a capable personal desktop assistant. "
                        "Understand and respond in English only. "
                        "Keep responses concise and conversational. "
                        "Never claim to perform computer actions unless they happened."
                    )
                ),
            )
            if chat:
                break
        except Exception:
            continue
    if not chat:
        logger.warning("Could not start Gemini session with any fallback model")

# 2. Initialize Text-to-Speech Engine
engine = pyttsx3.init()
engine.setProperty("rate", 190)  # High-responsiveness speech speed

voices = engine.getProperty("voices")
if len(voices) > 0:
    engine.setProperty("voice", voices[0].id)


def speak(text):
    set_voice_status("Speaking response…")
    console_print(f"\n  DO  {text}")
    try:
        engine.say(text)
        engine.runAndWait()
    except Exception:
        logger.exception("Text-to-speech failed")
        set_voice_status("Speech output failed. Check Windows sound and speech settings.")


def show_status(state="STANDBY"):
    now = datetime.datetime.now().astimezone().strftime("%H:%M:%S")
    ai_state = "ONLINE" if chat else "OFFLINE"
    console_print(
        f"\n{'=' * 58}\n"
        f"  DO  /  {state:<12}  /  AI {ai_state}  /  {now}\n"
        f"{'=' * 58}"
    )


def safe_filename(name, fallback="workspace_file.txt"):
    """Keep voice-provided names inside the current working directory."""
    name = Path(name).name
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return name or fallback


# Single reusable recognizer instance configured for high speed
recognizer = sr.Recognizer()
recognizer.pause_threshold = 0.5
recognizer.non_speaking_duration = 0.3


# 3. Internet Data Search & File Saver
def fetch_internet_data_and_save(topic):
    """Searches the internet for a topic and saves structured content into a text file."""
    speak(f"Fetching internet data regarding {topic}...")
    clean_filename = (
        re.sub(r"[^\w\s-]", "", topic).strip().replace(" ", "_").lower()
    )
    if not clean_filename:
        clean_filename = "internet_data"
    filepath = safe_filename(f"{clean_filename}_data.txt", "internet_data.txt")

    data_content = f"=== INTERNET DATA REPORT: {topic.upper()} ===\n"
    data_content += (
        f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )

    # 1. Direct Web API Query (DuckDuckGo Instant Answer)
    try:
        url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(topic)}&format=json&no_html=1"
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = json.loads(response.read().decode())
            if res_data.get("AbstractText"):
                data_content += (
                    f"SUMMARY:\n{res_data['AbstractText']}\n\nSOURCE URL:\n{res_data.get('AbstractURL', 'N/A')}\n\n"
                )
            if res_data.get("RelatedTopics"):
                data_content += "KEY RELATED DETAILS:\n"
                for item in res_data["RelatedTopics"][:5]:
                    if isinstance(item, dict) and "Text" in item:
                        data_content += f"- {item['Text']}\n"
                data_content += "\n"
    except Exception as e:
        console_print(f"[Web Fetch Notice]: {e}")

    # 2. Gemini AI Deep Internet Intelligence Report
    if chat:
        try:
            ai_query = f"Provide a detailed, comprehensive factual summary with key points about: {topic}"
            response = chat.send_message(ai_query)
            data_content += f"DETAILED INTEL REPORT:\n{response.text}\n"
        except Exception as e:
            console_print(f"[AI Fetch Notice]: {e}")

    # Save to file
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(data_content)

    speak(f"Internet data successfully compiled and saved to {filepath}.")
    try:
        os.startfile(filepath)
    except OSError:
        logger.exception("Could not open report")


# 4. Universal Offline App Launcher
def open_system_app(app_name):
    app_clean = app_name.lower().strip()

    if "whatsapp" in app_clean:
        speak("Opening WhatsApp.")
        os.system("start whatsapp:")
        return

    if "recycle bin" in app_clean:
        speak("Opening Recycle Bin.")
        os.system("start shell:RecycleBinFolder")
        return

    if "windows update" in app_clean or "update" in app_clean:
        speak("Opening Windows Update settings.")
        os.system("start ms-settings:windowsupdate")
        return

    if "chrome" in app_clean or "google" in app_clean:
        speak("Opening Chrome.")
        webbrowser.open("https://google.com")
        return

    if "youtube" in app_clean:
        speak("Opening YouTube.")
        webbrowser.open("https://youtube.com")
        return

    if "github" in app_clean:
        speak("Opening GitHub.")
        webbrowser.open("https://github.com")
        return

    if "gmail" in app_clean:
        speak("Opening Gmail.")
        webbrowser.open("https://mail.google.com")
        return

    if "browser" in app_clean or "internet" in app_clean:
        speak("Opening your browser.")
        webbrowser.open("https://www.google.com")
        return

    if "brave" in app_clean:
        speak("Opening Brave Browser.")
        os.system("start brave")
        return

    if "code" in app_clean or "vs code" in app_clean or "vscode" in app_clean:
        speak("Opening Visual Studio Code.")
        os.system("start code")
        return

    if "notepad" in app_clean:
        speak("Opening Notepad.")
        os.system("start notepad")
        return

    if "calc" in app_clean or "calculator" in app_clean:
        speak("Opening Calculator.")
        os.system("start calc")
        return

    if "file explorer" in app_clean or "this pc" in app_clean:
        speak("Opening File Explorer.")
        os.system("start explorer")
        return

    speak(f"Launching {app_name}.")
    pyautogui.press("win")
    time.sleep(0.2)
    pyautogui.write(app_name)
    time.sleep(0.2)
    pyautogui.press("enter")


# 5. Email Reader Module
def check_unread_emails():
    if not EMAIL_USER or not EMAIL_PASS:
        speak("Email credentials missing in .env file.")
        return

    try:
        speak("Checking inbox...")
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select("inbox")

        status, messages = mail.search(None, "UNSEEN")
        email_ids = messages[0].split() if messages and messages[0] else []

        if not email_ids:
            speak("No unread emails, boss.")
            return

        speak(f"You have {len(email_ids)} unread emails.")
        for email_id in email_ids[-3:]:
            res, msg = mail.fetch(email_id, "(RFC822)")
            for response_part in msg:
                if isinstance(response_part, tuple):
                    msg_obj = email.message_from_bytes(response_part[1])
                    parts = decode_header(msg_obj.get("Subject", "(no subject)"))
                    subject, encoding = parts[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(
                            encoding if encoding else "utf-8"
                        )
                    sender = msg_obj.get("From")
                    speak(f"From {sender}: {subject}")

        mail.close()
        mail.logout()
    except Exception as e:
        console_print(f"[Email Error]: {e}")
        speak("Failed to access email inbox.")


def normalize_voice_command(command):
    """Normalize English phrases for local actions."""
    text = command.lower().strip()
    if "youtube" in text and any(word in text for word in ("close", "exit", "quit")):
        return "close youtube"

    if "youtube" in text and "play" in text:
        remainder = text.split("play", 1)[1].strip()
        remainder = re.sub(r"\b(?:on|in) youtube\s*$", "", remainder).strip()
        for prefix in ("a song", "some music", "music"):
            if remainder == prefix:
                remainder = ""
        return f"play {remainder}" if remainder else "open youtube and play"

    app_names = ("youtube", "whatsapp", "github", "gmail", "chrome", "brave", "notepad", "browser", "calculator")
    open_words = ("open", "launch", "start")
    if any(name in text for name in app_names) and any(word in text for word in open_words):
        for name in app_names:
            if name in text:
                return f"open {name}"
    return text


def _recognize_english(audio):
    """Use Google's Indian English model for spoken English commands."""
    return recognizer.recognize_google(audio, language="en-IN")


def close_youtube_tab():
    """Close the focused YouTube browser tab only when its title confirms it."""
    try:
        import pygetwindow
        title = pygetwindow.getActiveWindowTitle() or ""
        if "youtube" not in title.lower():
            return False
        pyautogui.hotkey("ctrl", "w")
        return True
    except Exception:
        logger.exception("Could not safely close the active YouTube tab")
        return False


# 6. Direct Command Listening
def listen(source, transcript_callback=None):
    set_voice_status("Listening for your command…")
    console_print("\n[DO] Listening for command...")
    try:
        audio = recognizer.listen(source, timeout=5, phrase_time_limit=8)
    except sr.WaitTimeoutError:
        return ""

    try:
        command = _recognize_english(audio)
        console_print(f"You: {command}")
        if not is_english_text(command):
            if transcript_callback:
                transcript_callback(f"IGNORED (English only): {command}")
            set_voice_status("Non-English speech ignored. English only.")
            return ""
        if transcript_callback:
            transcript_callback(command)
        return command.lower()
    except sr.UnknownValueError:
        return ""
    except sr.RequestError:
        set_voice_status("Speech recognition service unavailable. Check your internet connection.")
        return ""


# 7. AI Response Engine
def get_ai_response(user_input):
    if not chat:
        return "AI brain is currently unavailable."

    try:
        response = chat.send_message(user_input)
        return response.text
    except Exception as e:
        err_msg = str(e)
        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
            console_print("\n[Quota Error]: Gemini API rate limit reached.")
            return "API limit reached. Retrying shortly."
        elif "503" in err_msg or "UNAVAILABLE" in err_msg:
            console_print("\n[Server Error]: Gemini API temporarily busy.")
            return "Server demand is high right now."
        else:
            console_print(f"\n[API Error]: {e}")
            return "Network connection issue."


# 8. Main Execution Loop
def run_jarvis(stop_event=None, status_callback=None, transcript_callback=None, permission_callback=None):
    global voice_status_callback
    voice_status_callback = status_callback
    show_status("BOOT SEQUENCE")
    speak("Do is online. Calibrating microphone.")

    with sr.Microphone() as source:
        # Calibrate room audio once and LOCK sensitivity threshold for high speed
        recognizer.adjust_for_ambient_noise(source, duration=0.8)
        recognizer.dynamic_energy_threshold = (
            False  # Stops mic threshold floating
        )
        speak("Microphone calibrated. Tell me what you need.")
        show_status()

        while stop_event is None or not stop_event.is_set():
            try:
                query = normalize_voice_command(listen(source, transcript_callback=transcript_callback))
                if stop_event is not None and stop_event.is_set():
                    break
                if not query:
                    continue
                show_status("VOICE ACTIVE")

                if permission_callback is not None and not permission_callback(query):
                    speak("That action is turned off in Do settings. You can enable it in the permissions menu.")
                    continue

                # System Shutdown
                if query.strip() in {
                    "stop", "exit", "goodbye", "shutdown", "shut down", "go offline"
                }:
                    speak("Shutting down core systems.")
                    break

                # Close only a focused YouTube tab; don't close an unrelated window.
                elif query == "close youtube":
                    if close_youtube_tab():
                        speak("Closed the active YouTube tab.")
                    else:
                        speak("Bring the YouTube tab to the front first, then ask me to close it.")

                # Time Command
                elif "time" in query:
                    current_time = datetime.datetime.now().strftime(
                        "%I:%M %p"
                    )
                    speak(f"It is {current_time}")

                # System Status
                elif (
                    "system status" in query
                    or "cpu" in query
                    or "ram" in query
                ):
                    cpu = psutil.cpu_percent()
                    ram = psutil.virtual_memory().percent
                    speak(f"CPU at {cpu} percent, RAM at {ram} percent.")

                # Internet Data Search & Save to File
                elif any(
                    phrase in query
                    for phrase in [
                        "save to file",
                        "write to file",
                        "save internet data",
                        "download data",
                    ]
                ) or ("search internet for" in query):
                    topic = (
                        query.replace("search internet for", "")
                        .replace("save to file", "")
                        .replace("write to file", "")
                        .replace("save internet data about", "")
                        .replace("download data about", "")
                        .replace("get info on", "")
                        .strip()
                    )
                    if topic:
                        fetch_internet_data_and_save(topic)
                    else:
                        speak(
                            "Which topic would you like me to fetch internet data for?"
                        )

                # Power Controls
                elif any(
                    w in query
                    for w in ["sleep mode", "sleep pc", "system in sleep"]
                ):
                    speak("Putting system into sleep mode.")
                    os.system(
                        "rundll32.exe powrprof.dll,SetSuspendState 0,1,0"
                    )

                elif "lock" in query and (
                    "screen" in query or "pc" in query
                ):
                    speak("Locking PC.")
                    os.system("rundll32.exe user32.dll,LockWorkStation")

                # Screenshot
                elif "screenshot" in query or "take a picture" in query:
                    pyautogui.screenshot("jarvis_screenshot.png")
                    speak("Screenshot captured.")

                # Volume Controls
                elif "volume up" in query or "increase volume" in query:
                    pyautogui.press("volumeup", presses=5)
                    speak("Volume increased.")

                elif "volume down" in query or "decrease volume" in query:
                    pyautogui.press("volumedown", presses=5)
                    speak("Volume decreased.")

                elif "mute" in query or "unmute" in query:
                    pyautogui.press("volumemute")

                # YouTube Controls
                elif "dislike" in query:
                    speak("Disliking video.")

                elif "like" in query and "video" in query:
                    speak("Liking video.")
                    pyautogui.hotkey("shift", "l")

                elif any(
                    w in query
                    for w in ["restart", "start again", "replay", "beginning"]
                ):
                    pyautogui.press("0")
                    speak("Restarting video.")

                elif any(
                    w in query
                    for w in ["rewind", "backward", "back", "go back", "rew"]
                ):
                    pyautogui.press("j")
                    speak("Rewinding 10 seconds.")

                elif any(
                    w in query
                    for w in [
                        "fast forward",
                        "forward",
                        "skip 10 seconds",
                    ]
                ):
                    pyautogui.press("l")
                    speak("Skipping forward 10 seconds.")

                elif any(w in query for w in ["pause", "resume", "unpause"]):
                    pyautogui.press("k")
                    speak("Playback toggled.")

                elif "fullscreen" in query or "full screen" in query:
                    pyautogui.press("f")
                    speak("Fullscreen toggled.")

                elif (
                    "next video" in query
                    or "play next" in query
                    or "skip video" in query
                ):
                    pyautogui.hotkey("shift", "n")
                    speak("Playing next video.")

                # Email Check
                elif "email" in query or "read mail" in query:
                    check_unread_emails()

                # File Creation
                elif "create a file" in query or "make a file" in query:
                    filename = (
                        query.replace("create a file", "")
                        .replace("make a file", "")
                        .replace("in vs code", "")
                        .strip()
                    )
                    if not filename:
                        filename = "workspace_file.txt"
                    if "python" in query and not filename.endswith(".py"):
                        filename += ".py"
                    filename = safe_filename(filename)

                    with open(filename, "w", encoding="utf-8") as f:
                        f.write("# File created by Jarvis\n")
                    speak(f"Created file {filename}. Opening now.")
                    try:
                        os.startfile(filename)
                    except OSError:
                        logger.exception("Could not open created file")

                # Media Launcher
                elif query == "open youtube and play":
                    open_system_app("youtube")
                    speak("What would you like me to play?")

                elif "play" in query:
                    song = query.replace("play", "").strip()
                    if song:
                        speak(f"Playing {song}.")
                        pywhatkit.playonyt(song)
                        time.sleep(1.5)
                        pyautogui.press("space")
                    else:
                        speak("What would you like me to play?")

                # Universal Application Opener
                elif any(
                    query.startswith(prefix)
                    for prefix in [
                        "open ",
                        "launch ",
                        "start ",
                        "on desktop ",
                    ]
                ):
                    app_target = query
                    for prefix in [
                        "on desktop launch ",
                        "on desktop open ",
                        "on desktop ",
                        "launch ",
                        "open ",
                        "start ",
                    ]:
                        if app_target.startswith(prefix):
                            app_target = app_target.replace(prefix, "", 1)
                    open_system_app(app_target.strip())

                elif "check update" in query or "windows update" in query:
                    open_system_app("windows update")

                # Web Search
                elif "search" in query or "google" in query:
                    search_term = (
                        query.replace("search", "")
                        .replace("google", "")
                        .strip()
                    )
                    if search_term:
                        speak(f"Searching for {search_term}")
                        search_url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(search_term)
                        webbrowser.open(search_url)

                # General AI Voice Reasoning
                else:
                    ai_reply = get_ai_response(query)
                    speak(ai_reply)
            except KeyboardInterrupt:
                speak("Offline.")
                sys.exit(0)

    if stop_event is not None and stop_event.is_set():
        speak("Voice interface offline.")
    voice_status_callback = None


if __name__ == "__main__":
    run_jarvis()
