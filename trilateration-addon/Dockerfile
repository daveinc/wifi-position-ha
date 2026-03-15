ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip py3-numpy py3-scipy

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --break-system-packages -r requirements.txt

COPY trilaterate.py .
COPY server.py .

# s6-overlay service definition
COPY rootfs /
