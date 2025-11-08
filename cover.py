import logging

from homeassistant.components import mqtt
from homeassistant.components.cover import CoverEntity, CoverEntityFeature, ATTR_POSITION 
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_CLOSED, STATE_OPEN

from .const import (
    DOMAIN, 
    CONF_MQTT_TOPIC_COMMAND, 
    CONF_CAR_UNIQUE_ID,
    CONF_MQTT_TOPIC_SUBSCRIBE, 
    DEFAULT_SUNROOF_POS_SUBTOPIC,
    # BYD_UPDATE_EVENT is no longer needed here
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
):
    """Set up the BYD Car Sunroof Blind entity."""
    
    config_data = hass.data[DOMAIN][config_entry.entry_id]
    
    command_topic = config_data.get(CONF_MQTT_TOPIC_COMMAND)
    base_status_topic = config_data.get(CONF_MQTT_TOPIC_SUBSCRIBE)
    car_unique_id = config_data.get(CONF_CAR_UNIQUE_ID)
    
    if not command_topic or not car_unique_id:
        _LOGGER.warning("MQTT Command topic or Car Unique ID is missing. Sunroof Blind control disabled.")
        return

    # Status topic is constructed: /dolphinc/sunroof/position
    status_topic = f"{base_status_topic.rstrip('/')}/{DEFAULT_SUNROOF_POS_SUBTOPIC}"
    
    model_name_base = config_entry.title.lower().replace("byd ", "").strip().replace(" ", "_")
    model_name_title = config_entry.title.replace("BYD ", "").strip().capitalize()
    
    async_add_entities([
        BYDSunroofBlind(
            hass, 
            config_entry.entry_id, 
            command_topic, 
            status_topic,
            car_unique_id, 
            model_name_base, 
            model_name_title
        )
    ], True)


class BYDSunroofBlind(CoverEntity):
    """Representation of the BYD Car Sunroof Blind."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN | 
        CoverEntityFeature.CLOSE | 
        CoverEntityFeature.SET_POSITION |
        CoverEntityFeature.STOP
    )
    
    def __init__(self, hass, entry_id, command_topic, status_topic, car_unique_id, model_name_base, model_name_title):
        """Initialize the cover entity."""
        self._hass = hass
        self._command_topic = command_topic
        self._status_topic = status_topic
        self._car_unique_id = car_unique_id
        # Position is 0 (closed) to 100 (open)
        self._current_position = 0 
        self._context = None 
        # self._sunroof_open_status attribute REMOVED
        
        # Home Assistant properties
        self._attr_unique_id = f"{DOMAIN}_{model_name_base}_sunroof_blind"
        self._attr_name = f"BYD {model_name_title} Sunroof Blind"
        self._attr_icon = "mdi:blinds"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": f"BYD {model_name_title}",
            "manufacturer": "BYD",
            "model": model_name_title,
        }
    
    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of the cover (0-100)."""
        return self._current_position

    @property
    def is_closed(self) -> bool | None:
        """Return true if cover is closed."""
        if self._current_position is None:
            return None
        return self._current_position == 0

    # extra_state_attributes property REMOVED
    
    async def async_open_cover(self, **kwargs) -> None:
        """Open the cover (set position to 100)."""
        await self._send_cover_command("开遮阳帘")
        self._current_position = 100
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs) -> None:
        """Close the cover (set position to 0)."""
        await self._send_cover_command("关遮阳帘")
        self._current_position = 0
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs) -> None:
        """Stop the cover's current action."""
        await self._send_cover_command("开遮阳帘")
        self.async_write_ha_state()

    async def async_set_cover_position(self, cover_position: int = 0, **kwargs) -> None:
        """Move the cover to a specific position (0-100)."""
        
        target_position = kwargs.get(ATTR_POSITION, cover_position)
        
        position_to_send = max(0, min(100, target_position))
        
        payload_command = f"开遮阳帘{position_to_send}%"
        
        await self._send_cover_command(payload_command)
        self._current_position = position_to_send
        self.async_write_ha_state()

    async def _send_cover_command(self, action_string: str) -> None:
        """Helper to send the MQTT command."""
        
        model_part = self._attr_device_info['name'] 
        
        # Payload format: BYD Dolphin=1734645381137联动=ACTION
        payload = f"{model_part}={self._car_unique_id}联动={action_string}"

        _LOGGER.debug("Publishing Sunroof Blind command: Topic: %s, Payload: %s", self._command_topic, payload)

        await self._hass.services.async_call(
            mqtt.DOMAIN, "publish", 
            {"topic": self._command_topic, "payload": payload, "qos": 0, "retain": False},
            blocking=True, context=self._context
        )


    async def async_added_to_hass(self):
        """Subscribe to the MQTT status topic when the entity is added."""
        
        # NOTE: The BYD_UPDATE_EVENT subscription for sunroof_open has been removed 
        # as it is now handled by the binary_sensor.py

        @callback
        def mqtt_message_received(message):
            """Handle new MQTT messages received on the status topic."""
            try:
                # The payload is expected to be a simple string representing percentage: "80"
                new_position = int(message.payload)
                if 0 <= new_position <= 100:
                    self._current_position = new_position
                    self.async_write_ha_state()
                else:
                    _LOGGER.warning("Received Sunroof position %s is outside the range [0, 100]", new_position)
            except ValueError:
                _LOGGER.error("Received non-numeric payload on %s: %s", self._status_topic, message.payload)

        # Subscribe to the dedicated status topic: /dolphinc/sunroof/position
        self.async_on_remove(
            await mqtt.async_subscribe(self._hass, self._status_topic, mqtt_message_received, qos=0)
        )