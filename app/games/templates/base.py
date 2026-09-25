from typing import Any, Protocol

from app.games.content import GameContent
from app.games.variants import Variant


class GameTemplate(Protocol):
    """Server-only logic per game type. Hidden tests are generated here, never shipped."""

    def hidden_tests(self, game: GameContent, variant: Variant) -> list[dict[str, Any]]: ...
