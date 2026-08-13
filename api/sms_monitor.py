from __future__ import annotations

import hashlib
import logging
import threading
from datetime import datetime
from typing import Optional

from paho.mqtt import client as mqtt

from .config import Settings
from .store import Store

LOGGER = logging.getLogger(__name__)


class WBSmsMonitor:
    """Record the delivery result published by send_sms.js on Wiren Board."""

    FIELDS = (
        "last_sent_time",
        "last_message_text",
        "last_recipient_number",
        "last_result",
    )

    def __init__(self, settings: Settings, store: Store) -> None:
        self.settings = settings
        self.store = store
        self._values: dict[str, str] = {}
        self._result_pending = False
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if settings.wb_mqtt_username:
            password = (
                settings.wb_mqtt_password.get_secret_value()
                if settings.wb_mqtt_password
                else None
            )
            self._client.username_pw_set(settings.wb_mqtt_username, password)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

    @property
    def topic_root(self) -> str:
        suffix = "/send/on"
        topic = self.settings.wb_sms_topic.rstrip("/")
        return topic[: -len(suffix)] if topic.endswith(suffix) else topic.rsplit("/", 2)[0]

    def start(self) -> None:
        self._client.connect_async(
            self.settings.wb_mqtt_host,
            self.settings.wb_mqtt_port,
            keepalive=30,
        )
        self._client.loop_start()

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
        self._client.disconnect()
        self._client.loop_stop()

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code != 0:
            LOGGER.warning("WB SMS monitor MQTT connection failed: %s", reason_code)
            return
        for field in self.FIELDS:
            client.subscribe(f"{self.topic_root}/{field}", qos=1)

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties) -> None:
        if reason_code != 0:
            LOGGER.warning("WB SMS monitor disconnected: %s", reason_code)

    def _on_message(self, client, userdata, message) -> None:
        field = message.topic.rsplit("/", 1)[-1]
        self.handle_value(field, message.payload.decode("utf-8", errors="replace"))

    def handle_value(self, field: str, value: str) -> None:
        if field not in self.FIELDS:
            return
        with self._lock:
            self._values[field] = value.strip()
            # The timestamp is unique for every attempt, while a successful
            # result can remain the same and therefore may not emit a changed
            # MQTT value. Debounce briefly so the remaining last_* fields can
            # arrive before the row is written.
            if field == "last_sent_time":
                self._result_pending = True
            if self._result_pending:
                if self._timer is not None:
                    self._timer.cancel()
                self._timer = threading.Timer(0.25, self._record_pending_result)
                self._timer.daemon = True
                self._timer.start()

    def _record_pending_result(self) -> None:
        with self._lock:
            if not self._result_pending or not all(
                self._values.get(field) for field in self.FIELDS
            ):
                return
            phone = self._values["last_recipient_number"]
            message = self._values["last_message_text"]
            result = self._values["last_result"]
            sent_time = self._values["last_sent_time"]
            self._result_pending = False
        event_key = hashlib.sha256(
            "\x1f".join((sent_time, phone, message, result)).encode("utf-8")
        ).hexdigest()
        failed = result.casefold().startswith(("ошибка", "error"))
        self.store.record_sms(
            phone=phone,
            message=message,
            backend="wb",
            status="failed" if failed else "sent",
            error=result if failed else None,
            created_at=_parse_timestamp(sent_time),
            event_key=event_key,
        )


def _parse_timestamp(value: str) -> Optional[int]:
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
    except (TypeError, ValueError):
        return None
