import asyncio
import logging
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from telethon import TelegramClient

from reminder import db
from reminder import telegram_client as tg
from reminder.logic import needs_reply, resolve_threshold, should_run

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("reminder")

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION_NAME = os.environ.get("SESSION_NAME", "reminder")
DEFAULT_THRESHOLD_HOURS = float(os.environ.get("DEFAULT_THRESHOLD_HOURS", 24))
TIER_HOURS = {
    "close": float(os.environ.get("CLOSE_THRESHOLD_HOURS", 10)),
    "family": float(os.environ.get("FAMILY_THRESHOLD_HOURS", 2)),
}
MAX_GROUP_SIZE = int(os.environ.get("MAX_GROUP_SIZE", 10))
FOLDER_NAME = os.environ.get("FOLDER_NAME", "To Reply Soon")
RUN_INTERVAL_HOURS = float(os.environ.get("RUN_INTERVAL_HOURS", 36))
DB_PATH = os.environ.get("DB_PATH", "reminder.sqlite3")


async def process_dialog(client, conn, folder, dialog, now: datetime) -> None:
    chat_id = dialog.id
    batch = await tg.fetch_unreplied_batch(client, dialog)
    reacted = await tg.my_reaction_on_last(client, dialog, batch)
    override = db.get_threshold(conn, chat_id)
    tier = db.get_tier(conn, chat_id)
    threshold = resolve_threshold(override, tier, TIER_HOURS, DEFAULT_THRESHOLD_HOURS)
    unanswered = needs_reply(batch, now, threshold, reacted)

    if unanswered and not db.is_flagged(conn, chat_id):
        await tg.add_peer_to_folder(client, folder, dialog.entity)
        db.mark_flagged(conn, chat_id, now)
        logger.info("Flagged chat %s (%s)", chat_id, dialog.name)
    elif not unanswered and db.is_flagged(conn, chat_id):
        await tg.remove_peer_from_folder(client, folder, dialog.entity)
        db.unmark_flagged(conn, chat_id)
        logger.info("Unflagged chat %s (%s)", chat_id, dialog.name)


async def main() -> None:
    conn = db.connect(DB_PATH)
    now = datetime.now(timezone.utc)

    last_run = db.get_last_run_at(conn)
    if not should_run(last_run, now, RUN_INTERVAL_HOURS):
        logger.info("Not due yet (last run %s), skipping", last_run)
        conn.close()
        return

    if not os.path.exists(f"{SESSION_NAME}.session"):
        logger.error("No session file found at %s.session. Run login.py first.", SESSION_NAME)
        conn.close()
        raise SystemExit(1)

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()
    try:
        commands = await tg.fetch_pending_commands(client)
        for message_id, action, username in commands:
            try:
                await tg.apply_command(client, conn, message_id, action, username)
            except Exception:
                logger.exception("Skipping command /%s @%s after error", action, username)

        folder = await tg.get_or_create_folder(client, FOLDER_NAME)
        async for dialog in client.iter_dialogs():
            try:
                if not await tg.is_eligible_dialog(client, dialog, MAX_GROUP_SIZE):
                    continue
                await process_dialog(client, conn, folder, dialog, now)
            except Exception:
                logger.exception("Skipping dialog %s (%s) after error", dialog.id, dialog.name)
    except Exception:
        logger.exception("Run failed")
        raise SystemExit(1)
    finally:
        await client.disconnect()

    db.set_last_run_at(conn, now)
    conn.close()
    logger.info("Run complete")


if __name__ == "__main__":
    asyncio.run(main())
