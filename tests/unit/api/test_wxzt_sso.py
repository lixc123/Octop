from __future__ import annotations

from octop.api.common.wxzt_sso import allowed_logout_url, allowed_return_url


def test_wxzt_navigation_urls_are_same_origin_and_canonical(monkeypatch) -> None:
    monkeypatch.setenv("OCTOP_WXZT_ORIGIN", "https://wxzt.example")
    assert allowed_return_url("https://wxzt.example/ai_hub_layout") == (
        "https://wxzt.example/ai_hub_layout"
    )
    assert allowed_logout_url("https://wxzt.example/logout") == "https://wxzt.example/logout"

    assert allowed_return_url("https://evil.example/ai_hub_layout") == (
        "https://wxzt.example/ai_hub_layout"
    )
    assert allowed_return_url("https://wxzt.example/ai_hub_layout?site=octop") == (
        "https://wxzt.example/ai_hub_layout"
    )
    assert allowed_logout_url("https://wxzt.example/logout?next=https://evil.example") == (
        "https://wxzt.example/logout"
    )
