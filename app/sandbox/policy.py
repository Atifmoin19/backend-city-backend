"""Static checks on a learner snippet BEFORE it is executed (first line of defense).

Allowlist approach: only listed modules may be imported; dunder attribute access and
dangerous builtins are rejected outright. Runtime defenses live in entry.py / executor.py.
"""

import ast
import textwrap
from dataclasses import dataclass

ALLOWED_IMPORTS: frozenset[str] = frozenset(
    {
        "fastapi",
        "pydantic",
        "typing",
        "typing_extensions",
        "annotated_types",
        "datetime",
        "decimal",
        "enum",
        "re",
        "uuid",
        "math",
        "dataclasses",
    }
)

BLOCKED_NAMES: frozenset[str] = frozenset(
    {
        "__import__",
        "eval",
        "exec",
        "compile",
        "open",
        "input",
        "breakpoint",
        "globals",
        "locals",
        "vars",
        "getattr",
        "setattr",
        "delattr",
        "memoryview",
        "__builtins__",
    }
)


@dataclass(frozen=True)
class PolicyViolation:
    line: int
    message: str


def check_snippet(snippet: str, *, max_chars: int) -> list[PolicyViolation]:
    if len(snippet) > max_chars:
        return [PolicyViolation(0, f"Snippet too long ({len(snippet)} > {max_chars} characters)")]
    try:
        # Editors send the region with its class-body indentation; splice() dedents the same way
        tree = ast.parse(textwrap.dedent(snippet))
    except SyntaxError as exc:
        return [PolicyViolation(exc.lineno or 0, f"Syntax error: {exc.msg}")]

    violations: list[PolicyViolation] = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in ALLOWED_IMPORTS:
                    violations.append(PolicyViolation(line, f"Import not allowed: {alias.name}"))
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if node.level or root not in ALLOWED_IMPORTS:
                violations.append(PolicyViolation(line, f"Import not allowed: {node.module}"))
        elif isinstance(node, ast.Name) and node.id in BLOCKED_NAMES:
            violations.append(PolicyViolation(line, f"Use of `{node.id}` is not allowed"))
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            violations.append(PolicyViolation(line, f"Dunder attribute `{node.attr}` not allowed"))
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            violations.append(PolicyViolation(line, "global/nonlocal not allowed"))
    return violations
