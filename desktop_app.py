"""Do native Windows desktop launcher with system tray and global hotkeys."""

import ctypes
import os
import sys
import threading
import time
from ctypes import wintypes

from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item
import webview


class _QuietStream:
    """Keep standard logging safe in the windowed PyInstaller executable."""

    encoding = "utf-8"

    def write(self, value):
        return len(value)

    def flush(self):
        pass


if getattr(sys, "frozen", False):
    sys.stdout = _QuietStream()
    sys.stderr = _QuietStream()

from web_server import ROOT, create_server, stop_voice_worker, toggle_voice_worker


def create_tray_icon():
    """Generate a small orbital-core mark for Do's Windows system tray icon."""
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((8, 8, 56, 56), fill="#08111f", outline="#70f4ff", width=2)
    draw.ellipse((2, 19, 62, 45), outline="#a372ff", width=2)
    draw.ellipse((13, 13, 51, 51), outline="#70f4ff", width=1)
    draw.ellipse((23, 23, 41, 41), fill="#49cde8", outline="#d9feff", width=1)
    draw.ellipse((27, 26, 32, 31), fill="#ffffff")
    return image


def run_hotkey_listener(toggle_callback, stop_event):
    """Listens for global summon hotkeys (Ctrl + Space and Alt + J) across Windows."""
    user32 = ctypes.windll.user32
    MOD_ALT = 0x0001
    MOD_CONTROL = 0x0002
    MOD_NOREPEAT = 0x4000
    VK_SPACE = 0x20
    VK_J = 0x4A

    # Register hotkeys
    registered = []
    if user32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_NOREPEAT, VK_SPACE):
        registered.append(1)
    else:
        print("Could not register Ctrl+Space; another application may use it.")
    if user32.RegisterHotKey(None, 2, MOD_ALT | MOD_NOREPEAT, VK_J):
        registered.append(2)
    else:
        print("Could not register Alt+J; another application may use it.")

    msg = wintypes.MSG()
    try:
        while not stop_event.is_set():
            if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                if msg.message == 0x0312:  # WM_HOTKEY
                    toggle_callback()
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            time.sleep(0.04)
    finally:
        for hotkey_id in registered:
            user32.UnregisterHotKey(None, hotkey_id)


def main():
    os.chdir(ROOT)
    server = create_server(port=0)
    address, port = server.server_address
    server_thread = threading.Thread(target=server.serve_forever, name="do-local-api", daemon=True)
    server_thread.start()

    window = None
    tray_icon = None
    stop_hotkey = threading.Event()
    is_visible = [True]

    def toggle_window():
        if not window:
            return
        try:
            if is_visible[0]:
                window.hide()
                is_visible[0] = False
            else:
                window.show()
                window.restore()
                is_visible[0] = True
        except Exception:
            pass

    def on_tray_toggle(icon, item):
        toggle_window()

    def on_tray_exit(icon, item):
        stop_hotkey.set()
        if icon:
            icon.stop()
        if window:
            try:
                window.destroy()
            except Exception:
                pass

    try:
        window = webview.create_window(
            "Do | Personal Intelligence",
            f"http://{address}:{port}/",
            width=1440,
            height=960,
            min_size=(920, 680),
            background_color="#080d18",
            text_select=True,
        )

        # Setup System Tray
        tray_menu = pystray.Menu(
            item("Show / Hide Do (Ctrl+Space)", on_tray_toggle, default=True),
            item("Toggle Voice Assistant", lambda icon, item: toggle_voice_worker()),
            item("Exit Do", on_tray_exit),
        )
        tray_icon = pystray.Icon("Do", create_tray_icon(), "Do (Ctrl+Space)", tray_menu)
        threading.Thread(target=tray_icon.run, daemon=True, name="do-tray").start()

        # Setup Global Hotkey Thread
        threading.Thread(target=run_hotkey_listener, args=(toggle_window, stop_hotkey), daemon=True, name="jarvis-hotkeys").start()

        window.events.closed += lambda: on_tray_exit(tray_icon, None)
        webview.start(debug=False)

    except Exception as error:
        ctypes.windll.user32.MessageBoxW(
            None,
            "Do could not start its desktop window. "
            "Install or update Microsoft Edge WebView2 Runtime, then try again.\n\n"
            f"Details: {error}",
            "Do startup error",
            0x10,
        )
    finally:
        stop_hotkey.set()
        if tray_icon:
            try:
                tray_icon.stop()
            except Exception:
                pass
        stop_voice_worker()
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
