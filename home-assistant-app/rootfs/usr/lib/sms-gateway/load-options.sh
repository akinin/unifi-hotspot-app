#!/usr/bin/with-contenv bash

# Version 0.6 groups related settings in the Home Assistant UI. Migrate the
# previous flat options once, preserving every user value.
options_json="$(bashio::addon.options)"
if bashio::jq.exists "${options_json}" '.sms_backend'; then
    bashio::log.info "Migrating application settings to grouped configuration"
    bashio::addon.option 'security' "^$(bashio::jq "${options_json}" '{api_token: (.api_token // ""), app_secret: (.app_secret // "")}')"
    bashio::addon.option 'sms' "^$(bashio::jq "${options_json}" '{backend: (.sms_backend // "mqtt")}')"
    bashio::addon.option 'wirenboard' "^$(bashio::jq "${options_json}" '{mqtt_host: (.wb_mqtt_host // "10.10.100.5"), mqtt_port: (.wb_mqtt_port // 1884), mqtt_username: (.wb_mqtt_username // ""), mqtt_password: (.wb_mqtt_password // ""), sms_topic: (.wb_sms_topic // "/devices/sms_sender/controls/send/on")}')"
    bashio::addon.option 'usb' "^$(bashio::jq "${options_json}" '{modem_id: (.mmcli_modem_id // "any")}')"
    bashio::addon.option 'unifi' "^$(bashio::jq "${options_json}" '{dry_run: (.unifi_dry_run // true), base_url: (.unifi_base_url // ""), api_key: (.unifi_api_key // ""), username: (.unifi_username // ""), password: (.unifi_password // ""), site: (.unifi_site // "default"), verify_tls: (.unifi_verify_tls // false), auth_minutes: (.unifi_auth_minutes // 1440)}')"
    bashio::addon.option 'portal' "^$(bashio::jq "${options_json}" '{title: (.hotspot_portal_title // "Welcome to Olshaniki"), background_color: (.hotspot_background_color // "#10141b"), logo_size: (.hotspot_logo_size // 132)}')"
    bashio::addon.option 'telegram' "^$(bashio::jq "${options_json}" '{bot_token: (.telegram_bot_token // ""), chat_id: (.telegram_chat_id // "")}')"
    bashio::addon.option 'otp' "^$(bashio::jq "${options_json}" '{ttl_seconds: (.otp_ttl_seconds // 300), length: (.otp_length // 6), resend_seconds: (.otp_resend_seconds // 60), max_attempts: (.otp_max_attempts // 5)}')"

    for old_key in \
        api_token app_secret sms_backend mmcli_modem_id \
        wb_mqtt_host wb_mqtt_port wb_mqtt_username wb_mqtt_password wb_sms_topic \
        unifi_dry_run unifi_base_url unifi_api_key unifi_username unifi_password \
        unifi_site unifi_verify_tls unifi_auth_minutes hotspot_portal_title \
        hotspot_background_color hotspot_logo_size telegram_bot_token \
        telegram_chat_id otp_ttl_seconds otp_length otp_resend_seconds otp_max_attempts; do
        bashio::addon.option "${old_key}"
    done
fi

export API_TOKEN="$(bashio::config 'security.api_token')"
export SMS_BACKEND="$(bashio::config 'sms.backend')"
export MMCLI_MODEM_ID="$(bashio::config 'usb.modem_id')"
export WB_MQTT_HOST="$(bashio::config 'wirenboard.mqtt_host')"
export WB_MQTT_PORT="$(bashio::config 'wirenboard.mqtt_port')"
export WB_MQTT_USERNAME="$(bashio::config 'wirenboard.mqtt_username')"
export WB_MQTT_PASSWORD="$(bashio::config 'wirenboard.mqtt_password')"
export WB_SMS_TOPIC="$(bashio::config 'wirenboard.sms_topic')"
export UNIFI_DRY_RUN="$(bashio::config 'unifi.dry_run')"
export UNIFI_BASE_URL="$(bashio::config 'unifi.base_url')"
export UNIFI_API_KEY="$(bashio::config 'unifi.api_key')"
export UNIFI_USERNAME="$(bashio::config 'unifi.username')"
export UNIFI_PASSWORD="$(bashio::config 'unifi.password')"
export UNIFI_SITE="$(bashio::config 'unifi.site')"
export UNIFI_VERIFY_TLS="$(bashio::config 'unifi.verify_tls')"
configured_auth_minutes="$(bashio::config 'unifi.auth_minutes')"
configured_portal_title="$(bashio::config 'portal.title')"
configured_background_color="$(bashio::config 'portal.background_color')"
configured_logo_size="$(bashio::config 'portal.logo_size')"
export TELEGRAM_BOT_TOKEN="$(bashio::config 'telegram.bot_token')"
export TELEGRAM_CHAT_ID="$(bashio::config 'telegram.chat_id')"
export OTP_TTL_SECONDS="$(bashio::config 'otp.ttl_seconds')"
export OTP_LENGTH="$(bashio::config 'otp.length')"
export OTP_RESEND_SECONDS="$(bashio::config 'otp.resend_seconds')"
export OTP_MAX_ATTEMPTS="$(bashio::config 'otp.max_attempts')"

export APP_HOST=0.0.0.0
export DATABASE_PATH=/data/sms_gateway.sqlite3
export SETTINGS_FILE_PATH=/data/runtime.env
export HOTSPOT_ACCESS_LOG_PATH=/data/hotspot_access.csv
if [[ ! -e "${SETTINGS_FILE_PATH}" ]]; then
    safe_portal_title="${configured_portal_title//$'\n'/ }"
    printf 'HOTSPOT_PORTAL_TITLE=%s\nHOTSPOT_BACKGROUND_COLOR=%s\nHOTSPOT_LOGO_SIZE=%s\nHOTSPOT_LOGO_PATH=/data/hotspot_logo.png\nUNIFI_AUTH_MINUTES=%s\n' \
        "${safe_portal_title//$'\r'/ }" "${configured_background_color}" "${configured_logo_size}" "${configured_auth_minutes}" > "${SETTINGS_FILE_PATH}"
elif ! grep -q '^UNIFI_AUTH_MINUTES=' "${SETTINGS_FILE_PATH}"; then
    printf 'UNIFI_AUTH_MINUTES=%s\n' "${configured_auth_minutes}" >> "${SETTINGS_FILE_PATH}"
fi

configured_secret="$(bashio::config 'security.app_secret')"
if [[ -n "${configured_secret}" ]]; then
    export APP_SECRET="${configured_secret}"
else
    if [[ ! -s /data/app_secret ]]; then
        python3 -c 'import secrets; print(secrets.token_urlsafe(48))' > /data/app_secret
        chmod 600 /data/app_secret
    fi
    export APP_SECRET="$(tr -d '\r\n' < /data/app_secret)"
fi

if [[ -z "${API_TOKEN}" ]]; then
    bashio::log.warning "API token is empty; protected HTTP API methods remain unavailable"
fi
if bashio::config.true 'unifi.dry_run'; then
    bashio::log.warning "UniFi dry-run is enabled; no client authorization state will be changed"
fi
if [[ "${SMS_BACKEND}" == "mmcli" ]]; then
    bashio::log.info "USB ModemManager SMS backend selected (modem: ${MMCLI_MODEM_ID})"
else
    bashio::log.info "Wiren Board MQTT SMS backend selected"
fi
