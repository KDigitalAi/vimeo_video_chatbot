"""OpenAPI surface: duplicates and mirrors hidden, core routes documented."""

from __future__ import annotations


def test_openapi_excludes_versioned_mirrors_and_hidden_chat_queries(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json().get("paths", {})
    path_keys = list(paths.keys())

    assert "/" in paths and "get" in paths["/"]
    assert not any(p.startswith("/api/v1/") for p in path_keys)
    assert "/chat/queries" not in paths


def test_openapi_includes_core_chat_and_pdf(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json().get("paths", {})

    assert "/chat/query" in paths
    assert "post" in paths["/chat/query"]
    assert "/chat/sessions" in paths
    assert "/chat/sessions/{session_id}" in paths
    assert "/chat/sessions/{session_id}/history" in paths
    assert "/pdf" in paths
    assert "/pdf/{pdf_id}" in paths
