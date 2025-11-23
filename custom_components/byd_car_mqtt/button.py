"""Button platform for the BYD Car MQTT integration."""
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN, 
    CONF_MQTT_TOPIC_COMMAND, 
    CONF_CAR_UNIQUE_ID,
    SERVICE_GET_DILAUNCHER_JSON,
    ATTR_OUTPUT_PATH,
    DEFAULT_OUTPUT_PATH
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
):
    """Set up the DiLauncher JSON generation button entity."""
    
    # We only need one button per integration instance
    async_add_entities([
        DiLauncherJsonButton(hass, config_entry)
    ])


class DiLauncherJsonButton(ButtonEntity):
    """Defines a button to trigger the DiLauncher JSON generation service."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        """Initialize the button."""
        self._hass = hass
        self._config_entry = config_entry
        
        # Device Info for the main BYD Device
        self._model_name_title = config_entry.data.get("model_name", "BYD Car")
        entry_id = config_entry.entry_id
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=f"BYD {self._model_name_title}", 
            manufacturer="BYD",
            model=self._model_name_title,
        )
        
        # Entity attributes
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_generate_dilauncher_json"
        self._attr_name = f"Generate DiLauncher Automations JSON"

    async def async_press(self) -> None:
        """Handle the button press. Calls the custom service."""
        _LOGGER.debug("DiLauncher JSON Button pressed. Calling service...")
        
        # Call the service registered in __init__.py
        await self._hass.services.async_call(
            DOMAIN, 
            SERVICE_GET_DILAUNCHER_JSON, 
            {ATTR_OUTPUT_PATH: DEFAULT_OUTPUT_PATH}, # Use the default path
            blocking=True, 
            context=self._context
        )
        _LOGGER.info("DiLauncher JSON generation service executed.")