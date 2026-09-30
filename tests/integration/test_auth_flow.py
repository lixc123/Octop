"""tests/integration/test_auth_flow.py"""

from __future__ import annotations

import pytest

from tests.support.auth import bootstrap_admin


@pytest.fixture
async def client(app_client):
    yield app_client


async def test_setup_required_then_login(client):
    c, srv, home = client
    r = await c.get("/api/setup/status")
    assert r.json()["setup_required"] is True
    r = await c.post("/api/auth/login", json={"username": "x", "password": "y"})
    assert r.status_code == 503 and r.json()["setup_required"] is True
    r = await bootstrap_admin(c, home, username="alice", password="TestPass12")
    assert r.status_code == 201
    r = await c.post("/api/auth/login", json={"username": "alice", "password": "TestPass12"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    r = await c.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.json()["username"] == "alice"

    r = await c.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 204


async def test_setup_again_410(client):
    c, _, home = client
    await bootstrap_admin(c, home, username="a", password="TestPass12")
    r = await c.post("/api/setup/initial-admin", json={"username": "b", "password": "TestPass12"})
    assert r.status_code == 410


async def test_change_password(client):
    c, _, home = client
    await bootstrap_admin(c, home, username="a", password="OldPass12")
    tok = (await c.post("/api/auth/login", json={"username": "a", "password": "OldPass12"})).json()[
        "access_token"
    ]
    r = await c.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {tok}"},
        json={"old_password": "OldPass12", "new_password": "NewPass12"},
    )
    assert r.status_code == 204
    assert (
        await c.post("/api/auth/login", json={"username": "a", "password": "OldPass12"})
    ).status_code == 401
    assert (
        await c.post("/api/auth/login", json={"username": "a", "password": "NewPass12"})
    ).status_code == 200


async def test_invalid_token_401(client):
    c, _, home = client
    await bootstrap_admin(c, home, username="a", password="TestPass12")
    r = await c.get("/api/auth/me", headers={"Authorization": "Bearer not.a.token"})
    assert r.status_code == 401


async def test_health_no_auth_required(client):
    c, _, _ = client
    r = await c.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert isinstance(body.get("started_at"), int)


async def test_captcha_public_is_setup_locked_then_slider(client):
    c, _, home = client
    r = await c.get("/api/auth/captcha")
    assert r.status_code == 503
    assert r.json()["setup_required"] is True
    await bootstrap_admin(c, home, username="alice", password="TestPass12")
    r = await c.get("/api/auth/captcha")
    assert r.status_code == 200
    assert r.json() == {"provider": "slider"}


async def test_patch_me_updates_display_name(client) -> None:
    c, _srv, home = client
    await bootstrap_admin(c, home)
    tok = (
        await c.post("/api/auth/login", json={"username": "admin", "password": "TestPass12"})
    ).json()["access_token"]
    auth = {"Authorization": f"Bearer {tok}"}

    r = await c.patch("/api/auth/me", json={"display_name": "Alice"}, headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["display_name"] == "Alice"
    assert body["username"] == "admin"

    r2 = await c.get("/api/auth/me", headers=auth)
    assert r2.json()["display_name"] == "Alice"


async def test_patch_me_clears_display_name(client) -> None:
    c, _srv, home = client
    await bootstrap_admin(c, home)
    tok = (
        await c.post("/api/auth/login", json={"username": "admin", "password": "TestPass12"})
    ).json()["access_token"]
    auth = {"Authorization": f"Bearer {tok}"}
    await c.patch("/api/auth/me", json={"display_name": "Alice"}, headers=auth)

    r = await c.patch("/api/auth/me", json={"display_name": None}, headers=auth)
    assert r.status_code == 200
    assert r.json()["display_name"] is None


async def test_patch_me_requires_auth(client) -> None:
    c, _srv, home = client
    await bootstrap_admin(c, home)
    r = await c.patch("/api/auth/me", json={"display_name": "Alice"})
    assert r.status_code == 401


async def test_wxzt_exchange_marks_source_blocks_password_and_revokes_token(
    client, monkeypatch
) -> None:
    """wxzt SSO is server-trusted, one-session scoped, and cannot edit local passwords."""
    from unittest.mock import AsyncMock

    monkeypatch.setenv("OCTOP_WXZT_ORIGIN", "https://wxzt.example")
    monkeypatch.setattr(
        "octop.api.routers.auth.redeem_ticket",
        AsyncMock(
            return_value={
                "userid": "wxzt-user-1",
                "username": "lixc",
                "display_name": "wxzt user",
                "role": "user",
                "logout_url": "https://wxzt.example/logout",
            }
        ),
    )
    c, _srv, _home = client
    await bootstrap_admin(c, _home)

    exchanged = await c.post(
        "/api/auth/wxzt/exchange",
        json={"code": "x" * 32, "return_url": "https://evil.example/steal"},
    )
    assert exchanged.status_code == 200, exchanged.text
    body = exchanged.json()
    assert body["user"]["auth_source"] == "wxzt"
    assert body["return_url"] == "https://wxzt.example/ai_hub_layout"
    assert body["logout_url"] == "https://wxzt.example/logout"
    local_login = await c.post(
        "/api/auth/login",
        json={"username": body["user"]["username"], "password": "Yx123456"},
    )
    assert local_login.status_code == 200, local_login.text
    token = body["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    me = await c.get("/api/auth/me", headers=auth)
    assert me.status_code == 200
    assert me.json()["auth_source"] == "wxzt"

    changed = await c.post(
        "/api/auth/change-password",
        headers=auth,
        json={"old_password": "does-not-apply", "new_password": "NewPass12"},
    )
    assert changed.status_code == 403

    logged_out = await c.post("/api/auth/logout", headers=auth)
    assert logged_out.status_code == 204
    assert (await c.get("/api/auth/me", headers=auth)).status_code == 401


async def test_wxzt_admin_role_keeps_admin_scope_but_not_password_change(
    client, monkeypatch
) -> None:
    from unittest.mock import AsyncMock

    monkeypatch.setenv("OCTOP_WXZT_ORIGIN", "https://wxzt.example")
    monkeypatch.setattr(
        "octop.api.routers.auth.redeem_ticket",
        AsyncMock(
            return_value={
                "userid": "wxzt-admin-1",
                "username": "wxzt-admin",
                "display_name": "wxzt admin",
                "role": "admin",
            }
        ),
    )
    c, _srv, _home = client
    await bootstrap_admin(c, _home)
    exchanged = await c.post("/api/auth/wxzt/exchange", json={"code": "y" * 32})
    assert exchanged.status_code == 200, exchanged.text
    body = exchanged.json()
    auth = {"Authorization": f"Bearer {body['access_token']}"}
    assert (await c.get("/api/admin/overview", headers=auth)).status_code == 200
    assert (
        await c.post(
            "/api/auth/change-password",
            headers=auth,
            json={"old_password": "x", "new_password": "NewPass12"},
        )
    ).status_code == 403


_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


async def test_me_can_choose_icon_and_upload(client) -> None:
    c, _srv, home = client
    await bootstrap_admin(c, home)
    tok = (
        await c.post("/api/auth/login", json={"username": "admin", "password": "TestPass12"})
    ).json()["access_token"]
    auth = {"Authorization": f"Bearer {tok}"}
    me = (await c.get("/api/auth/me", headers=auth)).json()

    chosen = await c.patch("/api/auth/me", headers=auth, json={"avatar_icon": "smile"})
    assert chosen.status_code == 200, chosen.text
    assert chosen.json()["avatar_icon"] == "smile"

    uploaded = await c.post(
        "/api/auth/me/avatar",
        headers=auth,
        files={"file": ("avatar.png", _PNG, "image/png")},
    )
    assert uploaded.status_code == 201, uploaded.text
    fetched = await c.get(f"/api/users/{me['id']}/avatar", headers=auth)
    assert fetched.status_code == 200
    assert fetched.content == _PNG

    cleared = await c.patch("/api/auth/me", headers=auth, json={"avatar_icon": None})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["avatar_icon"] is None
    assert cleared.json()["avatar_url"] is None
