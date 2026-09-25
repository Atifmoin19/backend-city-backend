"""Seeded variant rendering: picks params and fills {{placeholders}} everywhere."""

import random
from dataclasses import dataclass
from typing import Any

from app.games.content import GameBody

MAX_SEED = 2**31 - 1


@dataclass(frozen=True)
class Variant:
    seed: int
    params: dict[str, Any]


def pick_params(game: GameBody, seed: int) -> Variant:
    rng = random.Random(seed)  # noqa: S311 — gameplay variety, not cryptography
    params = {key: rng.choice(options) for key, options in sorted(game.variant_params.items())}
    return Variant(seed=seed, params=params)


def render(template: str, params: dict[str, Any]) -> str:
    for key, value in params.items():
        template = template.replace("{{" + key + "}}", str(value))
    return template


def render_json(obj: Any, params: dict[str, Any]) -> Any:
    """Render placeholders inside keys and string values. A value that is exactly one
    placeholder (e.g. "{{min_age}}") takes the param's own type, so numbers stay numbers."""
    if isinstance(obj, dict):
        return {render(str(k), params): render_json(v, params) for k, v in obj.items()}
    if isinstance(obj, list):
        return [render_json(v, params) for v in obj]
    if isinstance(obj, str):
        if obj.startswith("{{") and obj.endswith("}}") and obj[2:-2] in params:
            return params[obj[2:-2]]
        return render(obj, params)
    return obj


def new_seed() -> int:
    return random.SystemRandom().randint(1, MAX_SEED)
