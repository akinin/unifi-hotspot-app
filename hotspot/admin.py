import csv
import html
import io
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse

from api.config import Settings, get_settings
from api.deps import get_store
from api.models import normalize_phone
from api.sms import SmsSender
from api.store import Store

from .audit import build_access_event, record_access_event
from .store import HotspotStore
from .unifi import UniFiClient, UniFiClientNotFoundError

router = APIRouter(prefix="/admin")
ADMIN_ROOT = "./"
LOGO_PATH = Path(__file__).with_name("assets") / "ahs.png"

TEXT = {
    "en": {
        "active": "Active",
        "archive": "Archive",
        "portal": "Portal",
        "welcome_text": "Welcome text",
        "logo": "Logo",
        "choose_file": "Choose file",
        "no_file": "No file selected",
        "save": "Save",
        "test_sms": "Test SMS",
        "phone": "Phone",
        "message": "Message",
        "send": "Send",
        "active_clients": "Active clients",
        "client": "Client",
        "ip": "IP",
        "authorized": "Authorized",
        "valid_until": "Valid until",
        "traffic": "Traffic",
        "unifi": "UniFi",
        "actions": "Actions",
        "extend": "Extend",
        "edit": "Edit",
        "name": "Name",
        "no_active": "No active clients",
        "duration": "Duration",
        "status": "Status",
        "empty_archive": "Archive is empty",
        "revoke": "Revoke",
        "block": "Block",
        "theme": "Toggle theme",
        "export_csv": "Export CSV",
        "portal_saved": "Portal settings updated",
        "sms_sent": "Test SMS sent",
        "subtitle": "Wiren Board SMS and guest access",
        "portal_help": "Configure the welcome screen shown to Wi-Fi guests.",
        "sms_help": "Send a diagnostic message through the configured Wiren Board.",
        "active_help": "Manage authorized guests and their access time.",
        "archive_help": "Review previous guest authorizations and export the history.",
        "change_logo": "Click the logo to replace it",
        "no_active_hint": "Newly authorized Wi-Fi guests will appear here.",
        "search_clients": "Search clients",
        "search_archive": "Search archive",
        "found": "Found",
        "refresh": "Refresh",
        "copy": "Copy",
        "write_sms": "SMS",
        "copied": "Copied",
        "confirm_title": "Confirm action",
        "confirm_text": "This action changes guest access. Continue?",
        "cancel": "Cancel",
        "confirm": "Continue",
        "characters": "characters",
    },
    "ru": {
        "active": "Активные",
        "archive": "Архив",
        "portal": "Портал",
        "welcome_text": "Текст приветствия",
        "logo": "Логотип",
        "choose_file": "Выберите файл",
        "no_file": "Файл не выбран",
        "save": "Сохранить",
        "test_sms": "Тестовая SMS",
        "phone": "Телефон",
        "message": "Текст сообщения",
        "send": "Отправить",
        "active_clients": "Активные клиенты",
        "client": "Клиент",
        "ip": "IP",
        "authorized": "Авторизован",
        "valid_until": "Действует до",
        "traffic": "Трафик",
        "unifi": "UniFi",
        "actions": "Действия",
        "extend": "Продлить",
        "edit": "Изменить",
        "name": "Имя",
        "no_active": "Активных клиентов нет",
        "duration": "Срок",
        "status": "Статус",
        "empty_archive": "Архив пуст",
        "revoke": "Отозвать",
        "block": "Блокировать",
        "theme": "Сменить тему",
        "export_csv": "Выгрузить CSV",
        "portal_saved": "Настройки портала сохранены",
        "sms_sent": "Тестовая SMS отправлена",
        "subtitle": "SMS через Wiren Board и гостевой доступ",
        "portal_help": "Настройте экран приветствия, который увидят гости Wi-Fi.",
        "sms_help": "Отправьте диагностическое сообщение через настроенный Wiren Board.",
        "active_help": "Управляйте авторизованными гостями и сроком их доступа.",
        "archive_help": "Просматривайте историю авторизаций и выгружайте её в CSV.",
        "change_logo": "Нажмите на логотип, чтобы заменить его",
        "no_active_hint": "Здесь появятся авторизованные гости Wi-Fi.",
        "search_clients": "Поиск клиентов",
        "search_archive": "Поиск по архиву",
        "found": "Найдено",
        "refresh": "Обновить",
        "copy": "Копировать",
        "write_sms": "SMS",
        "copied": "Скопировано",
        "confirm_title": "Подтвердите действие",
        "confirm_text": "Это действие изменит гостевой доступ. Продолжить?",
        "cancel": "Отмена",
        "confirm": "Продолжить",
        "characters": "символов",
    },
}


def require_admin(settings: Settings = Depends(get_settings)) -> Settings:
    if settings.app_role != "admin":
        raise HTTPException(status_code=404, detail="not found")
    return settings


@router.get("/", response_class=HTMLResponse)
async def admin_home(
    request: Request,
    settings: Settings = Depends(require_admin),
    store: Store = Depends(get_store),
) -> HTMLResponse:
    lang = _lang(request)
    hotspot_store = HotspotStore(store)
    sessions = hotspot_store.list_active_sessions()
    unifi_clients = await _safe_unifi_clients(settings)
    message = request.query_params.get("message", "")
    error = request.query_params.get("error", "")
    return HTMLResponse(
        _layout(
            "Active clients",
            _messages(message, error)
            + _dashboard_cards(settings, lang, "active")
            + _active_table(settings, sessions, unifi_clients, lang),
            active_tab="active",
            lang=lang,
        )
    )


@router.get("/archive", response_class=HTMLResponse)
def admin_archive(
    request: Request,
    settings: Settings = Depends(require_admin),
    store: Store = Depends(get_store),
) -> HTMLResponse:
    lang = _lang(request)
    rows = HotspotStore(store).list_archive()
    message = request.query_params.get("message", "")
    error = request.query_params.get("error", "")
    return HTMLResponse(
        _layout(
            "Archive",
            _messages(message, error)
            + _dashboard_cards(settings, lang, "archive")
            + _archive_table(rows, lang),
            active_tab="archive",
            lang=lang,
        )
    )


