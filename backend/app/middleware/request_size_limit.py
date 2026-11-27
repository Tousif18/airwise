"""Inbound request-size protection for AI endpoints."""

import json
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestSizeLimitMiddleware:
    """Reject oversized AI request bodies while buffering at most 64 KB."""

    MAX_BODY_BYTES = 64 * 1024
    PROTECTED_PATHS = {
        "/api/v1/assistant/chat",
        "/api/v1/assistant/recommendations",
        "/api/v1/indoor/recommendations",
    }

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope.get("method", "").upper() != "POST"
            or scope.get("path") not in self.PROTECTED_PATHS
        ):
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        content_length = headers.get(b"content-length")
        if content_length:
            try:
                if int(content_length) > self.MAX_BODY_BYTES:
                    await self._send_too_large(send)
                    return
            except ValueError:
                await self._send_json(
                    send, 400, {"detail": "Invalid Content-Length header."}
                )
                return

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            body.extend(message.get("body", b""))
            if len(body) > self.MAX_BODY_BYTES:
                await self._send_too_large(send)
                return
            if not message.get("more_body", False):
                break

        delivered = False

        async def replay_body() -> Message:
            nonlocal delivered
            if delivered:
                return {"type": "http.request", "body": b"", "more_body": False}
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay_body, send)

    @staticmethod
    async def _send_too_large(send: Send) -> None:
        await RequestSizeLimitMiddleware._send_json(
            send,
            413,
            {
                "detail": "Request body is too large. Maximum size is 64 KB.",
                "error_code": "request_body_too_large",
            },
        )

    @staticmethod
    async def _send_json(send: Send, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
