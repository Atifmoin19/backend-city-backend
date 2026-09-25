"""Read playable games from the DB (games + game_versions) as GameContent."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.games.content import GameBody, GameContent
from app.models.enums import ContentStatus
from app.models.game import GameVersion
from app.repositories.content_repository import ContentRepository, GameRow


def body_of(v: GameVersion) -> GameBody:
    return GameBody(
        title=v.title,
        character=v.character_key,
        visualizer=v.visualizer_type,
        scenario=v.scenario,
        objective=v.objective,
        rules=v.rules,
        variant_params=v.variant_params,
        starter_code=v.starter_code,
        editable_region=v.editable_region,
        public_tests=v.public_tests,
        hidden_tests=v.hidden_test_template,
        reference_solution=v.reference_solution,
        hints=v.hints,
        dialogue=v.dialogue,
    )


def body_columns(body: GameBody) -> dict[str, object]:
    """GameBody -> GameVersion column values (inverse of body_of)."""
    return {
        "title": body.title,
        "character_key": body.character,
        "visualizer_type": body.visualizer,
        "scenario": body.scenario,
        "objective": body.objective,
        "rules": body.rules,
        "variant_params": body.variant_params,
        "starter_code": body.starter_code,
        "editable_region": dict(body.editable_region),
        "public_tests": body.public_tests,
        "hidden_test_template": body.hidden_tests,
        "reference_solution": body.reference_solution,
        "hints": body.hints,
        "dialogue": body.dialogue,
    }


def to_content(row: GameRow) -> GameContent:
    game, version, topic, level = row
    return GameContent(
        **body_of(version).model_dump(),
        game_id=game.id,
        version_id=version.id,
        version=version.version,
        slug=game.slug,
        game_type=game.game_type,
        is_checkpoint=game.is_checkpoint,
        topic_id=topic.id,
        topic_slug=topic.slug,
        district=level.district_key,
        pass_threshold=topic.pass_threshold,
        hints_allowed=topic.hints_allowed,
        retest_cooldown_minutes=topic.retest_cooldown_minutes,
    )


async def published_game(session: AsyncSession, slug: str) -> GameContent | None:
    row = await ContentRepository(session).current_game(slug)
    if row is None or row[0].status != ContentStatus.PUBLISHED:
        return None
    return to_content(row)


async def game_version(session: AsyncSession, version_id: uuid.UUID) -> GameContent | None:
    """Any version, published or not: attempts keep the version they started on."""
    row = await ContentRepository(session).game_version(version_id)
    return to_content(row) if row else None