@router.get("/logo")
def admin_logo(settings: Settings = Depends(require_admin)) -> FileResponse:
    logo_path = Path(settings.hotspot_logo_path)
    return FileResponse(logo_path if logo_path.exists() else LOGO_PATH)


@router.get("/archive.csv")
def export_archive_csv(
    settings: Settings = Depends(require_admin),
    store: Store = Depends(get_store),
) -> StreamingResponse:
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(
        ["Name", "MAC", "Phone", "Authorized at", "Valid until", "Duration days", "Status"]
    )
    now = int(time.time())
    for row in HotspotStore(store).list_archive(limit=100000):
        writer.writerow(
            [
                row["display_name"] or "",
                row["client_mac"],
                row["phone"],
                _dt(row["authorized_at"]),
                _dt(row["valid_until"]),
                row["minutes"] // 1440,
                _archive_status(row, now),
            ]
        )
    headers = {"Content-Disposition": 'attachment; filename="hotspot-archive.csv"'}
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8", headers=headers)


@router.post("/clients/{client_mac}/extend")
async def extend_client(
    client_mac: str,
    days: int = Form(...),
    lang: str = Form(default="en"),
    settings: Settings = Depends(require_admin),
    store: Store = Depends(get_store),
):
    if days not in (1, 2, 7, 365):
        return _redirect(error="Invalid duration", lang=lang, root="../../")
    hotspot_store = HotspotStore(store)
    session = hotspot_store.get_session(client_mac)
    if not session:
        return _redirect(error="Client was not found", lang=lang, root="../../")
    now = int(time.time())
    remaining_minutes = max(0, int(session["valid_until"] or now) - now) // 60
    minutes = remaining_minutes + days * 24 * 60
    try:
        await UniFiClient(settings).authorize_guest(
            client_mac,
            minutes=minutes,
            ap_mac=session["ap_mac"],
        )
    except UniFiClientNotFoundError:
        pass
    except Exception as exc:
        return _redirect(error=f"UniFi authorize failed: {exc}", lang=lang, root="../../")
    authorized_at = hotspot_store.mark_authorized(client_mac, minutes)
    session = hotspot_store.get_session(client_mac)
    record_access_event(
        settings,
        build_access_event(
            settings,
            client_mac,
            session["phone"],
            authorized_at,
            session["valid_until"],
        ),
    )
    return _redirect(message=f"Authorization extended for {days} day(s)", lang=lang, root="../../")


@router.post("/clients/{client_mac}/revoke")
async def revoke_client(
    client_mac: str,
    lang: str = Form(default="en"),
    settings: Settings = Depends(require_admin),
    store: Store = Depends(get_store),
):
    try:
        await UniFiClient(settings).unauthorize_guest(client_mac)
    except UniFiClientNotFoundError:
        pass
    except Exception as exc:
        return _redirect(error=f"UniFi revoke failed: {exc}", lang=lang, root="../../")
    HotspotStore(store).clear_authorized(client_mac)
    return _redirect(message="Authorization revoked", lang=lang, root="../../")


@router.post("/clients/{client_mac}/name")
def update_client_name(
    client_mac: str,
    display_name: str = Form(default=""),
    lang: str = Form(default="en"),
    settings: Settings = Depends(require_admin),
    store: Store = Depends(get_store),
):
    if not HotspotStore(store).set_display_name(client_mac, display_name):
        return _redirect(error="Client was not found", lang=lang, root="../../")
    return _redirect(message="Client name updated", lang=lang, root="../../")


@router.post("/clients/{client_mac}/block")
async def block_client(
    client_mac: str,
    lang: str = Form(default="en"),
    settings: Settings = Depends(require_admin),
    store: Store = Depends(get_store),
):
    try:
        await UniFiClient(settings).block_client(client_mac)
    except Exception as exc:
        return _redirect(error=f"UniFi block failed: {exc}", lang=lang, root="../../")
    HotspotStore(store).mark_blocked(client_mac, "Blocked from admin")
    return _redirect(message="Client blocked", lang=lang, root="../../")


@router.post("/settings")
async def update_settings(
    title: str = Form(...),
    lang: str = Form(default="en"),
    logo: Optional[UploadFile] = File(default=None),
    settings: Settings = Depends(require_admin),
):
    title = title.strip()[:120] or "Welcome"
    settings_path = Path(settings.settings_file_path)
    _set_env_value(settings_path, "HOTSPOT_PORTAL_TITLE", title)
    if logo and logo.filename:
        suffix = Path(logo.filename).suffix.lower()
        if suffix not in (".png", ".jpg", ".jpeg", ".webp", ".svg"):
            return _redirect(error="Unsupported logo format", lang=lang)
        logo_path = settings_path.parent / f"hotspot_logo{suffix}"
        logo_path.parent.mkdir(parents=True, exist_ok=True)
        with logo_path.open("wb") as output:
            shutil.copyfileobj(logo.file, output)
        _set_env_value(settings_path, "HOTSPOT_LOGO_PATH", str(logo_path))
    get_settings.cache_clear()
    return _redirect(message=_t(lang, "portal_saved"), lang=lang)


@router.post("/test-sms")
def send_test_sms(
    phone: str = Form(...),
    message: str = Form(...),
    lang: str = Form(default="en"),
    settings: Settings = Depends(require_admin),
):
    try:
        message = message.strip()
        if not message:
            raise ValueError("message is empty")
        SmsSender(settings).send(normalize_phone(phone), message)
    except Exception as exc:
        return _redirect(error=f"SMS send failed: {exc}", lang=lang)
    return _redirect(message=_t(lang, "sms_sent"), lang=lang)


async def _safe_unifi_clients(settings: Settings) -> dict[str, dict[str, Any]]:
    try:
        clients = await UniFiClient(settings).list_clients()
    except Exception:
        return {}
    return {
        str(client.get("mac", "")).lower(): client
        for client in clients
        if client.get("mac")
    }


