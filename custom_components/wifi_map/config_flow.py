"""Config flow for WiFi Position Map."""
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
import voluptuous as vol
from .manifest import DOMAIN  # noqa


class WiFiMapConfigFlow(config_entries.ConfigFlow, domain="wifi_map"):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="WiFi Position Map", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Optional("room_width_m", default=10.0): float,
                vol.Optional("room_height_m", default=8.0): float,
            })
        )
