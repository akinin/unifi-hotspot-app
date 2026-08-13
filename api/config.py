from functools import lru_cache
import os
from pathlib import Path
from typing import Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    api_token: Optional[SecretStr] = None
    app_secret: SecretStr = Field(default=SecretStr("change-me"))
    app_host: str = "0.0.0.0"
    app_port: int = 8088
    app_role: str = "api"
    database_path: str = "./data/sms_gateway.sqlite3"
    settings_file_path: str = ".env"

    wb_mqtt_host: str = "127.0.0.1"
    wb_mqtt_port: int = 1883
    wb_mqtt_username: Optional[str] = None
    wb_mqtt_password: Optional[SecretStr] = None
    wb_sms_topic: str = "/devices/sms_sender/controls/send/on"

    sms_backend: str = "mqtt"
    mmcli_modem_id: str = "any"

    unifi_base_url: Optional[str] = None
    unifi_api_key: Optional[SecretStr] = None
    unifi_username: Optional[str] = None
    unifi_password: Optional[SecretStr] = None
    unifi_site: str = "default"
    unifi_verify_tls: bool = False
    unifi_auth_minutes: int = 1440
    unifi_dry_run: bool = False

    hotspot_portal_port: int = 8880
    hotspot_admin_port: int = 8089
    hotspot_portal_title: str = "Welcome to Olshaniki"
    hotspot_background_color: str = "#10141b"
    hotspot_logo_size: int = 132
    hotspot_logo_path: str = "./data/hotspot_logo.png"

    hotspot_access_log_path: str = "./data/hotspot_access.csv"
    telegram_bot_token: Optional[SecretStr] = None
    telegram_chat_id: Optional[str] = None

    otp_ttl_seconds: int = 300
    otp_length: int = 6
    otp_resend_seconds: int = 60
    otp_max_attempts: int = 5
    otp_message_template: str = "Your Wi-Fi code: {code}"


@lru_cache(maxsize=8)
def _settings_for_file(path: str, modified_ns: int) -> Settings:
    return Settings(_env_file=path)


def get_settings() -> Settings:
    path = os.environ.get("SETTINGS_FILE_PATH", ".env")
    try:
        modified_ns = Path(path).stat().st_mtime_ns
    except FileNotFoundError:
        modified_ns = 0
    return _settings_for_file(path, modified_ns)


get_settings.cache_clear = _settings_for_file.cache_clear