def _set_env_value(path: Path, key: str, value: str) -> None:
    safe_value = value.replace("\r", " ").replace("\n", " ").strip()
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    updated = False
    for index, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[index] = f"{key}={safe_value}"
            updated = True
            break
    if not updated:
        lines.append(f"{key}={safe_value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _lang(request: Request) -> str:
    value = request.query_params.get("lang", "").lower()
    if value in TEXT:
        return value
    accepted = request.headers.get("accept-language", "").lower()
    return "ru" if accepted.startswith("ru") or ",ru" in accepted else "en"


def _t(lang: str, key: str) -> str:
    return TEXT.get(lang, TEXT["en"]).get(key, key)


def _redirect(
    message: str = "",
    error: str = "",
    lang: str = "en",
    root: str = ADMIN_ROOT,
) -> RedirectResponse:
    suffix = f"lang={_url(lang if lang in TEXT else 'en')}"
    if error:
        return RedirectResponse(f"{root}?{suffix}&error={_url(error)}", status_code=303)
    if message:
        return RedirectResponse(f"{root}?{suffix}&message={_url(message)}", status_code=303)
    return RedirectResponse(f"{root}?{suffix}", status_code=303)


def _url(value: str) -> str:
    from urllib.parse import quote

    return quote(value)


def _messages(message: str, error: str) -> str:
    if error:
        return f"<div class='notice error' role='alert'><span class='notice-icon'>!</span><span>{html.escape(error)}</span></div>"
    if message:
        return f"<div class='notice success' role='status'><span class='notice-icon'>✓</span><span>{html.escape(message)}</span></div>"
    return ""


def _settings_form(settings: Settings, lang: str, active_tab: str) -> str:
    title = html.escape(settings.hotspot_portal_title)
    return f"""
    <section class="ha-card portal-card">
      <div class="card-heading">
        <span class="card-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24"><path d="M12 18.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3ZM7.76 14.26l1.42 1.42a4 4 0 0 1 5.64 0l1.42-1.42a6 6 0 0 0-8.48 0ZM4.93 11.43l1.42 1.42a8 8 0 0 1 11.3 0l1.42-1.42a10 10 0 0 0-14.14 0ZM2.1 8.6 3.5 10a12 12 0 0 1 17 0l1.4-1.4a14 14 0 0 0-19.8 0Z"/></svg>
        </span>
        <div><h2>{_t(lang, "portal")}</h2><p>{_t(lang, "portal_help")}</p></div>
      </div>
      <form class="settings card-content" method="post" action="settings" enctype="multipart/form-data">
        <input type="hidden" name="lang" value="{html.escape(lang)}">
        <label class="field"><span>{_t(lang, "welcome_text")}</span><input name="title" value="{title}" maxlength="120"></label>
        <label class="logo-picker" title="{_t(lang, 'choose_file')}">
          <span class="logo-preview">
            <input id="logo-file" name="logo" type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml">
            <img id="logo-preview" src="logo" alt="{_t(lang, 'logo')}">
          </span>
          <span class="logo-copy"><strong>{_t(lang, "logo")}</strong><small>{_t(lang, "change_logo")}</small></span>
        </label>
        <div class="card-actions"><button class="primary-button" type="submit">{_t(lang, "save")}</button></div>
      </form>
    </section>
    """


def _dashboard_cards(settings: Settings, lang: str, active_tab: str) -> str:
    return f'<div class="dashboard-grid">{_settings_form(settings, lang, active_tab)}{_test_sms_form(lang)}</div>'


def _test_sms_form(lang: str) -> str:
    return f"""
    <section class="ha-card sms-card">
      <div class="card-heading">
        <span class="card-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24"><path d="M20 2H4a2 2 0 0 0-2 2v18l4-4h14a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2Zm0 14H5.17L4 17.17V4h16v12Z"/></svg>
        </span>
        <div><h2>{_t(lang, "test_sms")}</h2><p>{_t(lang, "sms_help")}</p></div>
      </div>
      <form class="test-sms card-content" method="post" action="test-sms">
        <input type="hidden" name="lang" value="{html.escape(lang)}">
        <label class="field"><span>{_t(lang, "phone")}</span><input id="sms-phone" name="phone" type="tel" inputmode="tel" autocomplete="tel" placeholder="+79991234567" required></label>
        <label class="field"><span>{_t(lang, "message")} <small id="message-counter">0 / 1000 {_t(lang, "characters")}</small></span><textarea id="sms-message" name="message" maxlength="1000" rows="3" required></textarea></label>
        <div class="card-actions"><button class="primary-button" type="submit">{_t(lang, "send")}</button></div>
      </form>
    </section>
    """


def _active_table(
    settings: Settings,
    sessions,
    unifi_clients: dict[str, dict[str, Any]],
    lang: str,
) -> str:
    rows = []
    for session in sessions:
        mac = str(session["client_mac"]).lower()
        client = unifi_clients.get(mac, {})
        phone = str(session["phone"])
        display_name = str(session["display_name"] or client.get("name") or client.get("hostname") or "")
        ip_address = str(client.get("ip") or "")
        search_text = html.escape(f"{display_name} {mac} {phone} {ip_address}".lower(), quote=True)
        rows.append(
            f"<tr data-filter-row data-search='{search_text}'>"
            f"<td data-label='{_t(lang, 'client')}'>{_client_identity(session, client, mac, lang)}</td>"
            f"<td data-label='{_t(lang, 'phone')}'><div class='value-actions'><span>{html.escape(phone)}</span><button type='button' class='icon-button copy-button' data-copy='{html.escape(phone, quote=True)}' title='{_t(lang, 'copy')}' aria-label='{_t(lang, 'copy')}'>⧉</button><button type='button' class='text-button sms-client-button' data-phone='{html.escape(phone, quote=True)}'>{_t(lang, 'write_sms')}</button></div></td>"
            f"<td data-label='{_t(lang, 'ip')}'>{html.escape(ip_address)}</td>"
            f"<td data-label='{_t(lang, 'authorized')}'>{_dt(session['authorized_at'])}</td>"
            f"<td data-label='{_t(lang, 'valid_until')}'>{_dt(session['valid_until'])}</td>"
            f"<td data-label='{_t(lang, 'extend')}'>{_extend_actions(mac, lang)}</td>"
            f"<td data-label='{_t(lang, 'revoke')}'>{_revoke_actions(mac, lang)}</td>"
            f"<td data-label='{_t(lang, 'block')}'>{_block_action(mac, lang)}</td>"
            "</tr>"
        )
    body = "\n".join(rows) if rows else f"<tr class='empty-row'><td colspan='8' class='empty'><strong>{_t(lang, 'no_active')}</strong><small>{_t(lang, 'no_active_hint')}</small></td></tr>"
    return f"""
    <section class="ha-card clients-card">
      <div class="section-head card-heading table-heading">
        <div class="section-title"><span class="card-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M16 11c1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3 1.34 3 3 3Zm-8 0c1.66 0 3-1.34 3-3S9.66 5 8 5 5 6.34 5 8s1.34 3 3 3Zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5C15 14.17 10.33 13 8 13Zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5Z"/></svg></span><div><h2>{_t(lang, "active_clients")}</h2><p>{_t(lang, "active_help")}</p></div></div>
        {_tabs(lang, "active")}
      </div>
      {_table_toolbar(lang, "active")}
      <div class="table-scroll"><table class="active-table filter-table" data-filter-table="active">
        <colgroup>
          <col class="col-client"><col class="col-phone"><col class="col-ip">
          <col class="col-date"><col class="col-date"><col class="col-extend">
          <col class="col-action"><col class="col-action">
        </colgroup>
        <thead>
          <tr>
            <th>{_t(lang, "client")}</th><th>{_t(lang, "phone")}</th><th>{_t(lang, "ip")}</th><th>{_t(lang, "authorized")}</th>
            <th>{_t(lang, "valid_until")}</th><th>{_t(lang, "extend")}</th><th>{_t(lang, "revoke")}</th><th>{_t(lang, "block")}</th>
          </tr>
        </thead>
        <tbody>{body}</tbody>
      </table></div>
    </section>
    """


def _client_identity(session, client: dict[str, Any], mac: str, lang: str) -> str:
    name = str(session["display_name"] or client.get("name") or client.get("hostname") or "")
    return f"""
    <button type="button" class="client-display" title="{_t(lang, 'edit')}">{html.escape(name or mac)}</button>
    <span class="muted-line"><small>{html.escape(mac)}</small><button type="button" class="icon-button copy-button" data-copy="{html.escape(mac, quote=True)}" title="{_t(lang, 'copy')}" aria-label="{_t(lang, 'copy')}">⧉</button></span>
    <form class="client-name" method="post" action="clients/{html.escape(mac)}/name" hidden>
      <input type="hidden" name="lang" value="{html.escape(lang)}">
      <input name="display_name" value="{html.escape(name)}" maxlength="120" placeholder="{_t(lang, 'name')}">
    </form>
    """


def _extend_actions(mac: str, lang: str = "en") -> str:
    options = "".join(
        f"<button name='days' value='{days}'>+{days}d</button>"
        for days in (1, 2, 7, 365)
    )
    return f"""
    <div class="actions">
      <form method="post" action="clients/{html.escape(mac)}/extend"><input type="hidden" name="lang" value="{html.escape(lang)}">{options}</form>
    </div>
    """


def _revoke_actions(mac: str, lang: str = "en") -> str:
    return f"""
    <div class="actions">
      <form method="post" action="clients/{html.escape(mac)}/revoke" data-confirm><input type="hidden" name="lang" value="{html.escape(lang)}"><button class="secondary-button">{_t(lang, "revoke")}</button></form>
    </div>
    """


def _block_action(mac: str, lang: str = "en") -> str:
    return f"""
    <div class="actions">
      <form method="post" action="clients/{html.escape(mac)}/block" data-confirm><input type="hidden" name="lang" value="{html.escape(lang)}"><button class="danger">{_t(lang, "block")}</button></form>
    </div>
    """


def _archive_table(rows, lang: str) -> str:
    now = int(time.time())
    table_rows = []
    for row in rows:
        status = _archive_status(row, now)
        search_text = html.escape(
            f"{row['display_name'] or ''} {row['client_mac']} {row['phone']} {status}".lower(),
            quote=True,
        )
        table_rows.append(
            f"<tr data-filter-row data-search='{search_text}'>"
            f"<td><strong>{html.escape(str(row['display_name'] or row['client_mac']))}</strong><small>{html.escape(str(row['client_mac']))}</small></td>"
            f"<td>{html.escape(str(row['phone']))}</td>"
            f"<td>{_dt(row['authorized_at'])}</td>"
            f"<td>{_dt(row['valid_until'])}</td>"
            f"<td>{row['minutes'] // 1440}d</td>"
            f"<td><span class='badge {status}'>{status}</span></td>"
            "</tr>"
        )
    body = "\n".join(table_rows) if table_rows else f"<tr class='empty-row'><td colspan='6' class='empty'>{_t(lang, 'empty_archive')}</td></tr>"
    return f"""
    <section class="ha-card clients-card">
      <div class="section-head card-heading table-heading">
        <div class="section-title"><span class="card-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M20.54 5.23 19.15 3.55A1.45 1.45 0 0 0 18 3H6c-.46 0-.88.21-1.15.55L3.46 5.23C3.17 5.57 3 6 3 6.5V19a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6.5c0-.5-.17-.93-.46-1.27ZM6.24 5h11.52l.83 1H5.41l.83-1ZM5 19V8h14v11H5Zm4-9h6v2H9v-2Z"/></svg></span><div><h2>{_t(lang, "archive")}</h2><p>{_t(lang, "archive_help")}</p></div></div>
        <div class="table-tools"><a class="secondary-button export-button" href="archive.csv">{_t(lang, "export_csv")}</a>{_tabs(lang, "archive")}</div>
      </div>
      {_table_toolbar(lang, "archive")}
      <div class="table-scroll"><table class="filter-table" data-filter-table="archive">
        <thead>
          <tr><th>{_t(lang, "client")}</th><th>{_t(lang, "phone")}</th><th>{_t(lang, "authorized")}</th><th>{_t(lang, "valid_until")}</th><th>{_t(lang, "duration")}</th><th>{_t(lang, "status")}</th></tr>
        </thead>
        <tbody>{body}</tbody>
      </table></div>
    </section>
    """


def _table_toolbar(lang: str, table_name: str) -> str:
    placeholder = _t(lang, "search_archive" if table_name == "archive" else "search_clients")
    return f"""
    <div class="table-toolbar">
      <label class="search-field">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m21 20-5.2-5.2a7 7 0 1 0-1 1L20 21l1-1ZM5 10.5a5.5 5.5 0 1 1 11 0 5.5 5.5 0 0 1-11 0Z"/></svg>
        <input type="search" data-filter-input="{table_name}" placeholder="{placeholder}" autocomplete="off">
      </label>
      <span class="result-count" data-result-count="{table_name}">{_t(lang, "found")}: 0</span>
      <button type="button" class="secondary-button refresh-button" data-refresh>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M17.65 6.35A7.95 7.95 0 0 0 12 4a8 8 0 1 0 7.75 10h-2.1A6 6 0 1 1 12 6c1.66 0 3.14.69 4.22 1.78L13 11h8V3l-3.35 3.35Z"/></svg>
        {_t(lang, "refresh")}
      </button>
    </div>
    """


def _archive_status(row, now: int) -> str:
    if row["blocked_at"]:
        return "blocked"
    if row["revoked_at"]:
        return "revoked"
    return "active" if row["valid_until"] > now else "expired"


def _client_meta(client: dict[str, Any]) -> str:
    parts = []
    for key in ("essid", "ap_mac", "radio", "channel", "signal"):
        if client.get(key) is not None:
            parts.append(f"{key}: {client[key]}")
    return "<br>".join(html.escape(str(part)) for part in parts)


def _traffic(client: dict[str, Any]) -> str:
    rx = _first_int(client, "rx_bytes", "bytes-r", "wired-rx_bytes", "rx_bytes-r")
    tx = _first_int(client, "tx_bytes", "bytes-t", "wired-tx_bytes", "tx_bytes-r")
    if rx is None and tx is None:
        return ""
    return f"RX {_bytes(rx or 0)}<br>TX {_bytes(tx or 0)}"


def _first_int(client: dict[str, Any], *keys: str) -> Optional[int]:
    for key in keys:
        value = client.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def _bytes(value: int) -> str:
    amount = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if amount < 1024 or unit == "TB":
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{value} B"


def _dt(value) -> str:
    if not value:
        return ""
    return datetime.fromtimestamp(int(value)).strftime("%Y-%m-%d %H:%M")


def _tabs(lang: str, active_tab: str) -> str:
    active = "class='active'" if active_tab == "active" else ""
    archive = "class='active'" if active_tab == "archive" else ""
    return f"""
    <nav class="tabs">
      <a href="./?lang={html.escape(lang)}" {active}>{_t(lang, "active")}</a>
      <a href="archive?lang={html.escape(lang)}" {archive}>{_t(lang, "archive")}</a>
    </nav>
    """


def _layout(title: str, content: str, active_tab: str, lang: str) -> str:
    ru_active = "class='active'" if lang == "ru" else ""
    en_active = "class='active'" if lang == "en" else ""
    return f"""
    <!doctype html>
    <html lang="{html.escape(lang)}">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link rel="icon" href="logo">
        <title>{html.escape(title)} - SMS Gateway Admin</title>
        <script>
          const savedTheme = localStorage.getItem("sms-theme");
          const initialTheme = savedTheme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
          document.documentElement.dataset.theme = initialTheme;
        </script>
        <style>
          :root {{ --primary: #03a9f4; --primary-dark: #0391d1; --bg: #f2f4f7; --surface: #fff; --surface-2: #f7f9fb; --text: #212121; --muted: #6b7280; --divider: #e1e5e9; --danger: #db4437; --success: #43a047; --shadow: 0 2px 8px rgba(0,0,0,.09); --radius: 12px; }}
          * {{ box-sizing: border-box; }}
          html {{ color-scheme: light; }}
          body {{ margin: 0; min-height: 100vh; font-family: Roboto, Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; background: var(--bg); color: var(--text); font-size: 14px; }}
          header {{ position: sticky; top: 0; z-index: 20; min-height: 64px; display: flex; justify-content: space-between; align-items: center; gap: 20px; padding: 10px max(20px, calc((100vw - 1280px) / 2)); background: var(--surface); border-bottom: 1px solid var(--divider); box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
          .brand {{ display: flex; align-items: center; gap: 12px; min-width: 0; }}
          .brand-mark {{ width: 40px; height: 40px; display: grid; place-items: center; flex: 0 0 auto; border-radius: 50%; background: #53bd00; color: #fff; font-size: 18px; font-weight: 900; letter-spacing: -2px; }}
          header h1 {{ margin: 0; font-size: 18px; font-weight: 500; line-height: 1.2; }}
          .brand p {{ margin: 3px 0 0; color: var(--muted); font-size: 12px; }}
          .header-controls, .language, .table-tools, .value-actions, .muted-line {{ display: flex; align-items: center; gap: 8px; }}
          .language {{ padding: 3px; border-radius: 10px; background: var(--surface-2); border: 1px solid var(--divider); }}
          .language a, .tabs a {{ color: var(--muted); text-decoration: none; font-weight: 600; }}
          .language a {{ min-width: 32px; padding: 6px 8px; border-radius: 7px; font-size: 11px; text-align: center; }}
          .language a.active {{ color: #fff; background: var(--primary); }}
          main {{ max-width: 1280px; margin: 0 auto; padding: 24px 20px 48px; }}
          .dashboard-grid {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(360px, .72fr); gap: 20px; align-items: start; margin-bottom: 20px; }}
          .ha-card {{ min-width: 0; margin: 0 0 20px; overflow: hidden; border: 1px solid var(--divider); border-radius: var(--radius); background: var(--surface); box-shadow: var(--shadow); }}
          .dashboard-grid .ha-card {{ margin-bottom: 0; }}
          .card-heading {{ display: flex; align-items: center; gap: 14px; padding: 18px 20px 14px; }}
          .card-heading h2 {{ margin: 0; font-size: 18px; font-weight: 500; }}
          .card-heading p {{ margin: 4px 0 0; color: var(--muted); line-height: 1.4; }}
          .card-icon {{ width: 42px; height: 42px; display: grid; place-items: center; flex: 0 0 auto; border-radius: 50%; background: rgba(3,169,244,.13); color: var(--primary); }}
          .card-icon svg {{ width: 23px; height: 23px; fill: currentColor; }}
          .card-content {{ padding: 4px 20px 20px; }}
          form.settings, form.test-sms {{ display: grid; gap: 16px; }}
          .field {{ display: grid; gap: 7px; color: var(--muted); font-size: 12px; font-weight: 500; }}
          .field > span {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; }}
          .field small {{ margin: 0; font-weight: 400; }}
          input, textarea {{ width: 100%; min-height: 44px; border: 1px solid #aeb7c0; border-radius: 8px; padding: 10px 12px; background: var(--surface); color: var(--text); font: inherit; outline: none; transition: border-color .15s, box-shadow .15s; }}
          textarea {{ min-height: 88px; resize: vertical; line-height: 1.45; }}
          input:focus, textarea:focus {{ border-color: var(--primary); box-shadow: 0 0 0 2px rgba(3,169,244,.18); }}
          input[type=file] {{ position: absolute; width: 1px; height: 1px; min-height: 0; opacity: 0; pointer-events: none; }}
          .logo-picker {{ display: flex; align-items: center; gap: 12px; width: max-content; max-width: 100%; cursor: pointer; }}
          .logo-preview {{ width: 62px; height: 62px; display: grid; place-items: center; overflow: hidden; flex: 0 0 auto; border: 2px solid var(--divider); border-radius: 12px; background: var(--surface-2); transition: border-color .15s, transform .15s; }}
          .logo-picker:hover .logo-preview {{ border-color: var(--primary); transform: translateY(-1px); }}
          .logo-preview img {{ width: 100%; height: 100%; display: block; object-fit: contain; padding: 5px; }}
          .logo-copy {{ display: grid; gap: 2px; color: var(--text); }}
          .logo-copy small {{ margin: 0; color: var(--muted); font-weight: 400; }}
          .card-actions {{ display: flex; justify-content: flex-end; padding-top: 2px; }}
          button, .secondary-button {{ min-height: 38px; display: inline-flex; align-items: center; justify-content: center; gap: 7px; border: 0; border-radius: 8px; padding: 0 14px; font: inherit; font-weight: 500; cursor: pointer; text-decoration: none; transition: background .15s, border-color .15s, transform .08s; }}
          button:active, .secondary-button:active {{ transform: translateY(1px); }}
          .primary-button {{ min-width: 112px; background: var(--primary); color: #fff; }}
          .primary-button:hover {{ background: var(--primary-dark); }}
          .secondary-button, .actions button {{ border: 1px solid var(--divider); background: var(--surface); color: var(--primary); }}
          .secondary-button:hover, .actions button:hover {{ background: rgba(3,169,244,.09); border-color: rgba(3,169,244,.45); }}
          button.danger {{ border: 1px solid rgba(219,68,55,.35); background: transparent; color: var(--danger); }}
          button.danger:hover {{ background: rgba(219,68,55,.1); }}
          .section-head {{ justify-content: space-between; padding-bottom: 14px; border-bottom: 1px solid var(--divider); }}
          .section-title {{ display: flex; align-items: center; gap: 14px; min-width: 0; }}
          .table-heading {{ flex-wrap: wrap; }}
          .tabs {{ display: inline-flex; gap: 3px; padding: 3px; border-radius: 10px; background: var(--surface-2); border: 1px solid var(--divider); }}
          .tabs a {{ padding: 7px 12px; border-radius: 7px; font-size: 13px; }}
          .tabs a.active {{ color: #fff; background: var(--primary); }}
          .table-toolbar {{ display: flex; align-items: center; gap: 12px; padding: 14px 20px; }}
          .search-field {{ position: relative; flex: 1 1 320px; max-width: 520px; }}
          .search-field svg {{ position: absolute; left: 12px; top: 50%; width: 20px; height: 20px; transform: translateY(-50%); fill: var(--muted); pointer-events: none; }}
          .search-field input {{ padding-left: 40px; background: var(--surface-2); }}
          .result-count {{ margin-left: auto; color: var(--muted); white-space: nowrap; font-size: 12px; }}
          .refresh-button svg {{ width: 18px; height: 18px; fill: currentColor; }}
          .table-scroll {{ overflow-x: auto; border-top: 1px solid var(--divider); }}
          table {{ width: 100%; border-collapse: collapse; background: var(--surface); }}
          th, td {{ padding: 13px 14px; border-bottom: 1px solid var(--divider); text-align: left; vertical-align: middle; font-size: 13px; }}
          th {{ background: var(--surface-2); color: var(--muted); font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .035em; white-space: nowrap; }}
          tbody tr:hover {{ background: rgba(3,169,244,.045); }}
          tbody tr:last-child td {{ border-bottom: 0; }}
          .active-table {{ min-width: 1080px; table-layout: fixed; }}
          .active-table .col-client {{ width: 17%; }} .active-table .col-phone {{ width: 16%; }} .active-table .col-ip {{ width: 8%; }} .active-table .col-date {{ width: 12%; }} .active-table .col-extend {{ width: 17%; }} .active-table .col-action {{ width: 9%; }}
          small {{ display: block; color: var(--muted); margin-top: 3px; }}
          .muted-line {{ justify-content: flex-start; gap: 5px; }}
          .muted-line small {{ margin: 0; }}
          .value-actions {{ flex-wrap: wrap; }}
          .icon-button {{ width: 28px; min-height: 28px; padding: 0; border: 0; border-radius: 50%; background: transparent; color: var(--muted); }}
          .icon-button:hover {{ background: rgba(3,169,244,.1); color: var(--primary); }}
          .text-button {{ min-height: 28px; padding: 0 8px; border: 0; background: transparent; color: var(--primary); }}
          .text-button:hover {{ background: rgba(3,169,244,.1); }}
          .actions, .actions form {{ display: flex; flex-wrap: wrap; gap: 6px; }}
          .actions button {{ min-height: 32px; padding: 0 9px; white-space: nowrap; }}
          .client-display {{ min-height: 0; padding: 0; border: 0; background: transparent; color: var(--text); font-weight: 500; text-align: left; }}
          .client-display:hover {{ color: var(--primary); background: transparent; }}
          .client-name input {{ width: 170px; min-height: 34px; padding: 6px 8px; }}
          .notice {{ display: flex; align-items: center; gap: 10px; margin: 0 0 18px; padding: 12px 14px; border-radius: 10px; font-weight: 500; box-shadow: var(--shadow); }}
          .notice-icon {{ width: 24px; height: 24px; display: grid; place-items: center; border-radius: 50%; background: currentColor; color: #fff; }}
          .success {{ border: 1px solid rgba(67,160,71,.3); background: #edf7ee; color: #2e7d32; }}
          .error {{ border: 1px solid rgba(219,68,55,.3); background: #fff0ef; color: #c62828; }}
          .empty {{ padding: 40px 20px; color: var(--muted); text-align: center; }}
          .empty strong {{ display: block; margin-bottom: 5px; color: var(--text); font-size: 15px; font-weight: 500; }}
          .badge {{ display: inline-flex; padding: 5px 9px; border-radius: 999px; background: #e6e9ed; font-weight: 600; font-size: 11px; text-transform: capitalize; }}
          .badge.active {{ background: #e6f4ea; color: #188038; }} .badge.revoked {{ background: #fef7e0; color: #b06000; }} .badge.blocked {{ background: #fce8e6; color: #c5221f; }}
          .export-button {{ white-space: nowrap; }}
          .theme-toggle {{ width: 38px; min-height: 38px; padding: 0; border: 1px solid var(--divider); border-radius: 50%; background: var(--surface); color: var(--muted); }}
          .theme-toggle:hover {{ background: var(--surface-2); color: var(--primary); }}
          .theme-toggle svg {{ width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }}
          .moon-icon {{ display: none; }}
          .toast {{ position: fixed; right: 20px; bottom: 20px; z-index: 50; padding: 11px 16px; border-radius: 8px; background: #323232; color: #fff; box-shadow: 0 5px 20px rgba(0,0,0,.28); opacity: 0; transform: translateY(12px); pointer-events: none; transition: opacity .2s, transform .2s; }}
          .toast.visible {{ opacity: 1; transform: translateY(0); }}
          dialog {{ width: min(420px, calc(100vw - 32px)); border: 0; border-radius: 14px; padding: 0; background: var(--surface); color: var(--text); box-shadow: 0 18px 60px rgba(0,0,0,.35); }}
          dialog::backdrop {{ background: rgba(0,0,0,.45); }}
          .dialog-content {{ padding: 22px; }} .dialog-content h2 {{ margin: 0 0 8px; font-size: 20px; font-weight: 500; }} .dialog-content p {{ margin: 0; color: var(--muted); line-height: 1.5; }} .dialog-actions {{ display: flex; justify-content: flex-end; gap: 8px; padding: 12px 18px; border-top: 1px solid var(--divider); }}
          [hidden] {{ display: none !important; }}
          [data-theme="dark"] {{ color-scheme: dark; --bg: #11151a; --surface: #1c1f23; --surface-2: #24282d; --text: #e5e7eb; --muted: #a1a7af; --divider: #343a40; --shadow: 0 2px 8px rgba(0,0,0,.35); }}
          [data-theme="dark"] .success {{ background: #17351f; color: #81c995; }} [data-theme="dark"] .error {{ background: #401c1b; color: #f28b82; }}
          [data-theme="dark"] input, [data-theme="dark"] textarea {{ border-color: #59616a; }}
          [data-theme="dark"] .sun-icon {{ display: none; }} [data-theme="dark"] .moon-icon {{ display: block; }}
          @media (max-width: 900px) {{ .dashboard-grid {{ grid-template-columns: 1fr; }} main {{ padding: 16px 12px 36px; }} header {{ padding: 10px 14px; }} .brand p {{ display: none; }} .table-heading {{ align-items: flex-start; }} .table-tools {{ flex-wrap: wrap; }} }}
          @media (max-width: 640px) {{ .card-heading {{ padding: 16px; }} .card-content {{ padding: 2px 16px 16px; }} .table-toolbar {{ flex-wrap: wrap; padding: 12px 16px; }} .search-field {{ flex-basis: 100%; max-width: none; }} .result-count {{ margin-left: 0; }} .refresh-button {{ margin-left: auto; }} .section-title .card-icon {{ display: none; }} .table-heading {{ gap: 12px; }} .table-tools {{ width: 100%; justify-content: space-between; }} .language {{ display: none; }} .active-table {{ min-width: 0; table-layout: auto; }} .active-table colgroup, .active-table thead {{ display: none; }} .active-table tbody {{ display: grid; gap: 12px; padding: 12px; background: var(--bg); }} .active-table tr {{ display: block; overflow: hidden; border: 1px solid var(--divider); border-radius: 10px; background: var(--surface); }} .active-table td {{ display: grid; grid-template-columns: 110px 1fr; gap: 12px; align-items: start; width: 100%; padding: 11px 12px; white-space: normal !important; }} .active-table td::before {{ content: attr(data-label); color: var(--muted); font-size: 11px; font-weight: 600; text-transform: uppercase; }} }}
        </style>
      </head>
      <body>
        <header>
          <div class="brand">
            <span class="brand-mark" aria-hidden="true">wb</span>
            <div><h1>SMS Gateway</h1><p>{_t(lang, "subtitle")}</p></div>
          </div>
          <div class="header-controls">
            <div class="language"><a href="?lang=ru" {ru_active}>RU</a><a href="?lang=en" {en_active}>EN</a></div>
            <button id="theme-toggle" class="theme-toggle" type="button" title="{_t(lang, 'theme')}" aria-label="{_t(lang, 'theme')}">
              <svg class="sun-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.66 6.34l1.41-1.41"></path></svg>
              <svg class="moon-icon" viewBox="0 0 24 24"><path d="M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5 8.5 8.5 0 1 0 20.5 14.2Z"></path></svg>
            </button>
          </div>
        </header>
        <main>{content}</main>
        <div id="toast" class="toast" role="status" aria-live="polite"></div>
        <dialog id="confirm-dialog">
          <div class="dialog-content"><h2>{_t(lang, "confirm_title")}</h2><p>{_t(lang, "confirm_text")}</p></div>
          <div class="dialog-actions">
            <button id="confirm-cancel" class="secondary-button" type="button">{_t(lang, "cancel")}</button>
            <button id="confirm-submit" class="danger" type="button">{_t(lang, "confirm")}</button>
          </div>
        </dialog>
        <script>
          const logoInput = document.getElementById("logo-file");
          const logoPreview = document.getElementById("logo-preview");
          if (logoInput && logoPreview) {{
            logoInput.addEventListener("change", () => {{
              if (logoInput.files.length) logoPreview.src = URL.createObjectURL(logoInput.files[0]);
            }});
          }}
          document.getElementById("theme-toggle").addEventListener("click", () => {{
            const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
            document.documentElement.dataset.theme = next;
            localStorage.setItem("sms-theme", next);
          }});
          const toast = document.getElementById("toast");
          let toastTimer;
          function showToast(message) {{
            toast.textContent = message;
            toast.classList.add("visible");
            clearTimeout(toastTimer);
            toastTimer = setTimeout(() => toast.classList.remove("visible"), 1800);
          }}
          document.querySelectorAll(".copy-button").forEach((button) => {{
            button.addEventListener("click", async () => {{
              try {{
                await navigator.clipboard.writeText(button.dataset.copy);
                showToast("{_t(lang, 'copied')}");
              }} catch (_) {{
                const helper = document.createElement("textarea");
                helper.value = button.dataset.copy;
                document.body.appendChild(helper);
                helper.select();
                document.execCommand("copy");
                helper.remove();
                showToast("{_t(lang, 'copied')}");
              }}
            }});
          }});
          const smsPhone = document.getElementById("sms-phone");
          const smsMessage = document.getElementById("sms-message");
          const messageCounter = document.getElementById("message-counter");
          function updateMessageCounter() {{
            if (smsMessage && messageCounter) messageCounter.textContent = `${{smsMessage.value.length}} / 1000 {_t(lang, 'characters')}`;
          }}
          if (smsMessage) smsMessage.addEventListener("input", updateMessageCounter);
          updateMessageCounter();
          document.querySelectorAll(".sms-client-button").forEach((button) => {{
            button.addEventListener("click", () => {{
              if (!smsPhone) return;
              smsPhone.value = button.dataset.phone;
              document.querySelector(".sms-card").scrollIntoView({{ behavior: "smooth", block: "center" }});
              setTimeout(() => (smsMessage || smsPhone).focus(), 350);
            }});
          }});
          document.querySelectorAll("[data-filter-input]").forEach((input) => {{
            const tableName = input.dataset.filterInput;
            const table = document.querySelector(`[data-filter-table="${{tableName}}"]`);
            const counter = document.querySelector(`[data-result-count="${{tableName}}"]`);
            const rows = Array.from(table.querySelectorAll("[data-filter-row]"));
            const applyFilter = () => {{
              const query = input.value.trim().toLocaleLowerCase();
              let visible = 0;
              rows.forEach((row) => {{
                const matches = !query || row.dataset.search.includes(query);
                row.hidden = !matches;
                if (matches) visible += 1;
              }});
              counter.textContent = `{_t(lang, 'found')}: ${{visible}}`;
            }};
            input.addEventListener("input", applyFilter);
            applyFilter();
          }});
          document.querySelectorAll("[data-refresh]").forEach((button) => button.addEventListener("click", () => location.reload()));
          const confirmDialog = document.getElementById("confirm-dialog");
          let pendingForm = null;
          document.querySelectorAll("form[data-confirm]").forEach((form) => {{
            form.addEventListener("submit", (event) => {{
              event.preventDefault();
              pendingForm = form;
              confirmDialog.showModal();
            }});
          }});
          document.getElementById("confirm-cancel").addEventListener("click", () => {{ pendingForm = null; confirmDialog.close(); }});
          document.getElementById("confirm-submit").addEventListener("click", () => {{
            const form = pendingForm;
            pendingForm = null;
            confirmDialog.close();
            if (form) form.submit();
          }});
          document.querySelectorAll(".client-display").forEach((display) => {{
            display.addEventListener("click", () => {{
              const form = display.parentElement.querySelector(".client-name");
              display.hidden = true;
              form.hidden = false;
              const input = form.querySelector("input[name=display_name]");
              input.dataset.original = input.value;
              input.focus();
              input.select();
              input.addEventListener("blur", () => {{
                if (input.value !== input.dataset.original) form.requestSubmit();
                else {{ form.hidden = true; display.hidden = false; }}
              }}, {{ once: true }});
            }});
          }});
        </script>
      </body>
    </html>
    """
