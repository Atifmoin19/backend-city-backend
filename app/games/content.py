"""Game content schema + file-based loader (Phase 0). Later this reads game_versions from the DB.

GameContent includes SERVER-ONLY fields (reference_solution). Never return it directly;
use app.schemas.games.GameVariantPublic.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from harness.splice import EditableRegion

SEED_DIR = Path(__file__).resolve().parents[2] / "content" / "seed" / "games"


class GameContent(BaseModel):
    slug: str
    game_type: str
    title: str
    district: str
    character: str
    visualizer: str
    is_checkpoint: bool
    pass_threshold: int
    scenario: dict[str, str]
    objective: str = ""  # one sentence: what winning looks like
    rules: list[str] = []  # the exact requirements, one per line (templated)
    variant_params: dict[str, list[Any]]
    starter_code: str
    editable_region: EditableRegion
    public_tests: list[dict[str, Any]]
    reference_solution: str
    hints: list[dict[str, Any]]
    dialogue: dict[str, str]


@lru_cache
def load_all() -> dict[str, GameContent]:
    games = [GameContent.model_validate(json.loads(p.read_text())) for p in SEED_DIR.glob("*.json")]
    return {g.slug: g for g in games}


def get_game(slug: str) -> GameContent | None:
    return load_all().get(slug)
