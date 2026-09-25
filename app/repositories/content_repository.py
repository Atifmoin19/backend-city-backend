import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chapter import Chapter
from app.models.game import Game, GameVersion
from app.models.level import Level
from app.models.topic import Topic
from app.models.track import Track
from app.models.user import User

GameRow = tuple[Game, GameVersion, Topic, Level]


class ContentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _game_rows(self) -> Select[Game, GameVersion, Topic, Level]:
        return (
            select(Game, GameVersion, Topic, Level)
            .join(Topic, Topic.id == Game.topic_id)
            .join(Chapter, Chapter.id == Topic.chapter_id)
            .join(Level, Level.id == Chapter.level_id)
        )

    async def current_game(self, slug: str) -> GameRow | None:
        """A game with its current (published) version and placement."""
        stmt = self._game_rows().join(GameVersion, GameVersion.id == Game.current_version_id)
        row = (await self.session.execute(stmt.where(Game.slug == slug))).first()
        return row

    async def game_version(self, version_id: uuid.UUID) -> GameRow | None:
        stmt = self._game_rows().join(GameVersion, GameVersion.game_id == Game.id)
        row = await self.session.execute(stmt.where(GameVersion.id == version_id))
        return row.first()

    async def game_by_slug(self, slug: str) -> Game | None:
        result = await self.session.execute(select(Game).where(Game.slug == slug))
        return result.scalar_one_or_none()

    async def versions(self, game_id: uuid.UUID) -> list[GameVersion]:
        result = await self.session.execute(
            select(GameVersion)
            .where(GameVersion.game_id == game_id)
            .order_by(GameVersion.version.desc())
        )
        return list(result.scalars())

    async def next_version_number(self, game_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.coalesce(func.max(GameVersion.version), 0)).where(
                GameVersion.game_id == game_id
            )
        )
        return int(result.scalar_one()) + 1

    async def topic_by_slug(self, slug: str) -> Topic | None:
        result = await self.session.execute(select(Topic).where(Topic.slug == slug))
        return result.scalars().first()

    async def topics_with_games(
        self, track_slug: str | None = None
    ) -> list[tuple[Topic, str, list[Game]]]:
        """Every topic with its track slug and games in play order (progress and admin).

        Tracks are separate "cities" (Python backend today; others later) sharing one API.
        """
        stmt = (
            select(Topic, Track.slug)
            .join(Chapter, Chapter.id == Topic.chapter_id)
            .join(Level, Level.id == Chapter.level_id)
            .join(Track, Track.id == Level.track_id)
            .order_by(Track.order, Level.order, Chapter.order, Topic.order)
        )
        if track_slug is not None:
            stmt = stmt.where(Track.slug == track_slug)
        topics = list(await self.session.execute(stmt))
        games = list(
            (await self.session.execute(select(Game).order_by(Game.order, Game.slug))).scalars()
        )
        by_topic: dict[uuid.UUID, list[Game]] = {}
        for g in games:
            by_topic.setdefault(g.topic_id, []).append(g)
        return [(t, track, by_topic.get(t.id, [])) for t, track in topics]

    async def all_games(self) -> list[tuple[Game, Topic, Level]]:
        stmt = (
            select(Game, Topic, Level)
            .join(Topic, Topic.id == Game.topic_id)
            .join(Chapter, Chapter.id == Topic.chapter_id)
            .join(Level, Level.id == Chapter.level_id)
            .order_by(Level.order, Topic.order, Game.order)
        )
        return list(await self.session.execute(stmt))

    async def levels_with_topics(self) -> list[tuple[Level, Topic]]:
        stmt = (
            select(Level, Topic)
            .join(Chapter, Chapter.level_id == Level.id)
            .join(Topic, Topic.chapter_id == Chapter.id)
            .order_by(Level.order, Chapter.order, Topic.order)
        )
        return [(lv, tp) for lv, tp in await self.session.execute(stmt)]

    async def latest_versions(self) -> dict[uuid.UUID, int]:
        stmt = select(GameVersion.game_id, func.max(GameVersion.version)).group_by(
            GameVersion.game_id
        )
        return {game_id: int(n) for game_id, n in await self.session.execute(stmt)}

    async def version_numbers_by_id(self) -> dict[uuid.UUID, int]:
        stmt = select(GameVersion.id, GameVersion.version)
        return {vid: n for vid, n in await self.session.execute(stmt)}

    async def version_by_number(self, game_id: uuid.UUID, number: int) -> GameVersion | None:
        result = await self.session.execute(
            select(GameVersion).where(GameVersion.game_id == game_id, GameVersion.version == number)
        )
        return result.scalar_one_or_none()

    async def version_history(self, game_id: uuid.UUID) -> list[tuple[GameVersion, str | None]]:
        """Versions newest first, each with the email of the admin who saved it."""
        stmt = (
            select(GameVersion, User.email)
            .outerjoin(User, User.id == GameVersion.created_by)
            .where(GameVersion.game_id == game_id)
            .order_by(GameVersion.version.desc())
        )
        return [(v, email) for v, email in await self.session.execute(stmt)]

    # --- structure (seed sync) ---

    async def track_by_slug(self, slug: str) -> Track | None:
        result = await self.session.execute(select(Track).where(Track.slug == slug))
        return result.scalar_one_or_none()

    async def level(self, track_id: uuid.UUID, slug: str) -> Level | None:
        result = await self.session.execute(
            select(Level).where(Level.track_id == track_id, Level.slug == slug)
        )
        return result.scalar_one_or_none()

    async def chapter(self, level_id: uuid.UUID, slug: str) -> Chapter | None:
        result = await self.session.execute(
            select(Chapter).where(Chapter.level_id == level_id, Chapter.slug == slug)
        )
        return result.scalar_one_or_none()
