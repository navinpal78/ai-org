#!/usr/bin/env python3

import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

AI_HOME = Path.home() / "AI"
TOKEN_FILE = AI_HOME / "secrets" / "telegram-ceo-bot.token"
CONFIG_FILE = AI_HOME / "secrets" / "telegram-ceo-gateway.env"
STATUS_FILE = AI_HOME / "logs" / "ceo" / "status"
OPENCODE = Path.home() / ".opencode" / "bin" / "opencode"

API_TIMEOUT = 45
POLL_TIMEOUT = 30
CEO_TIMEOUT = 600
MAX_TASK_LENGTH = 2000


def load_config():
    if not TOKEN_FILE.exists():
        raise RuntimeError(f"Telegram token missing: {TOKEN_FILE}")

    token = TOKEN_FILE.read_text().strip()
    if not token:
        raise RuntimeError("Telegram token is empty")

    allowed_user_id = None

    if CONFIG_FILE.exists():
        for line in CONFIG_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("TELEGRAM_ALLOWED_USER_ID="):
                allowed_user_id = line.split("=", 1)[1].strip()

    if not allowed_user_id:
        raise RuntimeError("TELEGRAM_ALLOWED_USER_ID is missing")

    return token, int(allowed_user_id)


TOKEN, ALLOWED_USER_ID = load_config()
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"


def telegram(method, data=None):
    url = f"{BASE_URL}/{method}"

    if data:
        encoded = urllib.parse.urlencode(data).encode()
        request = urllib.request.Request(url, data=encoded)
    else:
        request = urllib.request.Request(url)

    with urllib.request.urlopen(request, timeout=API_TIMEOUT) as response:
        result = json.loads(response.read().decode())

    if not result.get("ok"):
        raise RuntimeError(f"Telegram API error: {result}")

    return result["result"]


def send_message(chat_id, text):
    telegram(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
        },
    )


def read_status():
    if not STATUS_FILE.exists():
        return "NOT_READY", {}

    values = {}

    for line in STATUS_FILE.read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
        elif line.strip():
            values["status"] = line.strip()

    return values.get("status", "UNKNOWN"), values


def status_message():
    status, values = read_status()

    lines = [
        "CEO STATUS",
        "",
        status,
        "",
        f"OpenCode: {values.get('opencode', 'unknown')}",
        f"Python: {values.get('python', 'unknown')}",
        f"Node: {values.get('node', 'unknown')}",
        f"Updated: {values.get('timestamp', 'unknown')}",
    ]

    return "\n".join(lines)


def run_ceo_task(task):
    status, _ = read_status()

    if status != "READY":
        return (
            "CEO is not available for task execution.\n\n"
            f"Current status: {status}"
        )

    if not OPENCODE.is_file() or not os.access(OPENCODE, os.X_OK):
        return "CEO runtime unavailable: OpenCode executable is missing."

    if len(task) > MAX_TASK_LENGTH:
        return (
            f"Task is too long. Maximum allowed length is "
            f"{MAX_TASK_LENGTH} characters."
        )

    prompt = (
        "Telegram gateway request. Read-only mode.\n\n"
        f"USER TASK:\n{task}"
    )

    command = [
        str(OPENCODE),
        "run",
        "--agent",
        "ceo",
        "--model",
        "lmstudio/qwen/qwen3.5-9b",
        "--dir",
        str(AI_HOME),
        prompt,
    ]

    try:
        result = subprocess.run(
            command,
            cwd=AI_HOME,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=CEO_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return (
            "CEO task timed out after "
            f"{CEO_TIMEOUT} seconds.\n\n"
            "The local model may need more time for this request."
        )
    except Exception as exc:
        print(f"CEO execution error: {exc}", flush=True)
        return "CEO runtime error while starting the task."

    if result.returncode != 0:
        print(
            f"OpenCode exit code: {result.returncode}\n"
            f"stderr: {result.stderr[-4000:]}",
            flush=True,
        )
        return (
            "CEO task failed to complete.\n\n"
            "The gateway did not receive a valid CEO response."
        )

    output = result.stdout.strip()

    if not output:
        return "CEO completed the task but returned no response."

    # Telegram messages have a practical size limit.
    if len(output) > 3800:
        output = output[:3800] + "\n\n[Response truncated by gateway]"

    return output


def handle_update(update):
    message = update.get("message")

    if not message:
        return

    sender = message.get("from", {})
    sender_id = sender.get("id")

    if sender_id != ALLOWED_USER_ID:
        print(
            f"Rejected unauthorised Telegram user: {sender_id}",
            flush=True,
        )

        chat_id = message.get("chat", {}).get("id")

        if chat_id:
            send_message(
                chat_id,
                "Access denied. This CEO gateway is restricted.",
            )

        return

    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    if text == "/start":
        send_message(
            chat_id,
            "AI Organisation CEO gateway online.\n\n"
            "Available commands:\n"
            "/status\n\n"
            "You can also send a read-only task directly.",
        )
        return

    if text == "/status":
        send_message(chat_id, status_message())
        return

    if not text:
        send_message(
            chat_id,
            "Please send a read-only task.",
        )
        return

    send_message(
        chat_id,
        "CEO is processing your read-only task...",
    )

    response = run_ceo_task(text)
    send_message(chat_id, response)


def main():
    print("=== AI Organisation CEO Telegram Gateway ===", flush=True)
    print(
        f"Allowed Telegram user ID: {ALLOWED_USER_ID}",
        flush=True,
    )

    bot = telegram("getMe")

    print(
        f"Bot: @{bot.get('username', 'unknown')}",
        flush=True,
    )

    print("Gateway polling started.", flush=True)

    offset = None

    while True:
        try:
            data = {
                "timeout": POLL_TIMEOUT,
                "allowed_updates": json.dumps(["message"]),
            }

            if offset is not None:
                data["offset"] = offset

            updates = telegram("getUpdates", data)

            for update in updates:
                offset = update["update_id"] + 1
                handle_update(update)

        except KeyboardInterrupt:
            print("Gateway stopped.", flush=True)
            return

        except Exception as exc:
            print(f"Gateway error: {exc}", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
