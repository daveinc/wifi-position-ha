"""WiFi Position Map sensors — X, Y coordinates + confidence."""
from __future__ import annotations

import json
import logging
from homeassistant.components import mqtt
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)

POSITION_TOPIC = "wifi_position/position"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    sensors = [
        WiFiPositionSensor("x", "WiFi Position X", "m", "mdi:map-marker-radius"),
        WiFiPositionSensor("y", "WiFi Position Y", "m", "mdi:map-marker-radius"),
        WiFiPositionSensor("confidence", "WiFi Position Confidence", "%", "mdi:crosshairs-gps"),
        WiFiPositionSensor("active_anchors", "WiFi Active Anchors", None, "mdi:access-point-network"),
    ]
    async_add_entities(sensors)

    @callback
    def message_received(msg):
        try:
            payload = json.loads(msg.payload)
            for sensor in sensors:
                sensor.handle_update(payload)
        except Exception as e:
            _LOGGER.error(f"Position parse error: {e}")

    await mqtt.async_subscribe(hass, POSITION_TOPIC, message_received, 0)


class WiFiPositionSensor(SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_should_poll = False

    def __init__(self, field: str, name: str, unit: str | None, icon: str):
        self._field = field
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_unique_id = f"wifi_position_{field}"
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}

    def handle_update(self, payload: dict):
        if self._field in payload:
            self._attr_native_value = payload[self._field]
            if self._field == "x":
                self._attr_extra_state_attributes = {
                    "y": payload.get("y"),
                    "confidence": payload.get("confidence"),
                    "anchor_distances": payload.get("anchor_distances", {})
                }
            self.async_write_ha_state()
