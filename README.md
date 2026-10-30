# Do — Personal Desktop Assistant

Do is a Windows desktop assistant project built around voice commands, a Gemini chat panel, and local desktop actions. Its interface uses a compact obsidian split-pane layout with a quiet voice activity visualizer, keyboard command palette, and readable assistant replies. The visualizer reflects listening and response state; it is not a model of Do's intelligence or a microphone-level meter.

## What Do can do today

- **Voice commands:** Start and stop voice listening from the app or system tray. Summon the window with `Ctrl + Space` or `Alt + J`. There is no wake word.
- **English speech input:** Speech recognition requests Google's online recognizer using `en-IN`. A local word-list filter blocks non-Latin scripts and catches some common non-English phrases.
- **Desktop actions:** Open common applications and sites, search the web, play YouTube music, control YouTube playback, change volume, capture a screenshot, show system gauges, create a basic file, lock or sleep Windows, and read recent unread email when configured.
- **Gemini chat:** Send English text to Gemini for general questions. Chat uses a Gemini API key from `.env`.
- **Portable command line:** Install the `do` command on Windows, macOS, or Linux for one-shot questions, interactive text chat, configuration, and status.
- **Voice Test Log:** View the last ten recognized phrases. The log is held in memory and clears when Do closes.
- **Memory Vault:** Save and delete up to 200 local notes. Each note can contain up to 4,000 characters. Notes are not sent to Gemini.
- **Quick actions:** Run common typed requests from the console buttons.
- **Command palette:** Press `Ctrl + K` (or `⌘ + K` on macOS browsers) to search and run Do actions. Press `/` outside a text field to open it, use arrow keys to move, `Enter` to run, and `Esc` to close.
- **Windows tray and hotkeys:** Show or hide Do and toggle voice listening from the tray menu.

## Try these commands

Speak naturally in English after starting voice listening. Commands are pattern-based; these examples match the current implementation.

| Say | What Do does |
| --- | --- |
| `open WhatsApp`, `open GitHub`, `open Notepad` | Launches the named app or site. Common targets include Chrome, Brave, VS Code, Calculator, File Explorer, YouTube, Gmail, and GitHub. |
| `close YouTube` | Closes the active browser tab only when its window title contains YouTube. Bring that tab to the front first. |
| `play lo-fi hip hop` | Searches for and plays the requested music on YouTube. |
| `pause`, `resume`, `rewind`, `fast forward`, `fullscreen`, `next video` | Sends the matching YouTube player shortcut to the currently active window. Keep the YouTube player focused. |
| `what time is it` | Reads the local time. |
| `system status` | Reports CPU, memory, and storage information. |
| `volume up`, `volume down`, `mute` | Changes the Windows master volume. |
| `take a screenshot` | Saves a screenshot in the project or app working folder. |
| `search the internet for space exploration` | Creates a short research report file using available web and Gemini sources. |
| `create a file ideas.txt` | Creates a text file in the current working folder and attempts to open it. |
| `lock screen`, `sleep mode` | Locks Windows or requests Windows sleep. |
| `read email` | Reads up to three recent unread Gmail messages when email credentials are configured. |

`stop`, `exit`, or `go offline` ends the voice-listening loop; these phrases do not shut down Windows. The local text chat currently handles a narrower set of direct actions than voice mode; requests it cannot execute are sent to Gemini as chat.

## Requirements

- Windows 10 or 11 for the desktop shell and native desktop commands.
- 64-bit Python 3.12 to run from source or build the executable.
- Microsoft Edge WebView2 Runtime for the desktop window.
- A microphone and internet connection for speech recognition. Speech audio is processed by Google's online speech-recognition service.
- A Gemini API key for Gemini chat and AI-generated research reports. The basic local commands can work without it.
- Optional Gmail address and app password for the email-reading command. Enable IMAP for the Gmail account first.

## Configure

Copy `.env.example` to `.env` if you do not already have a local `.env`, then add the credentials you need:

```dotenv
GEMINI_API_KEY=your_gemini_api_key_here
EMAIL_USER=your_gmail_address
EMAIL_PASS=your_gmail_app_password
```

`GEMINI_API_KEY` enables Gemini chat. `EMAIL_USER` and `EMAIL_PASS` are optional. For Gmail, use an app password rather than your main account password. Keep `.env` private; it is excluded from Git and is not bundled inside the executable.

Gemini chat defaults to `gemini-3.5-flash-lite` with minimal reasoning for quicker everyday replies and a 700-token response cap. If it fails, Do tries `gemini-3.8-flash` once. Set `DO_GEMINI_MODEL` and `DO_GEMINI_FALLBACK_MODEL` in `.env` to choose different supported models. Gemini text is streamed into the chat as it arrives, and the chat shows elapsed wait time before the first token; actual latency still depends on your network and Google's service.

## Install the portable command line (Python required on that computer)

