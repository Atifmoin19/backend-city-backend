"""Sync content/seed/ (curriculum.json + games/*.json) into the DB.

Run on every deploy (`python -m app.games.seed`) and by the test suite. Idempotent:
  * tracks, levels, chapters, topics and games are created when missing, never overwritten
    (the admin API owns them afterwards);
  * a game whose current version came from the seed (created_by is NULL) gets a new version
    when its seed file changes; a version published by an admin is left alone.
"""

import asyncio
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.games.catalog import body_columns, body_of
from app.games.content import GameBody, SeedGame, curriculum, seed_games
from app.models.chapter import Chapter
from app.models.enums import ContentStatus
from app.models.game import Game, GameVersion
from app.models.level import Level
from app.models.topic import Topic
from app.models.track import Track
from app.repositories.content_repository import ContentRepository

PUBLISHED = ContentStatus.PUBLISHED


@dataclass
class SyncReport:
    created: list[str] = field(default_factory=list)
    new_versions: list[str] = field(default_factory=list)


async def sync(session: AsyncSession) -> SyncReport:
    repo = ContentRepository(session)
    report = SyncReport()
    cur = curriculum()
    games = seed_games()

    track = await repo.track_by_slug(cur.track_slug)
    if track is None:
        track = Track(slug=cur.track_slug, title=cur.track_title, status=PUBLISHED)
        session.add(track)
        await session.flush()
        report.created.append(f"track:{track.slug}")

    for li, lv in enumerate(cur.levels):
        level = await repo.level(track.id, lv.slug)
        if level is None:
            level = Level(
                track_id=track.id,
                slug=lv.slug,
                title=lv.title,
                district_key=lv.district_key,
                story_intro=lv.story_intro,
                order=li,
                status=PUBLISHED,
            )
            session.add(level)
            await session.flush()
            report.created.append(f"level:{lv.slug}")
        for ci, ch in enumerate(lv.chapters):
            chapter = await repo.chapter(level.id, ch.slug)
            if chapter is None:
                chapter = Chapter(
                    level_id=level.id, slug=ch.slug, title=ch.title, order=ci, status=PUBLISHED
                )
                session.add(chapter)
                await session.flush()
                report.created.append(f"chapter:{ch.slug}")
            for ti, tp in enumerate(ch.topics):
                topic = await repo.topic_by_slug(tp.slug)
                if topic is None:
                    topic = Topic(
                        chapter_id=chapter.id,
                        slug=tp.slug,
                        title=tp.title,
                        order=ti,
                        status=PUBLISHED,
                        pass_threshold=tp.pass_threshold,
                        required_games_count=len(tp.practice),
                        retest_cooldown_minutes=tp.retest_cooldown_minutes,
                    )
                    session.add(topic)
                    await session.flush()
                    report.created.append(f"topic:{tp.slug}")
                placed = [(s, False) for s in tp.practice]
                if tp.checkpoint:
                    placed.append((tp.checkpoint, True))
                for order, (slug, is_checkpoint) in enumerate(placed):
                    if slug not in games:
                        raise LookupError(f"curriculum names game {slug!r} with no seed file")
                    await _sync_game(repo, report, topic, games[slug], order, is_checkpoint)

    await session.commit()
    return report


async def _sync_game(
    repo: ContentRepository,
    report: SyncReport,
    topic: Topic,
    seed: SeedGame,
    order: int,
    is_checkpoint: bool,
) -> None:
    session = repo.session
    body = GameBody.model_validate(seed.model_dump())
    game = await repo.game_by_slug(seed.slug)
    if game is None:
        game = Game(
            slug=seed.slug,
            topic_id=topic.id,
            game_type=seed.game_type,
            is_checkpoint=is_checkpoint,
            order=order,
            status=PUBLISHED,
        )
        session.add(game)
        await session.flush()
        await _add_version(repo, game, body, 1)
        report.created.append(f"game:{seed.slug}")
        return

    current = (
        await session.get(GameVersion, game.current_version_id) if game.current_version_id else None
    )
    if current is not None and current.created_by is not None:
        return  # an admin owns this game now
    if current is not None and body_of(current) == body:
        return
    await _add_version(repo, game, body, await repo.next_version_number(game.id))
    report.new_versions.append(seed.slug)


async def _add_version(repo: ContentRepository, game: Game, body: GameBody, number: int) -> None:
    version = GameVersion(game_id=game.id, version=number, **body_columns(body))
    repo.session.add(version)
    await repo.session.flush()
    game.current_version_id = version.id


async def _main() -> None:
    from app.db.session import SessionFactory, engine

    async with SessionFactory() as session:
        report = await sync(session)
    await engine.dispose()
    print(f"[seed] created {len(report.created)}, new versions: {report.new_versions or 'none'}")


if __name__ == "__main__":
    asyncio.run(_main())
