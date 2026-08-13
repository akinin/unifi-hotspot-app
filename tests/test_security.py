import asyncio

import pytest
from fastapi import HTTPException

from api.config import Settings
from api.deps import require_api_token
from hotspot.admin import (
    _active_table,
    _archive_table,
    _layout,
    _redirect,
    _settings_form,
    _sms_log_table,
    _tabs,
    _unifi_overview,
    _wb_overview,
)
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
    assert 'href="unifi?lang=en"' in _tabs("en", "active")
    assert 'href="archive.csv"' in _archive_table([], "en")
    assert _redirect(message="done", root="../../").headers["location"].startswith("../../?")


def test_admin_dashboard_has_productivity_controls() -> None:
    settings = Settings(app_role="admin")
    active = _active_table(settings, [], {}, "en")
    archive = _archive_table([], "en")
    page = _layout(
        "Wiren Board",
        _wb_overview(settings, "en") + _sms_log_table([], "en"),
        "wb",
        "en",
    )

    assert 'data-filter-input="active"' in active
    assert 'data-filter-input="archive"' in archive
    assert 'data-filter-input="sms"' in page
    assert 'id="sms-message"' in page
    assert 'id="confirm-dialog"' in page
    assert 'class="toast"' in page
    assert 'src="wb-logo"' in page
    assert 'href="unifi?lang=en"' in page
    assert 'class="nav-mark unifi-mark"' in page
    assert "#0559C9" in page


def test_unifi_workspace_shows_connection_state_without_secrets() -> None:
    settings = Settings(
        app_role="admin",
        unifi_base_url="https://10.10.1.1",
        unifi_api_key="secret-key",
        unifi_dry_run=True,
    )
    page = _unifi_overview(settings, "en")

    assert "https://10.10.1.1" in page
    assert "Dry-run" in page
    assert "API key" in page
    assert "secret-key" not in page
    assert 'src="unifi-logo"' in page


def test_sms_store_records_delivery_history(tmp_path) -> None:
    from api.store import Store

    store = Store(str(tmp_path / "sms.sqlite3"))
    store.record_sms("+79990000000", "test", "mqtt", "sent")
    rows = store.list_sms_log()

    assert len(rows) == 1
    assert rows[0]["phone"] == "+79990000000"
    assert rows[0]["message"] == "test"
    assert rows[0]["status"] == "sent"
