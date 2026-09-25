"""Seeded variant rendering: picks params and fills {{placeholders}} everywhere."""

import json
import random
from dataclasses import dataclass
from typing import Any

from app.games.content import GameContent

MAX_SEED = 2**31 - 1


@dataclass(frozen=True)
class Variant:
    seed: int
    params: dict[str, Any]


def pick_params(game: GameContent, seed: int) -> Variant:
    rng = random.Random(seed)  # noqa: S311 — gameplay variety, not cryptography
    params = {key: rng.choice(options) for key, options in sorted(game.variant_params.items())}
    return Variant(seed=seed, params=params)


def render(template: str, params: dict[str, Any]) -> str:
    for key, value in params.items():
        template = template.replace("{{" + key + "}}", str(value))
    return template


def render_json(obj: Any, params: dict[str, Any]) -> Any:
    """Render placeholders inside keys and string values; exact-placeholder values keep type."""
    return json.loads(render(json.dumps(obj), params))


def new_seed() -> int:
    return random.SystemRandom().randint(1, MAX_SEED)
