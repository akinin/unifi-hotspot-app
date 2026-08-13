import asyncio
import time

import pytest
from fastapi import HTTPException

from api.config import Settings
from api.deps import require_api_token
from api.sms_monitor import WBSmsMonitor
from api.store import Store
from hotspot.admin import (
    _active_table,
    _archive_table,
    _layout,
    _portal_preview,
    _portal_preview_content,
    _portal_summary,
    _redirect,
    _sms_log_table,
    _tabs,
    _unifi_overview,
    _wb_overview,
    update_settings,
)
from hotspot.api import (
    ExtendRequest,
    PortalUpdate,
    active_clients,
    archive,
    block_client,
    extend_client,
    portal,
    revoke_client,
    update_portal,
)
from hotspot.store import HotspotStore
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

    assert 'href="preview?lang=en"' in _portal_summary(settings, "en")
    assert 'src="logo"' in _portal_summary(settings, "en")
    assert 'href="./?lang=en"' in _tabs("en", "active")
    assert 'href="archive.csv"' in _archive_table([], "en")
    assert _redirect(message="done", root="../../").headers["location"].startswith("../../?")


def test_admin_dashboard_has_productivity_controls() -> None:
    settings = Settings(app_role="admin")
    active = _active_table(settings, [], {}, "en")
    archive = _archive_table([], "en")
    page = _layout(
        "UniFi Hotspot",
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
    assert 'href="./?lang=en"' in page
    assert 'href="wb?lang=en"' in page
    assert 'href="usb?lang=en"' in page
    assert 'href="preview?lang=en"' in _tabs("en", "preview")
    assert 'name="backend" value="mqtt"' in page
    assert 'class="nav-mark unifi-mark"' in page
    assert "#0559C9" in page


def test_hotspot_preview_is_responsive_and_safe() -> None:
    settings = Settings(app_role="admin", hotspot_logo_size=164)
    workspace = _portal_preview(settings, "ru")
    content = _portal_preview_content("ru", settings, 164)

    assert 'sandbox="allow-scripts"' in workspace
    assert 'data-preview-width="390"' in workspace
    assert 'data-preview-width="760"' in workspace
    assert 'action="settings"' in workspace
    assert 'name="title"' in workspace
    assert 'name="background"' in workspace
    assert 'name="logo_size"' in workspace
    assert "class='active'" in _tabs("ru", "preview")
    assert 'src="data:image/png;base64,' in content
    assert "autofocus" not in content
    assert "Wi-Fi вход" in content
    assert "background-image: radial-gradient" in content
    assert "width: 164px" in content
    assert "fetch(" not in content
    assert 'data.type !== "portal-preview"' in content


def test_hotspot_designer_persists_all_appearance_settings(tmp_path) -> None:
    settings_file = tmp_path / "runtime.env"
    settings = Settings(app_role="admin", settings_file_path=str(settings_file))

    response = asyncio.run(
        update_settings(
            title="Guest portal",
            background="#34125f",
            logo_size=188,
            return_to="preview",
            lang="en",
            logo=None,
            settings=settings,
        )
    )
    saved = settings_file.read_text(encoding="utf-8")

    assert "HOTSPOT_PORTAL_TITLE=Guest portal" in saved
    assert "HOTSPOT_BACKGROUND_COLOR=#34125f" in saved
    assert "HOTSPOT_LOGO_SIZE=188" in saved
    assert response.headers["location"].startswith("preview?")


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


def test_usb_backend_uses_supplied_usb_branding() -> None:
    settings = Settings(app_role="admin", sms_backend="mmcli", mmcli_modem_id="any")
    page = _layout(
        "USB",
        _wb_overview(settings, "en"),
        "usb",
        "en",
        settings.sms_backend,
    )

    assert 'src="usb-logo"' in page
    assert "USB / ModemManager" in page
    assert "MMCLI" in page
    assert "Required WB script" not in page
    assert 'name="backend" value="mmcli"' in page


def test_active_clients_use_compact_action_popover() -> None:
    session = {
        "client_mac": "aa:bb:cc:dd:ee:ff",
        "phone": "+79990000000",
        "display_name": "Guest",
        "authorized_at": 1_700_000_000,
        "valid_until": 1_700_086_400,
    }
    page = _active_table(Settings(app_role="admin"), [session], {}, "ru")

    assert page.count("<th>") == 5
    assert 'class="client-actions-popover" popover' in page
    assert "Продлить" in page
    assert "Отозвать" in page
    assert "Блокировать" in page


def test_sms_store_records_delivery_history(tmp_path) -> None:
    from api.store import Store

    store = Store(str(tmp_path / "sms.sqlite3"))
    store.record_sms("+79990000000", "test", "mqtt", "sent")
    rows = store.list_sms_log()

    assert len(rows) == 1
    assert rows[0]["phone"] == "+79990000000"
    assert rows[0]["message"] == "test"
    assert rows[0]["status"] == "sent"


def test_wb_monitor_records_and_deduplicates_confirmed_sms(tmp_path) -> None:
    store = Store(str(tmp_path / "sms.sqlite3"))
    monitor = WBSmsMonitor(
        Settings(wb_sms_topic="/devices/sms_sender/controls/send/on"),
        store,
    )

    assert monitor.topic_root == "/devices/sms_sender/controls"
    values = {
        "last_sent_time": "2026-08-13T14:30:00.123Z",
        "last_message_text": "Test from Home Assistant",
        "last_recipient_number": "+79990000000",
        "last_result": "Команда отправки передана",
    }
    for field, value in values.items():
        monitor.handle_value(field, value)
    time.sleep(0.35)

    rows = store.list_sms_log()
    assert len(rows) == 1
    assert rows[0]["backend"] == "wb"
    assert rows[0]["status"] == "sent"

    for field, value in values.items():
        monitor.handle_value(field, value)
    time.sleep(0.35)
    assert len(store.list_sms_log()) == 1


def test_unifi_api_manages_portal_clients_and_archive(tmp_path) -> None:
    settings_file = tmp_path / "settings.env"
    settings = Settings(
        unifi_dry_run=True,
        settings_file_path=str(settings_file),
        hotspot_portal_title="Welcome",
    )
    store = Store(str(tmp_path / "hotspot.sqlite3"))
    hotspot_store = HotspotStore(store)
    hotspot_store.save_session(
        "00:11:22:33:44:55",
        "+79990000000",
        None,
        None,
    )
    hotspot_store.mark_authorized("00:11:22:33:44:55", 60)

    assert portal(settings=settings)["title"] == "Welcome"
    assert update_portal(PortalUpdate(title="Guest Wi-Fi"), settings=settings)["ok"]
    assert "HOTSPOT_PORTAL_TITLE=Guest Wi-Fi" in settings_file.read_text()

    clients = asyncio.run(active_clients(settings=settings, store=store))
    assert clients["count"] == 1
    assert clients["clients"][0]["mac"] == "00:11:22:33:44:55"

    extended = asyncio.run(
        extend_client(
            "00:11:22:33:44:55",
            ExtendRequest(days=2),
            settings=settings,
            store=store,
        )
    )
    assert extended["ok"]
    assert archive(store=store)["count"] == 2

    assert asyncio.run(
        revoke_client("00:11:22:33:44:55", settings=settings, store=store)
    )["ok"]

    hotspot_store.save_session(
        "00:11:22:33:44:66",
        "+79990000001",
        None,
        None,
    )
    hotspot_store.mark_authorized("00:11:22:33:44:66", 60)
    assert asyncio.run(
        block_client("00:11:22:33:44:66", settings=settings, store=store)
    )["ok"]
