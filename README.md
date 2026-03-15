# 📡 WiFi Position Tracker for Home Assistant

Real-time indoor positioning using ESP32 CSI/RSSI trilateration.  
Based on [Espressif esp-csi](https://github.com/espressif/esp-csi) (Apache 2.0).

Outputs live X/Y coordinates of a tracked person onto a floorplan map in Home Assistant.

---

## How It Works

```
ESP32 anchor nodes (fixed, corners of room)
        │  measure RSSI from beacon
        ▼
Trilateration Add-on (runs inside HA)
        │  weighted least squares + Kalman filter
        ▼
wifi_position/position  (MQTT)
        │
        ▼
Home Assistant sensors + live floorplan map
```

---

## Installation

### 1. Add-on (trilateration engine)
1. In HA → Settings → Add-ons → Add-on Store → ⋮ → Custom repositories
2. Add: `https://github.com/daveinc/wifi-position-ha`
3. Install **WiFi CSI Position Tracker**
4. Configure room dimensions and MQTT settings
5. Start

### 2. Custom Integration (HA sensors + map)
1. Install via HACS → Custom repositories → `https://github.com/daveinc/wifi-position-ha`
2. Settings → Integrations → Add → **WiFi Position Map**
3. Enter room dimensions

### 3. Floorplan Card
Add to your dashboard (Lovelace):
```yaml
type: picture-elements
image: /local/floorplan.png
elements:
  - type: state-icon
    entity: sensor.wifi_position_x
    style:
      left: >
        {{ (states('sensor.wifi_position_x') | float / ROOM_WIDTH * 100) }}%
      top: >
        {{ (100 - states('sensor.wifi_position_y') | float / ROOM_HEIGHT * 100) }}%
```

### 4. ESP32 Firmware
See [firmware-notes/FIRMWARE.md](firmware-notes/FIRMWARE.md)

---

## Hardware

| Role | Device | Cost |
|------|--------|------|
| Anchor nodes (×4) | Any ESP32 | ~$5 each |
| Beacon (carried) | ESP32-C3 Mini | ~$4 |

---

## License
Apache 2.0 — same as the upstream esp-csi project.
