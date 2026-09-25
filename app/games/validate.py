"""Static checks on game content before an admin can save or publish it."""

import json
import re

from app.games.content import GameBody
from app.games.registry import GENERATORS

_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def _test_issues(label: str, tests: object) -> list[str]:
    if not isinstance(tests, list):
        return [f"{label} must be a list"]
    issues = []
    names: set[str] = set()
    for i, t in enumerate(tests, 1):
        req = t.get("request") if isinstance(t, dict) else None
        if not isinstance(t, dict) or not isinstance(req, dict):
            issues.append(f"{label} #{i}: needs a `request` object")
            continue
        if not isinstance(t.get("name"), str) or not t["name"]:
            issues.append(f"{label} #{i}: needs a `name`")
        elif t["name"] in names:
            issues.append(f"{label} #{i}: duplicate name {t['name']!r}")
        else:
            names.add(t["name"])
        if not isinstance(req.get("method"), str) or not isinstance(req.get("path"), str):
            issues.append(f"{label} #{i}: request needs `method` and `path`")
        if not isinstance(t.get("expect_status"), int):
            issues.append(f"{label} #{i}: `expect_status` must be a number")
    return issues


def content_issues(body: GameBody, *, is_checkpoint: bool) -> list[str]:
    """Problems that make a version unplayable. Empty = structurally fine."""
    issues: list[str] = []
    lines = [ln.strip() for ln in body.starter_code.splitlines()]
    start, end = body.editable_region["start_marker"], body.editable_region["end_marker"]
    if start not in lines or end not in lines:
        issues.append("starter_code must contain both edit markers on their own lines")
    elif lines.index(end) <= lines.index(start):
        issues.append("the end marker must come after the start marker")
    if "app = FastAPI(" not in body.starter_code:
        issues.append("starter_code must define `app = FastAPI()`")

    issues += _test_issues("public test", body.public_tests)
    if not body.public_tests:
        issues.append("add at least one public test")
    generator = body.hidden_tests.get("generator")
    if generator is not None and generator not in GENERATORS:
        issues.append(f"unknown hidden-test generator {generator!r}")
    elif generator is None:
        hidden = body.hidden_tests.get("tests", [])
        issues += _test_issues("hidden test", hidden)
        if is_checkpoint and not hidden:
            issues.append("a checkpoint needs hidden tests")

    tiers = [h.get("tier") for h in body.hints]
    if any(not isinstance(t, int) or not 1 <= t <= 3 for t in tiers) or len(set(tiers)) != len(
        tiers
    ):
        issues.append("hint tiers must be unique numbers from 1 to 3")
    if any(not isinstance(h.get("text"), str) or not h["text"] for h in body.hints):
        issues.append("every hint needs `text`")

    everything = json.dumps(body.model_dump(exclude={"variant_params"}))
    unknown = sorted(set(_PLACEHOLDER.findall(everything)) - set(body.variant_params))
    if unknown:
        issues.append(f"placeholders without variant_params: {', '.join(unknown)}")
    if any(not isinstance(v, list) or not v for v in body.variant_params.values()):
        issues.append("every variant_params entry must be a non-empty list of options")
    return issues
