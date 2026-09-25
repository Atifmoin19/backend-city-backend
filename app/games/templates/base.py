from typing import Any, Protocol

from app.games.content import GameBody
from app.games.variants import Variant, render_json


class HiddenTestGenerator(Protocol):
    """Server-only logic that builds a variant's hidden tests. Never shipped."""

    def hidden_tests(self, game: GameBody, variant: Variant) -> list[dict[str, Any]]: ...


class TemplatedTests:
    """Default: `hidden_tests.tests` from the content, with the variant's placeholders filled."""

    def hidden_tests(self, game: GameBody, variant: Variant) -> list[dict[str, Any]]:
        tests: list[dict[str, Any]] = render_json(
            game.hidden_tests.get("tests", []), variant.params
        )
        return tests
