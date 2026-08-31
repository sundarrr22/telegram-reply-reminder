import asyncio
import os
import sys

from dotenv import load_dotenv
from telethon import TelegramClient

from reminder import db

load_dotenv()

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION_NAME = os.environ.get("SESSION_NAME", "reminder")
DB_PATH = os.environ.get("DB_PATH", "reminder.sqlite3")

USAGE = "Usage: python set_threshold.py [list | set <chat_id> <hours> | clear <chat_id>]"


async def list_chats(client) -> None:
    async for dialog in client.iter_dialogs():
        if dialog.is_user:
            print(f"{dialog.id}\t{dialog.name}")


async def main() -> None:
    conn = db.connect(DB_PATH)
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()
    try:
        args = sys.argv[1:]
        if not args or args[0] == "list":
            await list_chats(client)
        elif args[0] == "set" and len(args) == 3:
            chat_id, hours = int(args[1]), float(args[2])
            db.set_threshold(conn, chat_id, hours)
            print(f"Set threshold for {chat_id} to {hours}h")
        elif args[0] == "clear" and len(args) == 2:
            chat_id = int(args[1])
            db.clear_threshold(conn, chat_id)
            print(f"Cleared threshold for {chat_id}")
        else:
            print(USAGE)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
