"""Game content schemas.

`GameContent` is one playable game version, assembled from the DB (games + game_versions +
the topic/level it belongs to). It includes SERVER-ONLY fields (reference_solution,
hidden_tests). Never return it directly; use app.schemas.games.GameVariantPublic.

`SeedGame` / `Curriculum` are the files under content/seed/ that app.games.seed syncs into
the DB. After the first sync the DB (edited through the admin API) is the source of truth.
"""

import json
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from harness.splice import EditableRegion

SEED_DIR = Path(__file__).resolve().parents[2] / "content" / "seed"


class GameBody(BaseModel):
    """Everything a game version stores. Shared by seed files, the DB and the admin API."""

    title: str = Field(min_length=1, max_length=120)
    character: str = Field(min_length=1, max_length=40)
    visualizer: str = Field(min_length=1, max_length=40)
    scenario: dict[str, str]
    objective: str = ""  # one sentence: what winning looks like
    rules: list[str] = []  # the exact requirements, one per line (templated)
    variant_params: dict[str, list[Any]] = {}
    starter_code: str
    editable_region: EditableRegion
    public_tests: list[dict[str, Any]]
    # {"generator": "<name>"} for code-generated tests, or {"tests": [...templated tests]}
    hidden_tests: dict[str, Any] = {}
    reference_solution: str
    hints: list[dict[str, Any]] = []
    dialogue: dict[str, str] = {}


class SeedGame(GameBody):
    slug: str
    game_type: str


class GameContent(GameBody):
    """A published (or explicitly requested) game version, ready to render and grade."""

    game_id: uuid.UUID
    version_id: uuid.UUID
    version: int
    slug: str
    game_type: str
    is_checkpoint: bool
    topic_id: uuid.UUID
    topic_slug: str
    district: str
    pass_threshold: int
    hints_allowed: bool = True
    retest_cooldown_minutes: int = 0


class SeedTopic(BaseModel):
    slug: str
    title: str
    pass_threshold: int = 70
    retest_cooldown_minutes: int = 0
    practice: list[str] = []  # game slugs, in play order
    checkpoint: str | None = None


class SeedChapter(BaseModel):
    slug: str
    title: str
    topics: list[SeedTopic]


class SeedLevel(BaseModel):
    slug: str
    title: str
    district_key: str
    story_intro: str = ""
    chapters: list[SeedChapter]


class Curriculum(BaseModel):
    track_slug: str
    track_title: str
    levels: list[SeedLevel]


@lru_cache
def seed_games() -> dict[str, SeedGame]:
    paths = sorted((SEED_DIR / "games").glob("*.json"))
    games = [SeedGame.model_validate(json.loads(p.read_text())) for p in paths]
    return {g.slug: g for g in games}


@lru_cache
def curriculum() -> Curriculum:
    return Curriculum.model_validate(json.loads((SEED_DIR / "curriculum.json").read_text()))
