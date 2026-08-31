import re
from typing import Optional, Tuple

_COMMAND_PATTERN = re.compile(r"^/(close|family|remove)\s+@?(\w+)$")


def parse_command(text: str) -> Optional[Tuple[str, str]]:
    match = _COMMAND_PATTERN.match(text.strip())
    if not match:
        return None
    action, username = match.groups()
    return action, username
