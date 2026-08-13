ARG BUILD_FROM=ghcr.io/home-assistant/base:3.23
FROM ${BUILD_FROM}

WORKDIR /opt/sms-gateway
COPY requirements.txt ./requirements.txt
RUN apk add --no-cache py3-pip python3 \
    && python3 -m pip install --no-cache-dir --break-system-packages \
        -r requirements.txt

COPY api ./api
COPY hotspot ./hotspot
COPY home-assistant-app/rootfs /

ENV PYTHONPATH=/opt/sms-gateway
ENTRYPOINT ["/init"]

LABEL \
    org.opencontainers.image.title="Home Assistant App: Wiren Board SMS Gateway" \
    org.opencontainers.image.description="SMS API and UniFi hotspot portal through Wiren Board" \
    org.opencontainers.image.source="https://github.com/akinin/wirenboard-sms"
