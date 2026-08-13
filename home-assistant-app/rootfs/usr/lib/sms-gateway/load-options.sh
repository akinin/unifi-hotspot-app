#!/usr/bin/with-contenv bash

export API_TOKEN="$(bashio::config 'api_token')"
export SMS_BACKEND="$(bashio::config 'sms_backend')"
export MMCLI_MODEM_ID="$(bashio::config 'mmcli_modem_id')"
export WB_MQTT_HOST="$(bashio::config 'wb_mqtt_host')"
export WB_MQTT_PORT="$(bashio::config 'wb_mqtt_port')"
export WB_MQTT_USERNAME="$(bashio::config 'wb_mqtt_username')"
export WB_MQTT_PASSWORD="$(bashio::config 'wb_mqtt_password')"
export WB_SMS_TOPIC="$(bashio::config 'wb_sms_topic')"
export UNIFI_DRY_RUN="$(bashio::config 'unifi_dry_run')"
export UNIFI_BASE_URL="$(bashio::config 'unifi_base_url')"
export UNIFI_API_KEY="$(bashio::config 'unifi_api_key')"
export UNIFI_USERNAME="$(bashio::config 'unifi_username')"
export UNIFI_PASSWORD="$(bashio::config 'unifi_password')"
export UNIFI_SITE="$(bashio::config 'unifi_site')"
export UNIFI_VERIFY_TLS="$(bashio::config 'unifi_verify_tls')"
export UNIFI_AUTH_MINUTES="$(bashio::config 'unifi_auth_minutes')"
configured_portal_title="$(bashio::config 'hotspot_portal_title')"
export TELEGRAM_BOT_TOKEN="$(bashio::config 'telegram_bot_token')"
export TELEGRAM_CHAT_ID="$(bashio::config 'telegram_chat_id')"
export OTP_TTL_SECONDS="$(bashio::config 'otp_ttl_seconds')"
export OTP_LENGTH="$(bashio::config 'otp_length')"
export OTP_RESEND_SECONDS="$(bashio::config 'otp_resend_seconds')"
export OTP_MAX_ATTEMPTS="$(bashio::config 'otp_max_attempts')"

export APP_HOST=0.0.0.0
export DATABASE_PATH=/data/sms_gateway.sqlite3
export SETTINGS_FILE_PATH=/data/runtime.env
export HOTSPOT_ACCESS_LOG_PATH=/data/hotspot_access.csv
if [[ ! -e "${SETTINGS_FILE_PATH}" ]]; then
    safe_portal_title="${configured_portal_title//$'\n'/ }"
    printf 'HOTSPOT_PORTAL_TITLE=%s\nHOTSPOT_LOGO_PATH=/data/hotspot_logo.png\n' \
        "${safe_portal_title//$'\r'/ }" > "${SETTINGS_FILE_PATH}"
fi

configured_secret="$(bashio::config 'app_secret')"
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
if bashio::config.true 'unifi_dry_run'; then
    bashio::log.warning "UniFi dry-run is enabled; no client authorization state will be changed"
fi
if [[ "${SMS_BACKEND}" == "mmcli" ]]; then
    bashio::log.info "USB ModemManager SMS backend selected (modem: ${MMCLI_MODEM_ID})"
else
    bashio::log.info "Wiren Board MQTT SMS backend selected"
fi
