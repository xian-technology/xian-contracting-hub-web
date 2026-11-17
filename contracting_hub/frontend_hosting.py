"""Document fallback for declared database-backed pages in single-port hosting."""

import re
from collections.abc import Iterable

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from contracting_hub.services.auth import USERNAME_PATTERN
from contracting_hub.services.contract_metadata import CONTRACT_SLUG_PATTERN


def _dynamic_patterns(routes: Iterable[str]) -> tuple[re.Pattern[str], ...]:
    slug = CONTRACT_SLUG_PATTERN.pattern.removeprefix("^").removesuffix("$")
    username = USERNAME_PATTERN.pattern.removeprefix("^").removesuffix("$")
    return tuple(
        re.compile(
            re.escape(route)
            .replace(r"\[slug\]", f"(?:{slug})")
            .replace(r"\[username\]", f"(?:{username})")
            + "/?"
        )
        for route in routes
        if "[" in route
    )


def _positive_quality(parameters: list[str]) -> bool:
    for parameter in parameters:
        name, _, value = parameter.strip().partition("=")
        if name == "q":
            try:
                return 0 < float(value) <= 1
            except ValueError:
                return False
    return True


def _accepts_html(scope: Scope) -> bool:
    values = Headers(scope=scope).getlist("accept")
    if not values:
        return True
    accept = ",".join(values)
    qualities = {}
    for entry in accept.lower().split(","):
        media_type, *parameters = entry.split(";")
        media_type = media_type.strip()
        if media_type in {"text/html", "text/*", "*/*"}:
            qualities[media_type] = _positive_quality(parameters)
    return next(
        (qualities[media] for media in ("text/html", "text/*", "*/*") if media in qualities),
        False,
    )


def _vary_accept(headers: MutableHeaders) -> None:
    values = headers.getlist("vary")
    existing = {part.strip().lower() for value in values for part in value.split(",")}
    if "*" not in existing and "accept" not in existing:
        headers["vary"] = ", ".join([*values, "Accept"])


class DynamicPageFallback:
    """Keep the compiled router's HTML body and correct only document status."""

    def __init__(self, app: ASGIApp, *, routes: Iterable[str]):
        self.app = app
        self.patterns = _dynamic_patterns(routes)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] not in {"GET", "HEAD"}
            or not any(pattern.fullmatch(scope["path"]) for pattern in self.patterns)
        ):
            await self.app(scope, receive, send)
            return

        accepts_html = _accepts_html(scope)

        async def send_document(message: Message) -> None:
            if message["type"] == "http.response.start":
                message = {**message, "headers": list(message.get("headers", []))}
                headers = MutableHeaders(scope=message)
                _vary_accept(headers)
                media_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
                if message["status"] == 404 and media_type == "text/html" and accepts_html:
                    message["status"] = 200
            await send(message)

        await self.app(scope, receive, send_document)
