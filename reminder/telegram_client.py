import logging

from telethon.tl import functions, types

from reminder import db
from reminder.commands import parse_command
from reminder.logic import Message

logger = logging.getLogger(__name__)


def _filter_title(f) -> str:
    """DialogFilter.title is a TextWithEntities (not a plain str) as of the
    installed Telethon/TL layer, so unwrap it before comparing."""
    title = getattr(f, "title", None)
    return getattr(title, "text", title)


async def get_or_create_folder(client, folder_title: str):
    result = await client(functions.messages.GetDialogFiltersRequest())
    filters = getattr(result, "filters", result)
    for f in filters:
        if _filter_title(f) == folder_title:
            return f
    existing_ids = [f.id for f in filters if hasattr(f, "id")]
    new_id = max(existing_ids, default=1) + 1
    new_filter = types.DialogFilter(
        id=new_id,
        title=types.TextWithEntities(text=folder_title, entities=[]),
        pinned_peers=[],
        include_peers=[],
        exclude_peers=[],
    )
    await client(
        functions.messages.UpdateDialogFilterRequest(id=new_id, filter=new_filter)
    )
    return new_filter


def _peer_key(peer):
    return getattr(
        peer, "user_id", getattr(peer, "channel_id", getattr(peer, "chat_id", None))
    )


async def add_peer_to_folder(client, folder, entity) -> None:
    input_peer = await client.get_input_entity(entity)
    if not any(_peer_key(p) == _peer_key(input_peer) for p in folder.include_peers):
        folder.include_peers.append(input_peer)
        await client(
            functions.messages.UpdateDialogFilterRequest(id=folder.id, filter=folder)
        )


async def remove_peer_from_folder(client, folder, entity) -> None:
    input_peer = await client.get_input_entity(entity)
    before = len(folder.include_peers)
    folder.include_peers = [
        p for p in folder.include_peers if _peer_key(p) != _peer_key(input_peer)
    ]
    if len(folder.include_peers) != before:
        await client(
            functions.messages.UpdateDialogFilterRequest(id=folder.id, filter=folder)
        )


async def fetch_unreplied_batch(client, dialog, limit: int = 20) -> list:
    messages = []
    async for msg in client.iter_messages(dialog.entity, limit=limit):
        if msg.out:
            break
        messages.append(
            Message(
                id=msg.id,
                from_me=bool(msg.out),
                date=msg.date,
                text=msg.message or "",
                is_sticker=msg.sticker is not None,
                is_gif=msg.gif is not None,
            )
        )
    return messages


async def my_reaction_on_last(client, dialog, batch) -> bool:
    if not batch:
        return False
    last = batch[0]
    fetched = await client.get_messages(dialog.entity, ids=last.id)
    if not fetched or not fetched.reactions:
        return False
    return any(r.my for r in fetched.reactions.recent_reactions or [])


async def get_participant_count(client, entity) -> int:
    if isinstance(entity, types.ChatForbidden):
        return -1
    if isinstance(entity, types.Chat):
        return entity.participants_count
    if isinstance(entity, types.Channel):
        full = await client(functions.channels.GetFullChannelRequest(entity))
        return full.full_chat.participants_count
    return 0


async def is_eligible_dialog(client, dialog, max_group_size: int) -> bool:
    if dialog.is_user:
        return True
    if dialog.is_group:
        count = await get_participant_count(client, dialog.entity)
        return 0 <= count < max_group_size
    return False


async def fetch_pending_commands(client) -> list:
    """Returns (message_id, action, username) for command-shaped text
    messages in Saved Messages ("me")."""
    commands = []
    async for msg in client.iter_messages("me"):
        if not msg.message:
            continue
        parsed = parse_command(msg.message)
        if parsed:
            action, username = parsed
            commands.append((msg.id, action, username))
    return commands


async def apply_command(client, conn, message_id: int, action: str, username: str) -> None:
    try:
        entity = await client.get_entity(username)
    except (ValueError, TypeError):
        logger.warning(
            "Could not resolve @%s for command %s, leaving message in place",
            username,
            action,
        )
        return

    if action == "remove":
        db.clear_tier(conn, entity.id)
    else:
        db.set_tier(conn, entity.id, action)

    await client.delete_messages("me", message_id)
    logger.info("Applied /%s @%s (chat_id=%s)", action, username, entity.id)
