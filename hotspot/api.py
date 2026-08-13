from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.config import Settings, get_settings
from api.deps import get_store, require_api_token
from api.store import Store

from .audit import build_access_event, record_access_event
from .store import HotspotStore
from .unifi import UniFiClient, UniFiClientNotFoundError


router = APIRouter(
    prefix="/api/unifi",
    dependencies=[Depends(require_api_token)],
)


class PortalUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class ExtendRequest(BaseModel):
    days: int = Field(ge=1, le=365)


def _hotspot_store(store: Store) -> HotspotStore:
    return HotspotStore(store)


@router.get("/status")
async def status(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    configured = bool(
        settings.unifi_base_url
        and (
            settings.unifi_api_key
            or (settings.unifi_username and settings.unifi_password)
        )
    )
    reachable = False
    error = None
    if configured:
        try:
            await UniFiClient(settings).list_clients()
            reachable = True
        except Exception as exc:
            error = str(exc)
    return {
        "configured": configured,
        "reachable": reachable,
        "error": error,
        "dry_run": settings.unifi_dry_run,
        "controller": settings.unifi_base_url,
        "site": settings.unifi_site,
        "auth_minutes": settings.unifi_auth_minutes,
        "credentials": "api_key" if settings.unifi_api_key else "local_account",
    }


@router.get("/portal")
def portal(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    return {
        "title": settings.hotspot_portal_title,
        "logo_url": "/admin/logo",
    }


@router.put("/portal")
def update_portal(
    payload: PortalUpdate,
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Portal title must not be empty")
    _set_env_value(Path(settings.settings_file_path), "HOTSPOT_PORTAL_TITLE", title)
    get_settings.cache_clear()
    return {"ok": True, "title": title}


@router.get("/clients")
async def active_clients(
    settings: Settings = Depends(get_settings),
    store: Store = Depends(get_store),
) -> dict[str, object]:
    sessions = _hotspot_store(store).list_active_sessions()
    try:
        clients = await UniFiClient(settings).list_clients()
    except Exception as exc:
        clients = []
        unifi_error = str(exc)
    else:
        unifi_error = None
    by_mac = {
        str(client.get("mac", "")).lower(): client
        for client in clients
        if client.get("mac")
    }
    items = []
    for session in sessions:
        mac = str(session["client_mac"]).lower()
        client = by_mac.get(mac, {})
        items.append(
            {
                "mac": mac,
                "name": session["display_name"] or client.get("name") or client.get("hostname"),
                "phone": session["phone"],
                "ip": client.get("ip"),
                "authorized_at": session["authorized_at"],
                "valid_until": session["valid_until"],
                "ap_mac": session["ap_mac"],
            }
        )
    return {"count": len(items), "clients": items, "unifi_error": unifi_error}


@router.get("/archive")
def archive(
    limit: int = 200,
    store: Store = Depends(get_store),
) -> dict[str, object]:
    safe_limit = min(max(limit, 1), 1000)
    now = int(time.time())
    items = []
    for row in _hotspot_store(store).list_archive(limit=safe_limit):
        status_value = "blocked" if row["blocked_at"] else "revoked" if row["revoked_at"] else "active" if row["valid_until"] > now else "expired"
        items.append(
            {
                "id": row["id"],
                "mac": row["client_mac"],
                "name": row["display_name"],
                "phone": row["phone"],
                "authorized_at": row["authorized_at"],
                "valid_until": row["valid_until"],
                "minutes": row["minutes"],
                "status": status_value,
            }
        )
    return {"count": len(items), "items": items}


@router.post("/clients/{client_mac}/extend")
async def extend_client(
    client_mac: str,
    payload: ExtendRequest,
    settings: Settings = Depends(get_settings),
    store: Store = Depends(get_store),
) -> dict[str, object]:
    hotspot_store = _hotspot_store(store)
    session = hotspot_store.get_session(client_mac.lower())
    if session is None:
        raise HTTPException(status_code=404, detail="Client was not found")
    now = int(time.time())
    remaining_minutes = max(0, int(session["valid_until"] or now) - now) // 60
    minutes = remaining_minutes + payload.days * 24 * 60
    try:
        await UniFiClient(settings).authorize_guest(
            client_mac,
            minutes=minutes,
            ap_mac=session["ap_mac"],
        )
    except UniFiClientNotFoundError:
        pass
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    authorized_at = hotspot_store.mark_authorized(client_mac.lower(), minutes)
    updated = hotspot_store.get_session(client_mac.lower())
    record_access_event(
        settings,
        build_access_event(
            settings,
            client_mac.lower(),
            updated["phone"],
            authorized_at,
            updated["valid_until"],
        ),
    )
    return {"ok": True, "valid_until": updated["valid_until"]}


@router.post("/clients/{client_mac}/revoke")
async def revoke_client(
    client_mac: str,
    settings: Settings = Depends(get_settings),
    store: Store = Depends(get_store),
) -> dict[str, bool]:
    try:
        await UniFiClient(settings).unauthorize_guest(client_mac)
    except UniFiClientNotFoundError:
        pass
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    _hotspot_store(store).clear_authorized(client_mac.lower())
    return {"ok": True}


@router.post("/clients/{client_mac}/block")
async def block_client(
    client_mac: str,
    settings: Settings = Depends(get_settings),
    store: Store = Depends(get_store),
) -> dict[str, bool]:
    try:
        await UniFiClient(settings).block_client(client_mac)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    _hotspot_store(store).mark_blocked(client_mac.lower(), "Blocked from Home Assistant")
    return {"ok": True}


def _set_env_value(path: Path, key: str, value: str) -> None:
    safe_value = value.replace("\r", " ").replace("\n", " ").strip()
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    prefix = f"{key}="
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = f"{prefix}{safe_value}"
            break
    else:
        lines.append(f"{prefix}{safe_value}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
