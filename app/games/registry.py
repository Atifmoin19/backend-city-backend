from app.games.content import GameBody
from app.games.templates.base import HiddenTestGenerator, TemplatedTests
from app.games.templates.bouncer import SignupBoundaries

GENERATORS: dict[str, HiddenTestGenerator] = {
    "signup_boundaries": SignupBoundaries(),
}
_TEMPLATED = TemplatedTests()


def generator_for(game: GameBody) -> HiddenTestGenerator:
    """Code generator named in `hidden_tests.generator`, else the templated test list."""
    name = game.hidden_tests.get("generator")
    if name is None:
        return _TEMPLATED
    try:
        return GENERATORS[str(name)]
    except KeyError as exc:
        raise LookupError(f"No hidden-test generator {name!r}") from exc
