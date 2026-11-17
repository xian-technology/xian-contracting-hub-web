"""HTTP document status for the app's real single-port production transformer."""

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.testclient import TestClient

from contracting_hub.app import app


@pytest.fixture
def client(tmp_path):
    (tmp_path / "index.html").write_text("<h1>Prerendered home</h1>")
    (tmp_path / "404.html").write_text("<html>Compiled client router</html>")
    (tmp_path / "existing.css").write_text("body { color: green }")

    async def api_error(request):
        return JSONResponse({"error": "missing"}, status_code=404)

    async def cached_error(request):
        response = Response(
            "<html>Compiled client router</html>",
            status_code=404,
            media_type="text/html",
            headers={
                "Vary": request.query_params.get("vary", "Accept-Encoding"),
                "Cache-Control": "max-age=60",
            },
        )
        if request.query_params.get("second_vary"):
            response.raw_headers.append((b"vary", request.query_params["second_vary"].encode()))
        return response

    async def socket(websocket):
        await websocket.accept()
        await websocket.send_text("delegated")
        await websocket.close()

    server = Starlette(
        routes=[
            Route("/contracts/api-error", api_error),
            Route("/contracts/cached-error", cached_error),
            WebSocketRoute("/_event", socket),
            Mount("/", StaticFiles(directory=tmp_path, html=True)),
        ]
    )
    if app.api_transformer is not None:
        server = app.api_transformer(server)
    with TestClient(server) as test_client:
        yield test_client


@pytest.mark.parametrize(
    "path",
    [
        "/contracts/staking?version=0.3.0",
        "/contracts/escrow-tools/",
        "/developers/alice_validator",
        "/admin/contracts/staking/edit",
        "/admin/contracts/staking/versions",
        "/admin/contracts/staking/relations",
    ],
)
def test_declared_dynamic_html_documents_return_200_with_unmodified_shell(client, path):
    response = client.get(path, headers={"Accept": "text/html"})
    assert response.status_code == 200
    assert response.text == "<html>Compiled client router</html>"
    assert response.headers["content-length"] == str(len(response.content))
    assert "accept" in response.headers["vary"].lower()


@pytest.mark.parametrize("accept", ["application/json", "", "text/html;q=0"])
def test_non_document_negotiation_keeps_html_404_and_varies_cache(client, accept):
    response = client.get("/contracts/staking", headers={"Accept": accept})
    assert response.status_code == 404
    assert "accept" in response.headers["vary"].lower()


@pytest.mark.parametrize(
    "accept",
    [
        "application/json, text/html;q=0.8",
        "Text/Html; charset=utf-8",
        "text/html;q=1",
        "*/*",
        "text/*",
    ],
)
def test_positive_html_negotiation_is_supported(client, accept):
    assert client.get("/contracts/staking", headers={"Accept": accept}).status_code == 200


def test_curl_style_request_without_accept_is_an_html_document(client):
    del client.headers["accept"]
    response = client.get("/contracts/staking")
    assert response.status_code == 200
    assert response.text == "<html>Compiled client router</html>"


@pytest.mark.parametrize("accept", ["text/html;q=0, */*", "text/*;q=0, */*"])
def test_specific_html_refusal_overrides_less_specific_wildcard(client, accept):
    assert client.get("/contracts/staking", headers={"Accept": accept}).status_code == 404


@pytest.mark.parametrize("quality", ["invalid", "NaN", "inf", "-1", "1.1"])
def test_invalid_html_quality_does_not_promote_a_404(client, quality):
    response = client.get("/contracts/staking", headers={"Accept": f"text/html;q={quality}"})
    assert response.status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "/missing-public-route",
        "/assets/missing.js",
        "/contracts/missing.js",
        "/developers/alice.css",
        "/contracts/%2e%2e/secrets",
        "/contracts/staking/extra",
    ],
)
def test_unknown_routes_assets_and_traversal_are_not_successful_documents(client, path):
    assert client.get(path, headers={"Accept": "text/html"}).status_code == 404


@pytest.mark.parametrize("method", ["post", "put", "delete", "patch"])
def test_non_read_methods_retain_method_not_allowed(client, method):
    assert getattr(client, method)("/contracts/staking").status_code == 405


def test_head_preserves_get_content_length_without_a_body(client):
    headers = {"Accept": "text/html"}
    get = client.get("/contracts/staking", headers=headers)
    head = client.head("/contracts/staking", headers=headers)
    assert head.status_code == get.status_code == 200
    assert head.content == b""
    assert head.headers["content-length"] == get.headers["content-length"]


def test_existing_files_and_json_errors_keep_status_and_body(client):
    assert client.get("/", headers={"Accept": "text/html"}).text == "<h1>Prerendered home</h1>"
    css = client.get("/existing.css", headers={"Accept": "text/html"})
    assert css.status_code == 200 and css.text == "body { color: green }"
    api = client.get("/contracts/api-error", headers={"Accept": "text/html"})
    assert api.status_code == 404 and api.json() == {"error": "missing"}


@pytest.mark.parametrize("accept,status", [("text/html", 200), ("application/json", 404)])
def test_cache_headers_are_preserved_and_vary_accept_is_merged(client, accept, status):
    response = client.get("/contracts/cached-error", headers={"Accept": accept})
    assert response.status_code == status
    assert response.headers["cache-control"] == "max-age=60"
    assert {part.strip().lower() for part in response.headers["vary"].split(",")} == {
        "accept",
        "accept-encoding",
    }


def test_websocket_protocol_is_delegated(client):
    with client.websocket_connect("/_event") as socket:
        assert socket.receive_text() == "delegated"


@pytest.mark.parametrize("vary", ["*", "Accept", "Accept-Encoding, ACCEPT"])
def test_existing_accept_or_wildcard_cache_variation_is_not_duplicated(client, vary):
    response = client.get(
        "/contracts/cached-error", params={"vary": vary}, headers={"Accept": "text/html"}
    )
    assert response.status_code == 200
    assert response.headers["vary"] == vary


def test_route_shell_status_does_not_attest_to_database_resource_existence(client):
    response = client.get("/contracts/no-such-resource", headers={"Accept": "text/html"})
    assert response.status_code == 200
    assert response.text == "<html>Compiled client router</html>"


@pytest.mark.parametrize(
    "accepts,status",
    [(["*/*", "text/html;q=0"], 404), (["application/json", "text/html"], 200)],
)
def test_repeated_accept_fields_obey_combined_document_preference(client, accepts, status):
    response = client.get("/contracts/staking", headers=[("Accept", value) for value in accepts])
    assert response.status_code == status


def test_repeated_vary_fields_preserve_all_existing_cache_dimensions(client):
    response = client.get(
        "/contracts/cached-error",
        params={"second_vary": "Origin"},
        headers={"Accept": "text/html"},
    )
    assert response.status_code == 200
    assert {part.strip().lower() for part in response.headers["vary"].split(",")} == {
        "accept-encoding",
        "origin",
        "accept",
    }
