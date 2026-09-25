"""Minimal in-process ASGI client: no sockets, no event-loop threads (works in Pyodide)."""

import json
from typing import Any, TypedDict

from starlette.types import ASGIApp, Message


class SimRequest(TypedDict, total=False):
    method: str
    path: str
    json: Any
    query: str
    headers: dict[str, str]


class SimResponse(TypedDict):
    status: int
    body: Any


async def call(app: ASGIApp, req: SimRequest) -> SimResponse:
    payload = b"" if "json" not in req else json.dumps(req["json"]).encode()
    headers = [(k.lower().encode(), v.encode()) for k, v in req.get("headers", {}).items()]
    if payload:
        headers.append((b"content-type", b"application/json"))
    path = req.get("path", "/")
    scope: dict[str, Any] = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": req.get("method", "GET").upper(),
        "path": path,
        "raw_path": path.encode(),
        "query_string": req.get("query", "").encode(),
        "headers": headers,
        "scheme": "http",
        "server": ("backend-city", 80),
        "client": ("packet", 1),
        "root_path": "",
    }
    sent = False
    messages: list[Message] = []

    async def receive() -> Message:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": payload, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        messages.append(message)

    await app(scope, receive, send)
    status = next(int(m["status"]) for m in messages if m["type"] == "http.response.start")
    raw = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    try:
        body: Any = json.loads(raw) if raw else None
    except ValueError:
        body = raw.decode(errors="replace")
    return {"status": status, "body": body}