The CLI needs Python 3.10 or newer and internet access for Gemini. It is separate from the Windows desktop shell, so its text-chat commands also work on macOS and Linux.

From a checked-out copy of this project, create and activate a virtual environment, then install the project:

```sh
python -m venv .venv-do
```

On systems where the Python command is named `python3`, use `python3` for the environment creation and pip commands instead.

Activate it in PowerShell:

```powershell
.\.venv-do\Scripts\Activate.ps1
```

Or activate it in macOS/Linux:

```sh
source .venv-do/bin/activate
```

Then, on any of those systems:

```sh
python -m pip install .
do status
do configure
do ask "What can you help me with?"
do chat
```

If you already use `pipx` and want the `do` command available without activating a virtual environment, run `pipx install .` from the project folder instead of `python -m pip install .`.

`do configure` securely prompts for a Gemini API key without echoing it and saves it to a per-user config file. Shell environment variables take precedence, followed by Do's user config and then a `.env` file in the current folder. Each computer using this CLI needs its own Python installation and Gemini configuration. The CLI is not the install path for a friend who has no Python.

The user config is `%APPDATA%\Do\.env` on Windows, `$XDG_CONFIG_HOME/do/.env` when `XDG_CONFIG_HOME` is set, or `~/.config/do/.env` on macOS/Linux. CLI chat history is kept only in the current process and is not saved to disk.

CLI commands:

- `do configure` — save or replace the Gemini key.
- `do status` — show Python, operating system, and key configuration status without exposing the key.
- `do ask "question"` — ask one question and exit. `do ask -` reads the question from standard input.
- `do chat` — continue a text conversation; enter `exit` or press `Ctrl+C` to leave.
- `do --help` — show command help.

The cross-platform CLI currently handles English Gemini text chat only. It does not launch apps, control the desktop, or listen to a microphone; those features remain in the Windows desktop assistant and depend on OS-specific integrations.

## Host Do as an installable website (friends do not install Python)

The website build runs on one server. Friends only need a modern browser and the HTTPS website address; they can install it from the browser as a PWA. The website version provides Gemini text chat and browser-local notes. It cannot control a visitor's computer or use its microphone as the Windows desktop build does. Never expose the server directly without HTTPS.

### Deploy with a Docker-capable host

1. Put this project in a private Git repository and connect it to a hosting provider that can build a `Dockerfile` and expose an HTTPS web service. Configure the service to use the repository root as its build context.
2. Set these server environment variables in the host dashboard (do not commit real values):

   ```text
   GEMINI_API_KEY=your_server_side_gemini_key
   DO_HOSTED_MODE=1
   DO_ACCESS_CODE=a-long-random-private-code
   ```

   The container listens on the host-provided `PORT` (default 8000). The hosting provider must terminate HTTPS and proxy requests to the container. Do refuses to start in hosted mode without `DO_ACCESS_CODE`.
3. Open the HTTPS address, enter the access code, and share both the address and code with people you trust. Use a long random code. The current access gate is a shared code rather than individual accounts; anyone with the code can use the shared Gemini quota. Access attempts are limited per source address.
4. On desktop Chrome or Edge, use the browser's install icon/menu. On iPhone, open the HTTPS address in Safari and choose **Share → Add to Home Screen**. On Android, use the browser menu's **Install app** or **Add to Home screen** option.

The server-side Gemini key remains on the host. The browser keeps the access code in session storage and notes in that browser's local storage; notes are not uploaded. The service worker caches only the static app shell and never caches API calls or conversations. Chat needs an internet connection. Hosted mode disables desktop voice and local-computer actions; voice remains available in the Windows app.

This repository includes a generic `Dockerfile`, `requirements-web.txt`, PWA manifest, icon, and service worker. It does not include a hosting account or public domain, so deployment must be completed from the owner's hosting account before a friend can open a public link. Keep the host patched, rotate the shared code if it leaks, and monitor Gemini usage.

### What “like Siri” means for Do

