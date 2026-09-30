"""tests/integration/test_providers_api.py"""

from __future__ import annotations


async def test_list_providers(env):
    """GET /providers returns all providers (read-only endpoint for any user)."""
    c, _, auth = env
    r = await c.post(
        "/api/admin/providers",
        headers=auth,
        json={"name": "openai", "kind": "openai", "api_key": "k"},
    )
    assert r.status_code == 201

    r = await c.get("/api/providers", headers=auth)
    assert r.status_code == 200
    assert any(p["name"] == "openai" for p in r.json())


async def test_admin_creates_provider(env):
    """POST /admin/providers creates a provider."""
    c, _, auth = env
    r = await c.post(
        "/api/admin/providers",
        headers=auth,
        json={"name": "openai", "kind": "openai", "api_key": "k"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "openai"
    assert "user_id" not in body


async def test_regular_user_cannot_create_provider(env):
    """POST /admin/providers is admin-only."""
    c, _, admin_auth = env
    await c.post(
        "/api/users",
        headers=admin_auth,
        json={"username": "regular", "password": "TestPass12", "role": "user"},
    )
    tok = (
        await c.post("/api/auth/login", json={"username": "regular", "password": "TestPass12"})
    ).json()["access_token"]
    user_auth = {"Authorization": f"Bearer {tok}"}

    r = await c.post(
        "/api/admin/providers",
        headers=user_auth,
        json={"name": "should-fail", "kind": "openai"},
    )
    assert r.status_code == 403


async def test_admin_delete_provider(env):
    """DELETE /admin/providers/{id} removes the provider."""
    c, _, auth = env
    r = await c.post(
        "/api/admin/providers",
        headers=auth,
        json={"name": "to-delete", "kind": "openai"},
    )
    assert r.status_code == 201
    pid = r.json()["id"]

    r = await c.delete(f"/api/admin/providers/{pid}", headers=auth)
    assert r.status_code in (200, 204)

    r = await c.get("/api/admin/providers", headers=auth)
    ids = [p["id"] for p in r.json()]
    assert pid not in ids


async def test_admin_cannot_delete_local_runtime_provider(env):
    """DELETE /admin/providers/{id} keeps ONNX / Ollama local rows."""
    c, _, auth = env
    r = await c.post(
        "/api/admin/providers",
        headers=auth,
        json={"name": "ONNX (Local)", "kind": "openai", "api_key": "onnx"},
    )
    assert r.status_code == 201
    pid = r.json()["id"]

    r = await c.delete(f"/api/admin/providers/{pid}", headers=auth)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "PROVIDER_LOCAL_PROTECTED"

    r = await c.get("/api/admin/providers", headers=auth)
    ids = [p["id"] for p in r.json()]
    assert pid in ids


async def test_managed_wxzt_router_hides_token_and_is_not_mutable(env):
    c, srv, auth = env
    assert srv.services is not None
    existing = srv.services.provider_repo.get_by_name("wxzt-ai-router")
    pid = (
        existing.id
        if existing is not None
        else srv.services.provider_repo.create(
            name="wxzt-ai-router",
            kind="openai",
            base_url="https://wxzt.example/v1",
            api_key="router-secret",
            models_json='[{"id":"geminibalance_main","enabled":true}]',
        )
    )
    srv.services.provider_repo.update(
        pid,
        kind="openai",
        base_url="https://wxzt.example/v1",
        api_key="router-secret",
        models_json='[{"id":"geminibalance_main","enabled":true}]',
        enabled=True,
    )

    listed = await c.get("/api/providers", headers=auth)
    assert listed.status_code == 200
    row = next(item for item in listed.json() if item["id"] == pid)
    assert row["api_key"] is None
    assert row["api_key_configured"] is True

    patched = await c.patch(f"/api/admin/providers/{pid}", headers=auth, json={"enabled": False})
    assert patched.status_code == 409
    deleted = await c.delete(f"/api/admin/providers/{pid}", headers=auth)
    assert deleted.status_code == 409
