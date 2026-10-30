"""Cross-platform command-line interface for Do's Gemini assistant."""

from __future__ import annotations

import argparse
import getpass
import os
import platform
import sys
from pathlib import Path

from dotenv import load_dotenv, set_key

from language_filter import is_english_text


VERSION = "0.1.0"
MODEL_CANDIDATES = [
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
]
SYSTEM_PROMPT = (
    "You are Do, a helpful personal assistant. Respond in English only. "
    "Be clear and practical. Do not claim to control the computer or perform "
    "an action unless an available tool confirms it."
)


def user_config_path() -> Path:
    """Return Do's per-user configuration path on Windows, macOS, or Linux."""
    if os.name == "nt" and os.getenv("APPDATA"):
        return Path(os.environ["APPDATA"]) / "Do" / ".env"
    if os.getenv("XDG_CONFIG_HOME"):
        return Path(os.environ["XDG_CONFIG_HOME"]) / "do" / ".env"
    return Path.home() / ".config" / "do" / ".env"


def load_configuration() -> Path:
    """Load shell, project, and per-user environment configuration."""
    config = user_config_path()
    if config.is_file():
        load_dotenv(config, override=False)
    project_env = Path.cwd() / ".env"
    if project_env.is_file():
        load_dotenv(project_env, override=False)
    return config


def configure() -> int:
    config = load_configuration()
    if os.getenv("GEMINI_API_KEY"):
        print("A Gemini API key is already available in this environment.")
        replace = input("Save a different key to Do's user config? [y/N] ").strip().lower()
        if replace not in {"y", "yes"}:
            print(f"Config file: {config}")
            return 0

    key = getpass.getpass("Gemini API key (input hidden): ").strip()
    if not key:
        print("No key entered; configuration was not changed.", file=sys.stderr)
        return 2
    confirm = getpass.getpass("Enter the key again to confirm: ").strip()
    if key != confirm:
        print("The keys did not match; configuration was not changed.", file=sys.stderr)
        return 2

    config.parent.mkdir(parents=True, exist_ok=True)
    set_key(str(config), "GEMINI_API_KEY", key, quote_mode="always")
    if os.name != "nt":
        config.chmod(0o600)
    print(f"Gemini key saved to {config}")
    print("Do never prints the key. Run `do status` to check configuration.")
    return 0


def status() -> int:
    config = load_configuration()
    print(f"Do CLI {VERSION}")
    print(f"System: {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"Python: {platform.python_version()}")
    print(f"Gemini: {'configured' if os.getenv('GEMINI_API_KEY') else 'not configured'}")
    print(f"User config: {config}")
    if not os.getenv("GEMINI_API_KEY"):
        print("Run `do configure` or set GEMINI_API_KEY in your environment.")
    return 0


def create_client():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("Gemini key is missing. Run `do configure` first.")

    from google import genai
    return genai.Client(api_key=key)


def generate_response(client, messages: list[dict[str, str]]) -> str:
    from google.genai import types

    contents = []
    for message in messages[-12:]:
        role = "model" if message["role"] == "assistant" else "user"
        text = message["content"].strip()[:4000]
        if text:
            contents.append(types.Content(role=role, parts=[types.Part(text=text)]))
    config = types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT)
    last_error = None
    for model in MODEL_CANDIDATES:
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
            answer = getattr(response, "text", None)
            if answer:
                return answer.strip()
        except Exception as error:  # Try the next configured model when a model is unavailable.
            last_error = error
    detail = f": {last_error}" if last_error else ""
    raise RuntimeError(f"Gemini did not return a response{detail}")


def ask(prompt: str) -> int:
    if not prompt:
        print("Enter an English question.", file=sys.stderr)
        return 2
    if not is_english_text(prompt):
        print("Do CLI accepts English input only. Rephrase in English.", file=sys.stderr)
        return 2
    if len(prompt) > 4000:
        print("Do CLI messages are limited to 4,000 characters.", file=sys.stderr)
        return 2
    try:
        client = create_client()
        answer = generate_response(client, [{"role": "user", "content": prompt}])
    except Exception as error:
        print(f"Do could not get a Gemini response: {error}", file=sys.stderr)
        return 1
    if not answer:
        print("Gemini returned an empty response.", file=sys.stderr)
        return 1
    print(answer.strip())
    return 0


def interactive_chat() -> int:
    try:
        client = create_client()
    except Exception as error:
        print(f"Do could not start: {error}", file=sys.stderr)
        return 1

    messages: list[dict[str, str]] = []
    print("Do CLI is ready. Type `exit` or press Ctrl+C to leave.")
    while True:
        try:
            prompt = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nDo> Chat ended.")
            return 0
        if not prompt:
            continue
        if prompt.lower() in {"exit", "quit", "/exit", "/quit"}:
            print("Do> Chat ended.")
            return 0
        if not is_english_text(prompt):
            print("Do> I accept English input only. Please rephrase in English.")
            continue
        if len(prompt) > 4000:
            print("Do> Messages are limited to 4,000 characters.")
            continue
        messages.append({"role": "user", "content": prompt})
        try:
            answer = generate_response(client, messages)
            messages.append({"role": "assistant", "content": answer})
            print(f"Do> {answer}")
        except Exception as error:
            messages.pop()
            print(f"Do> I could not reach Gemini: {error}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="do",
        description="Do's cross-platform command-line assistant.",
        epilog="The portable CLI provides Gemini chat. Native desktop controls remain OS-specific.",
    )
    parser.add_argument("--version", action="version", version=f"Do CLI {VERSION}")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("configure", help="save your Gemini API key in your user config")
    commands.add_parser("status", help="show system and Gemini configuration status")

    ask_parser = commands.add_parser("ask", help="ask Do one question")
    ask_parser.add_argument("prompt", nargs="+", help="question text, or - to read it from stdin")

    commands.add_parser("chat", help="start an interactive Gemini conversation")
    return parser


def main() -> int:
    load_configuration()
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "configure":
        return configure()
    if args.command == "status":
        return status()
    if args.command == "ask":
        prompt = sys.stdin.read().strip() if args.prompt == ["-"] else " ".join(args.prompt)
        return ask(prompt)
    if args.command == "chat":
        return interactive_chat()
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