The installed website can be opened from the home screen and accepts typed English chat. A browser PWA cannot provide Siri's operating-system wake-word or background assistant privileges. Apple's supported integration path for app actions is App Intents, which makes selected app actions available to Siri and Shortcuts; Do would need a native iOS app and deliberately defined intents for that deeper integration. [Apple App Intents](https://developer.apple.com/documentation/appintents/app-intents) · [Siri and App Intents](https://developer.apple.com/documentation/appintents/apple-intelligence-and-siri-ai).

## Run from source

Open PowerShell in the project folder and run:

```powershell
py -3.12 -m venv .venv-desktop
.\.venv-desktop\Scripts\python.exe -m pip install -r requirements-desktop.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
.\.venv-desktop\Scripts\python.exe .\desktop_app.py
```

Add your Gemini key, save `.env`, and restart Do after changing credentials. If `.venv-desktop` already exists, skip its creation step.

## Run the browser development version

After installing the requirements and configuring `.env`:

```powershell
.\.venv-desktop\Scripts\python.exe .\web_server.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Stop the server with `Ctrl+C`. The server binds to loopback (`127.0.0.1`); the Gemini key stays on the Python side and is not exposed to frontend JavaScript.

## Build the Windows executable

The included PowerShell script builds a one-file Windows executable and packages the frontend:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1 -AppName Do
```

The default output is `dist\Do.exe`. To create a distinctly named build, replace `Do` with a name such as `Do-Hologram`. Add your Gemini key to `dist\.env` before running the executable. The script copies `.env.example` only when `dist\.env` does not already exist, so it does not overwrite existing credentials. Build on Windows; the executable is not cross-platform.

The current standard desktop build is `dist\Do.exe`.

## Data and privacy

- Messages not handled by Do's local command runner are sent to Google Gemini when the API key is configured. Up to twelve recent conversation messages are included in a chat request.
- Voice audio is sent to Google's speech-recognition service. The transcript log keeps only ten entries in memory and is cleared on exit; rejected non-English phrases are marked as ignored in that log.
- Notes are stored locally in `%LOCALAPPDATA%\Do\notes.json` (or a user-local data folder on non-Windows systems). Notes are not currently included in Gemini requests.
- Optional email credentials are used by the voice email command to connect to Gmail via IMAP over SSL.
- The portable CLI stores its Gemini key in the per-user config path described above; it never echoes the key in terminal output.
- The local app server listens on `127.0.0.1`. Write requests check that they come from the app's local origin.
- Do's English-only filter is an offline heuristic, not a full language detector. It rejects non-Latin scripts and recognizes a limited list of common non-English words, so it can miss unfamiliar phrases or reject an English sentence containing a listed word.

## Current limitations

- Do does not yet interpret the desktop screen or images with computer vision. Its voice visualizer reflects listener state and does not analyze microphone amplitude.
- Voice actions rely on phrase matching and keyboard shortcuts. Some actions can be unreliable when the wrong window is focused; keep the intended app active, especially for YouTube playback controls.
- The speech service needs internet access, and recognition quality depends on the microphone, room noise, accent, and service availability.
- Gemini can answer questions, but it does not have a general-purpose tool layer for taking arbitrary desktop actions.
- The app is Windows-focused; native commands and the desktop shell will not work as-is on macOS or Linux.
- The project does not currently include a software license.

## Project layout

```text
desktop_app.py          Windows desktop window, tray icon, and global hotkeys
do_cli.py               Cross-platform command-line chat and setup commands
pyproject.toml          Python package metadata and `do` command entry point
web_server.py           Loopback web server, Gemini chat bridge, voice status, and local notes
jarvis.py               Speech recognition, text-to-speech, and desktop command handlers
language_filter.py      Offline English-input heuristic
frontend/index.html     Do interface structure
frontend/app.js         Chat, notes, voice controls, command palette, and reply rendering
frontend/obsidian.css   Responsive obsidian interface and component styles
build_exe.ps1           Windows executable build script
requirements-desktop.txt Python and desktop dependencies
.env.example            Safe example configuration; add real credentials to a private .env
```

The `jarvis.py` filename is a legacy module name; the application is branded Do and does not use a wake word.

## A future for Do and AI

The roadmap below is a direction for the project, not a list of features that already exist. The goal is to make Do more capable while keeping actions understandable and under the user's control.

### 1. Make commands dependable

- Show the live transcript, detected intent, and target app before an action runs.
- Add confidence checks, clarification questions, and a simple way to correct misheard commands.
- Replace scattered phrase checks with a documented command registry and reusable app adapters.
- Add action history, clear success or failure feedback, and undo where an action can be reversed.

### 2. Add optional visual understanding

- Let the user explicitly ask Do to inspect a screenshot or the current window.
- Identify visible controls and explain a proposed click sequence before acting.
- Start with read-only screen descriptions; require confirmation for consequential actions such as sending, deleting, or changing settings.
- Keep screen capture off unless the user starts a visual request, and show a clear capture indicator.

### 3. Build useful personal memory

- Add opt-in preferences and project context that the user can view, edit, export, and delete.
- Keep personal memory local by default and ask before sending it to an AI service.
- Support user-defined commands such as “when I say focus mode, open my work apps and set my volume to 20%.”

### 4. Improve privacy and resilience

- Explore on-device speech recognition, local text-to-speech, and small local language models for basic tasks.
- Make network-dependent features clearly show when data leaves the computer.
- Keep Gemini as an optional capability, with graceful offline behavior for local commands and notes.

### 5. Add a safe tool ecosystem

- Connect apps through small, documented tools instead of giving an AI unrestricted access to the desktop.
- Give each tool the minimum permissions it needs and keep a readable action log.
- Let users enable, disable, and review integrations individually.

A strong long-term version of Do would combine language, vision, memory, and reliable app integrations, but it should always show what it understood, explain what it plans to do, and let the user decide when an action needs approval.

## License

No license is included. Add a license before distributing or inviting others to reuse this project.
