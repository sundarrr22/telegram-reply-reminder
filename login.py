import os

from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION_NAME = os.environ.get("SESSION_NAME", "reminder")

if __name__ == "__main__":
    with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        me = client.get_me()
        print(f"Logged in as {me.first_name} (id={me.id})")
        print(f"Session saved to {SESSION_NAME}.session — keep this file secret.")
