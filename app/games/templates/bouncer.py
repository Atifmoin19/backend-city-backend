"""Signup-gate hidden tests: probe every boundary of the variant's rules with random names."""

import random
from typing import Any

from app.games.content import GameBody
from app.games.variants import Variant

_NAME_CHARS = "abcdefghijklmnopqrstuvwxyz_0123456789"


def _signup(name: str, body: dict[str, Any], expect: int) -> dict[str, Any]:
    return {
        "name": name,
        "request": {"method": "POST", "path": "/signup", "json": body},
        "expect_status": expect,
    }


class SignupBoundaries:
    def hidden_tests(self, game: GameBody, variant: Variant) -> list[dict[str, Any]]:
        p = variant.params
        f, a = p["field_name"], p["age_field"]
        lo, hi, nmin, nmax = p["min_age"], p["max_age"], p["name_min"], p["name_max"]
        rng = random.Random(variant.seed ^ 0x5EED)  # noqa: S311

        def name(length: int) -> str:
            return "".join(rng.choice(_NAME_CHARS) for _ in range(length))

        ok_name, ok_age = name((nmin + nmax) // 2), (lo + hi) // 2
        return [
            _signup("age at minimum", {f: ok_name, a: lo}, 201),
            _signup("age just below minimum", {f: ok_name, a: lo - 1}, 422),
            _signup("age at maximum", {f: ok_name, a: hi}, 201),
            _signup("age just above maximum", {f: ok_name, a: hi + 1}, 422),
            _signup("negative age", {f: ok_name, a: -rng.randint(1, 50)}, 422),
            _signup("name at min length", {f: name(nmin), a: ok_age}, 201),
            _signup("name below min length", {f: name(nmin - 1), a: ok_age}, 422),
            _signup("name at max length", {f: name(nmax), a: ok_age}, 201),
            _signup("name above max length", {f: name(nmax + 1), a: ok_age}, 422),
            _signup("missing age", {f: ok_name}, 422),
            _signup("age not a number", {f: ok_name, a: "old"}, 422),
            _signup(
                "random recruit", {f: name(rng.randint(nmin, nmax)), a: rng.randint(lo, hi)}, 201
            ),
        ]
