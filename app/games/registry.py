from app.games.templates.base import GameTemplate
from app.games.templates.bouncer import BouncerTemplate

TEMPLATES: dict[str, GameTemplate] = {
    "bouncer": BouncerTemplate(),
}


def template_for(game_type: str) -> GameTemplate:
    try:
        return TEMPLATES[game_type]
    except KeyError as exc:
        raise LookupError(f"No template for game type {game_type!r}") from exc
