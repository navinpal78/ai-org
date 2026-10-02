#!/usr/bin/env bash
set -euo pipefail

SECRET_DIR="$HOME/AI/secrets"
TOKEN_FILE="$SECRET_DIR/telegram-ceo-bot.token"

mkdir -p "$SECRET_DIR"
chmod 700 "$SECRET_DIR"

echo "=== CEO Telegram Gateway Setup ==="
echo
echo "Enter the Telegram bot token from BotFather."
echo "The token will NOT be displayed while you type."
echo

read -rsp "Bot token: " TOKEN
echo

if [ -z "$TOKEN" ]; then
    echo "ERROR: Empty token."
    exit 1
fi

echo "$TOKEN" > "$TOKEN_FILE"
chmod 600 "$TOKEN_FILE"

echo
echo "Testing Telegram connection..."

RESPONSE="$(python3 - "$TOKEN" <<'PY'
import json
import sys
import urllib.request

token = sys.argv[1]
url = f"https://api.telegram.org/bot{token}/getMe"

try:
    with urllib.request.urlopen(url, timeout=15) as response:
        print(response.read().decode())
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
PY
)"

echo "$RESPONSE"

python3 - "$RESPONSE" <<'PY'
import json
import sys

data = json.loads(sys.argv[1])

if not data.get("ok"):
    print("ERROR: Telegram rejected the bot token.")
    sys.exit(1)

bot = data["result"]

print()
print("Telegram bot verified:")
print(f"  Username: @{bot.get('username')}")
print(f"  Name:     {bot.get('first_name')}")
PY

echo
echo "Token saved securely at:"
echo "$TOKEN_FILE"
echo
echo "Now retrieving your Telegram user ID..."
echo "Make sure you have already sent /start to the bot."
echo

python3 - "$TOKEN" <<'PY'
import json
import sys
import urllib.request
import urllib.parse

token = sys.argv[1]
url = f"https://api.telegram.org/bot{token}/getUpdates"

try:
    with urllib.request.urlopen(url, timeout=15) as response:
        data = json.loads(response.read().decode())
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)

if not data.get("ok"):
    print("ERROR: Telegram getUpdates failed.")
    sys.exit(1)

updates = data.get("result", [])

if not updates:
    print("No updates found.")
    print("Send /start to the bot and run this setup script again.")
    sys.exit(0)

print()
print("Telegram users who have contacted this bot:")
print()

seen = set()

for update in updates:
    message = update.get("message") or update.get("edited_message")
    if not message:
        continue

    user = message.get("from")
    if not user:
        continue

    user_id = user.get("id")

    if user_id in seen:
        continue

    seen.add(user_id)

    print(f"User ID:       {user_id}")
    print(f"First name:    {user.get('first_name', '')}")
    print(f"Last name:     {user.get('last_name', '')}")
    print(f"Username:      @{user.get('username', '')}")
    print()

if not seen:
    print("No user messages found.")
PY
