# Do Frontend

The frontend is the interface for Do's Windows desktop assistant and local browser development mode. It includes the command console, English voice status and recent-transcript log, Gemini chat, local notes, and a procedural canvas hologram.

For setup, build instructions, current capabilities, privacy notes, limitations, and the future AI roadmap, see the [project README](../README.md).

## Browser development mode

From PowerShell in the project folder, start the local Python server:

```powershell
.\.venv-desktop\Scripts\python.exe .\web_server.py
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000). The server binds to loopback. Configure `GEMINI_API_KEY` in the project `.env` for AI chat. The **START VOICE ASSISTANT** button starts the Python microphone worker; recognition requires an internet connection.
