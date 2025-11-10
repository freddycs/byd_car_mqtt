import logging

from homeassistant.components import mqtt
from homeassistant.components.number import NumberEntity, NumberDeviceClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature 

from .const import (
    DOMAIN, 
    CONF_MQTT_TOPIC_COMMAND, 
    CONF_CAR_UNIQUE_ID,
    CONF_MQTT_TOPIC_SUBSCRIBE, 
    DEFAULT_AC_TEMP_STATUS_SUBTOPIC
)

_LOGGER = logging.getLogger(__name__)

# Constants for the A/C Temperature range
TEMP_MIN = 17
TEMP_MAX = 33
TEMP_STEP = 1

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
):
    """Set up the BYD Car A/C Temperature Number entity."""
    
    config_data = hass.data[DOMAIN][config_entry.entry_id]
    
    command_topic = config_data.get(CONF_MQTT_TOPIC_COMMAND)
    base_status_topic = config_data.get(CONF_MQTT_TOPIC_SUBSCRIBE)
    car_unique_id = config_data.get(CONF_CAR_UNIQUE_ID)
    
    if not command_topic or not car_unique_id:
        _LOGGER.warning("MQTT Command topic or Car Unique ID is missing. A/C Temp control disabled.")
        return

    # Status topic is constructed from the base status topic + subtopic
    status_topic = f"{base_status_topic.rstrip('/')}/{DEFAULT_AC_TEMP_STATUS_SUBTOPIC}"
    
    model_name_base = config_entry.title.lower().replace("byd ", "").strip().replace(" ", "_")
    model_name_title = config_entry.title.replace("BYD ", "").strip().capitalize()
    
    async_add_entities([
        BYDCarACTempNumber(
            hass, 
            config_entry.entry_id, 
            command_topic, 
            status_topic,
            car_unique_id, 
            model_name_base, 
            model_name_title
        )
    ], True)


class BYDCarACTempNumber(NumberEntity):
    """Representation of the BYD Car A/C Temperature Setting."""

    def __init__(self, hass, entry_id, command_topic, status_topic, car_unique_id, model_name_base, model_name_title):
        """Initialize the number entity."""
        self._hass = hass
        self._command_topic = command_topic
        self._status_topic = status_topic
        self._car_unique_id = car_unique_id
        self._current_temp = TEMP_MIN # Default to minimum temp

        # Home Assistant properties
        self._attr_device_class = NumberDeviceClass.TEMPERATURE
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_native_min_value = TEMP_MIN
        self._attr_native_max_value = TEMP_MAX
        self._attr_native_step = TEMP_STEP
        
        self._attr_unique_id = f"{DOMAIN}_{model_name_base}_ac_temp_set"
        self._attr_name = f"BYD {model_name_title} A/C Target Temp"
        self._attr_icon = "mdi:thermometer"
        
        # We need the entry_id for device info linking and the device name for the payload
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": f"BYD {model_name_title}",
            "manufacturer": "BYD",
            "model": model_name_title,
        }
        
    @property
    def native_value(self) -> float | None:
        """Return the current A/C temperature setting."""
        return self._current_temp

    async def async_added_to_hass(self):
        """Subscribe to the MQTT status topic when the entity is added."""
        @callback
        def mqtt_message_received(message):
            """Handle new MQTT messages received on the /actemp topic."""
            try:
                # The payload is expected to be a simple string like "24"
                new_temp = float(message.payload)
                if TEMP_MIN <= new_temp <= TEMP_MAX:
                    self._current_temp = new_temp
                    self.async_write_ha_state()
                else:
                    _LOGGER.warning("Received A/C temp %s is outside the range [%s, %s]", new_temp, TEMP_MIN, TEMP_MAX)
            except ValueError:
                _LOGGER.error("Received non-numeric payload on %s: %s", self._status_topic, message.payload)

        # Subscribe to the dedicated status topic: /dolphinc/actemp
        self.async_on_remove(
            await mqtt.async_subscribe(self._hass, self._status_topic, mqtt_message_received, qos=0)
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set the new A/C target temperature and publish via MQTT."""
        
        # 1. Define the integer temperature value
        temp_int = int(round(value))
        
        if not (TEMP_MIN <= temp_int <= TEMP_MAX):
            _LOGGER.error("Attempted to set A/C temp outside range: %s", temp_int)
            return

        # 2. Get the Model Name from device info (e.g., "BYD Dolphin")
        model_part = self._attr_device_info['name'] 

        # 3. Build the EXACT MQTT command payload 
        # e.g., BYD Dolphin=1734645381137联动=温度:30
        payload = f"{model_part}={self._car_unique_id}联动=温度:{temp_int}"

        _LOGGER.debug("Publishing A/C temp command: Topic: %s, Payload: %s", self._command_topic, payload)

        # 4. Publish the command using the literal service name "publish"
        await self._hass.services.async_call(
            mqtt.DOMAIN, 
            "publish", # <-- FINAL FIX: Using literal service name
            {
                "topic": self._command_topic,
                "payload": payload,
                "qos": 0,
                "retain": False,
            },
            blocking=True,
            context=self._context
        )
        
        # 5. Optimistically update the state
        self._current_temp = temp_int
        self.async_write_ha_state()
