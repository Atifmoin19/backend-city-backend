"""Learner-facing game schemas. SECURITY: no hidden tests, no reference solution here."""

from typing import Any

from pydantic import BaseModel, Field


class PublicTest(BaseModel):
    name: str
    request: dict[str, Any]
    expect_status: int


class Hint(BaseModel):
    tier: int
    text: str


class GameVariantPublic(BaseModel):
    slug: str
    game_type: str
    title: str
    district: str
    character: str
    visualizer: str
    is_checkpoint: bool
    pass_threshold: int
    scenario: dict[str, str]
    objective: str
    rules: list[str]
    starter_code: str
    editable_region: dict[str, str]
    public_tests: list[PublicTest]
    hint_tiers: list[int]  # text is fetched on demand via /hint so each use can be counted
    dialogue: dict[str, str]
    seed: int
    attempt_token: str
    harness_version: str


class HintRequest(BaseModel):
    attempt_token: str = Field(min_length=10, max_length=2000)
    tier: int = Field(ge=1, le=3)


class GradeRequest(BaseModel):
    attempt_token: str = Field(min_length=10, max_length=2000)
    snippet: str = Field(max_length=20_000)  # hard cap; policy enforces the real limit


class TestOutcome(BaseModel):
    name: str
    expect_status: int
    status: int
    passed: bool


class Violation(BaseModel):
    line: int
    message: str


class GradeResponse(BaseModel):
    verdict: str  # "graded" | "rejected" | "load_error" | "timeout" | "crashed"
    score: int
    passed: bool
    stars: int
    pass_threshold: int
    public_results: list[TestOutcome] = []
    hidden_passed: int = 0
    hidden_total: int = 0
    violations: list[Violation] = []
    error: str | None = None
