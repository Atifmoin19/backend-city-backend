"""Insert a learner snippet into the starter code between the edit markers."""

import textwrap
from typing import TypedDict


class EditableRegion(TypedDict):
    start_marker: str
    end_marker: str


class SpliceError(ValueError):
    pass


def splice(starter_code: str, snippet: str, region: EditableRegion) -> str:
    lines = starter_code.splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip() == region["start_marker"])
        end = next(i for i, ln in enumerate(lines) if ln.strip() == region["end_marker"])
    except StopIteration as exc:
        raise SpliceError("Edit markers not found in starter code") from exc
    if end <= start:
        raise SpliceError("End marker precedes start marker")
    indent = lines[start][: len(lines[start]) - len(lines[start].lstrip())]
    body = textwrap.indent(textwrap.dedent(snippet).strip("\n"), indent) or f"{indent}pass"
    return "\n".join([*lines[: start + 1], body, *lines[end:]]) + "\n"
