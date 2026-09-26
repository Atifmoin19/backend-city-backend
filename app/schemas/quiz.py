from pydantic import BaseModel, Field, model_validator

SLUG = r"^[a-z0-9][a-z0-9-]{0,79}$"


class QuizResultIn(BaseModel):
    quiz: str = Field(pattern=SLUG)
    score: int = Field(ge=0, le=100)
    total: int = Field(ge=1, le=100)
    best_combo: int = Field(default=0, ge=0, le=100)
    seconds: int | None = Field(default=None, ge=0, le=3600)

    @model_validator(mode="after")
    def _within_total(self) -> "QuizResultIn":
        if self.score > self.total or self.best_combo > self.total:
            raise ValueError("score and best_combo can't exceed total")
        return self


class QuizBest(BaseModel):
    quiz: str
    best_score: int
    total: int  # of the best round
    best_combo: int
    plays: int


class QuizResults(BaseModel):
    results: list[QuizBest]


class PlacementIn(BaseModel):
    start_district: str = Field(pattern=SLUG)
