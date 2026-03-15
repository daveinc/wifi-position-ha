"""
WiFi Position Tracker — Main Server
Listens to ESP32 anchor MQTT topics, runs trilateration,
pushes X/Y to Home Assistant, serves live map dashboard.
"""

import asyncio
import json
import logging
from typing import Optional

import paho.mqtt.client as mqtt
from aiohttp import web

from trilaterate import Trilaterator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

OPTIONS_FILE = "/data/options.json"

def load_options() -> dict:
    try:
        with open(OPTIONS_FILE) as f:
            return json.load(f)
    except Exception:
        return {
            "mqtt_host": "core-mosquitto",
            "mqtt_port": 1883,
            "mqtt_user": "",
            "mqtt_password": "",
            "anchor_count": 4,
            "update_interval_ms": 100,
            "room_width_m": 10.0,
            "room_height_m": 8.0
        }

OPTIONS = load_options()

ANCHOR_TOPIC = "wifi_position/anchor/+/rssi"
POSITION_TOPIC = "wifi_position/position"
HA_DISCOVERY_PREFIX = "homeassistant"

trilaterator = Trilaterator(
    room_width=OPTIONS["room_width_m"],
    room_height=OPTIONS["room_height_m"]
)
latest_position: Optional[dict] = None
connected_clients: set = set()


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Connected to MQTT broker")
        client.subscribe(ANCHOR_TOPIC)
        client.subscribe("wifi_position/anchor/+/config")
        publish_ha_discovery(client)
    else:
        logger.error(f"MQTT connection failed: rc={rc}")


def on_message(client, userdata, msg):
    global latest_position
    topic = msg.topic
    try:
        payload = json.loads(msg.payload.decode())
    except Exception:
        payload = msg.payload.decode()

    if topic.endswith("/config"):
        node_id = topic.split("/")[2]
        if isinstance(payload, dict) and "x" in payload and "y" in payload:
            trilaterator.add_anchor(node_id, float(payload["x"]), float(payload["y"]))
        return

    if "/rssi" in topic:
        node_id = topic.split("/")[2]
        rssi = payload.get("rssi", payload) if isinstance(payload, dict) else float(payload)
        trilaterator.update_rssi(node_id, float(rssi))
        position = trilaterator.compute_position()
        if position:
            latest_position = position
            client.publish(POSITION_TOPIC, json.dumps(position), retain=True)
            client.publish(f"{HA_DISCOVERY_PREFIX}/sensor/wifi_position_x/state", str(position["x"]))
            client.publish(f"{HA_DISCOVERY_PREFIX}/sensor/wifi_position_y/state", str(position["y"]))
            client.publish(f"{HA_DISCOVERY_PREFIX}/sensor/wifi_position_confidence/state", str(position["confidence"]))
            asyncio.run_coroutine_threadsafe(broadcast_position(position), asyncio.get_event_loop())


def publish_ha_discovery(client):
    sensors = [
        {"slug": "wifi_position_x", "name": "WiFi Position X", "unit": "m", "icon": "mdi:map-marker"},
        {"slug": "wifi_position_y", "name": "WiFi Position Y", "unit": "m", "icon": "mdi:map-marker"},
        {"slug": "wifi_position_confidence", "name": "WiFi Position Confidence", "unit": "%", "icon": "mdi:crosshairs-gps"},
    ]
    for s in sensors:
        config = {
            "name": s["name"],
            "state_topic": f"{HA_DISCOVERY_PREFIX}/sensor/{s['slug']}/state",
            "unit_of_measurement": s["unit"],
            "icon": s["icon"],
            "unique_id": s["slug"],
            "device": {
                "identifiers": ["wifi_position_tracker"],
                "name": "WiFi Position Tracker",
                "model": "ESP32 CSI",
                "manufacturer": "Espressif / daveinc"
            }
        }
        client.publish(f"{HA_DISCOVERY_PREFIX}/sensor/{s['slug']}/config", json.dumps(config), retain=True)
    logger.info("HA discovery messages published")


async def broadcast_position(position: dict):
    if not connected_clients:
        return
    msg = json.dumps(position)
    dead = set()
    for ws in connected_clients:
        try:
            await ws.send_str(msg)
        except Exception:
            dead.add(ws)
    connected_clients.difference_update(dead)


async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    connected_clients.add(ws)
    try:
        async for msg in ws:
            pass
    finally:
        connected_clients.discard(ws)
    return ws


async def dashboard_handler(request):
    room_w = OPTIONS["room_width_m"]
    room_h = OPTIONS["room_height_m"]
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>WiFi Position Tracker</title>
<style>
  body {{ margin: 0; background: #111; color: #eee; font-family: monospace; display: flex; flex-direction: column; align-items: center; padding: 20px; }}
  h1 {{ color: #4af; }}
  #map-container {{ position: relative; border: 2px solid #4af; background: #1a1a2e; }}
  #beacon {{ position: absolute; width: 16px; height: 16px; background: #4af; border-radius: 50%; transform: translate(-50%, -50%); box-shadow: 0 0 12px #4af; transition: left 0.1s, top 0.1s; }}
  #stats {{ margin-top: 12px; font-size: 14px; color: #aaa; }}
</style>
</head>
<body>
<h1>📡 WiFi Position Tracker</h1>
<div id="map-container" style="width:600px;height:{int(600 * room_h / room_w)}px">
  <div id="beacon" style="left:50%;top:50%"></div>
</div>
<div id="stats">Waiting for data...</div>
<script>
  const RW = {room_w}, RH = {room_h};
  const MAP_W = 600, MAP_H = {int(600 * room_h / room_w)};
  const beacon = document.getElementById('beacon');
  const stats = document.getElementById('stats');
  const ws = new WebSocket(`ws://${{location.host}}/ws`);
  ws.onmessage = (e) => {{
    const d = JSON.parse(e.data);
    beacon.style.left = (d.x / RW * MAP_W) + 'px';
    beacon.style.top = ((1 - d.y / RH) * MAP_H) + 'px';
    stats.textContent = `X: ${{d.x}}m  Y: ${{d.y}}m  Confidence: ${{d.confidence}}%  Anchors: ${{d.active_anchors}}`;
  }};
</script>
</body>
</html>"""
    return web.Response(text=html, content_type="text/html")


async def position_api(request):
    if latest_position:
        return web.json_response(latest_position)
    return web.json_response({"error": "no position data yet"}, status=503)


async def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    if OPTIONS.get("mqtt_user"):
        client.username_pw_set(OPTIONS["mqtt_user"], OPTIONS["mqtt_password"])
    client.connect(OPTIONS["mqtt_host"], OPTIONS["mqtt_port"], keepalive=60)
    client.loop_start()

    app = web.Application()
    app.router.add_get("/", dashboard_handler)
    app.router.add_get("/ws", websocket_handler)
    app.router.add_get("/api/position", position_api)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8099)
    await site.start()
    logger.info("WiFi Position Tracker running on port 8099")

    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        client.loop_stop()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
