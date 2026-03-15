# ESP32 Firmware Notes

## Based on Espressif esp-csi (Apache 2.0)
## https://github.com/espressif/esp-csi

## Which example to use
The `examples/esp-radar/console_test` is the best base for anchor nodes.
It includes Espressif's own filtering algorithms and outputs clean RSSI + CSI data.

## What each node needs to publish (via MQTT)

### On boot — register anchor position:
Topic:   wifi_position/anchor/<node_id>/config
Payload: {"x": 0.0, "y": 0.0}

### Every 100ms — RSSI reading from beacon:
Topic:   wifi_position/anchor/<node_id>/rssi  
Payload: {"rssi": -65}

## Recommended anchor placement for a rectangular room
- Anchor A: (0, 0)          — bottom-left corner
- Anchor B: (width, 0)      — bottom-right corner
- Anchor C: (width, height) — top-right corner
- Anchor D: (0, height)     — top-left corner

4 anchors gives redundancy — trilateration still works if one has a bad reading.

## Supported chips (all support CSI)
- ESP32-S3 ✅ best — highest CSI data density
- ESP32-C6 ✅ great — newer, good range
- ESP32-C3 ✅ good
- ESP32 original ✅ works

## Beacon (carried by person)
Any ESP32 broadcasting WiFi packets.
ESP32-C3 Mini recommended — coin-sized, USB-C, ~$4.
