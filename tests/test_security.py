import asyncio

import pytest
from fastapi import HTTPException

from api.config import Settings
from api.deps import require_api_token
from hotspot.admin import _archive_table, _redirect, _settings_form, _tabs
from hotspot.unifi import UniFiClient


def test_missing_api_token_keeps_protected_api_closed() -> None:
    settings = Settings(api_token=None)

    with pytest.raises(HTTPException) as error:
        require_api_token(settings=settings, authorization=None)

    assert error.value.status_code == 503


def test_configured_api_token_is_required() -> None:
    settings = Settings(api_token="secret-token")

    with pytest.raises(HTTPException) as error:
        require_api_token(settings=settings, authorization="Bearer wrong-token")

    assert error.value.status_code == 401
    require_api_token(settings=settings, authorization="Bearer secret-token")


def test_unifi_dry_run_does_not_require_credentials_or_network() -> None:
    client = UniFiClient(Settings(unifi_dry_run=True, unifi_base_url=None))

    asyncio.run(client.authorize_guest("00:11:22:33:44:55"))
    asyncio.run(client.unauthorize_guest("00:11:22:33:44:55"))
    asyncio.run(client.block_client("00:11:22:33:44:55"))


def test_admin_markup_uses_ingress_safe_relative_links() -> None:
    settings = Settings(app_role="admin")

    assert 'action="settings"' in _settings_form(settings, "en", "active")
    assert 'src="logo"' in _settings_form(settings, "en", "active")
    assert 'href="./?lang=en"' in _tabs("en", "active")
    assert 'href="archive.csv"' in _archive_table([], "en")
    assert _redirect(message="done", root="../../").headers["location"].startswith("../../?")
