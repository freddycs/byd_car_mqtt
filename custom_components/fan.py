import logging
from math import ceil 

from homeassistant.components import mqtt
from homeassistant.components.fan import FanEntity, FanEntityFeature 
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry

from .const import (
    DOMAIN, 
    CONF_MQTT_TOPIC_COMMAND, 
    CONF_CAR_UNIQUE_ID,
    CONF_MQTT_TOPIC_SUBSCRIBE, 
    DEFAULT_AC_FAN_SPEED_SUBTOPIC,
    # --- NEW IMPORTS for Ventilation ---
    DEFAULT_DRIVER_VENT_SUBTOPIC,
    DEFAULT_PASSENGER_VENT_SUBTOPIC,
    CONF_ENABLE_DRIVER_VENT,
    CONF_ENABLE_PASSENGER_VENT,
)

_LOGGER = logging.getLogger(__name__)

# Constants for the A/C Fan Speed range (0-7)
AC_FAN_MAX_VALUE = 7 
AC_FAN_MIN_VALUE = 0 
AC_FAN_OFF_VALUE = 0
AC_FAN_SPEED_COUNT = AC_FAN_MAX_VALUE 

# Constants for the Seat Ventilation range (0-2)
VENT_MAX_VALUE = 2 
VENT_MIN_VALUE = 0 
VENT_OFF_VALUE = 0
VENT_SPEED_COUNT = VENT_MAX_VALUE # Steps 1-2 (2 steps)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
):
    """Set up the BYD Car Fan entities (A/C and Seat Ventilation)."""
    
    config_data = hass.data[DOMAIN][config_entry.entry_id]
    
    command_topic = config_data.get(CONF_MQTT_TOPIC_COMMAND)
    base_status_topic = config_data.get(CONF_MQTT_TOPIC_SUBSCRIBE)
    car_unique_id = config_data.get(CONF_CAR_UNIQUE_ID)
    
    if not command_topic or not car_unique_id:
        _LOGGER.warning("MQTT Command topic or Car Unique ID is missing. Fan control disabled.")
        return

    model_name_base = config_entry.title.lower().replace("byd ", "").strip().replace(" ", "_")
    model_name_title = config_entry.title.replace("BYD ", "").strip().capitalize()
    
    entities = []

    # --- 1. A/C Fan Speed Entity (Existing Logic) ---
    ac_status_topic = f"{base_status_topic.rstrip('/')}/{DEFAULT_AC_FAN_SPEED_SUBTOPIC}"
    entities.append(
        BYDCarACFan(
            hass, config_entry.entry_id, command_topic, ac_status_topic,
            car_unique_id, model_name_base, model_name_title
        )
    )

    # --- 2. Driver Seat Ventilation Entity (New Logic) ---
    if config_data.get(CONF_ENABLE_DRIVER_VENT, True): # Default to True for existing setups
        driver_status_topic = f"{base_status_topic.rstrip('/')}/{DEFAULT_DRIVER_VENT_SUBTOPIC}"
        entities.append(
            BYDCarSeatVentilation(
                hass, config_entry.entry_id, command_topic, driver_status_topic,
                car_unique_id, model_name_base, model_name_title, "Driver"
            )
        )

    # --- 3. Passenger Seat Ventilation Entity (New Logic) ---
    if config_data.get(CONF_ENABLE_PASSENGER_VENT, True): # Default to True for existing setups
        passenger_status_topic = f"{base_status_topic.rstrip('/')}/{DEFAULT_PASSENGER_VENT_SUBTOPIC}"
        entities.append(
            BYDCarSeatVentilation(
                hass, config_entry.entry_id, command_topic, passenger_status_topic,
                car_unique_id, model_name_base, model_name_title, "Passenger"
            )
        )

    async_add_entities(entities, True)


class BYDCarACFan(FanEntity):
    """Representation of the BYD Car A/C Fan Speed Setting (0-7)."""

    _attr_supported_features = FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_OFF | FanEntityFeature.TURN_ON
    
    def __init__(self, hass, entry_id, command_topic, status_topic, car_unique_id, model_name_base, model_name_title):
        """Initialize the fan entity."""
        self._hass = hass
        self._command_topic = command_topic
        self._status_topic = status_topic
        self._car_unique_id = car_unique_id
        self._current_speed_value = AC_FAN_OFF_VALUE # Stored as 0-7 integer
        
        self._attr_speed_count = AC_FAN_SPEED_COUNT
        
        self._attr_unique_id = f"{DOMAIN}_{model_name_base}_ac_fan_set"
        self._attr_name = f"BYD {model_name_title} A/C Fan Speed"
        self._attr_icon = "mdi:fan"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": f"BYD {model_name_title}",
            "manufacturer": "BYD",
            "model": model_name_title,
        }
        # Required for the service call context
        self._context = None 
        
    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage (0-100) based on the 0-7 value."""
        if self._current_speed_value == AC_FAN_OFF_VALUE:
            return 0
            
        # Custom mapping: Speed value (1-7) / Max speed (7) * 100
        return int(round((self._current_speed_value / AC_FAN_MAX_VALUE) * 100))

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan speed as a percentage (0-100) and publish via MQTT."""
        
        # 1. Convert percentage (0-100) back to the car's 0-7 integer value.
        if percentage == 0:
            speed_value = AC_FAN_OFF_VALUE # 0
        else:
            # Custom mapping: Percentage / 100 * Max value (7)
            speed_value = int(ceil((percentage / 100) * AC_FAN_MAX_VALUE))
            # Safety clamp (should be 1-7)
            speed_value = max(AC_FAN_MIN_VALUE + 1, min(AC_FAN_MAX_VALUE, speed_value))

        await self._send_fan_command(speed_value)
    
    # FIX APPLIED HERE: Added preset_mode argument to match the required HA signature
    async def async_turn_on(self, percentage: int | None = None, preset_mode: str | None = None, **kwargs) -> None: 
        """Turn on the fan."""
        if percentage is None or percentage == 0:
            await self._send_fan_command(AC_FAN_MIN_VALUE + 1)
        else:
            await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the fan."""
        await self._send_fan_command(AC_FAN_OFF_VALUE)

    async def _send_fan_command(self, speed_value: int) -> None:
        """Helper to send the MQTT command for A/C Fan."""
        
        model_part = self._attr_device_info['name'] 
        payload = f"{model_part}={self._car_unique_id}联动=风量:{speed_value}"

        _LOGGER.debug("Publishing A/C fan speed command: Topic: %s, Payload: %s", self._command_topic, payload)

        await self._hass.services.async_call(
            mqtt.DOMAIN, "publish", 
            {"topic": self._command_topic, "payload": payload, "qos": 0, "retain": False},
            blocking=True, context=self._context
        )
        
        self._current_speed_value = speed_value
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Subscribe to the MQTT status topic when the entity is added."""
        @callback
        def mqtt_message_received(message):
            """Handle new MQTT messages received on the /fanspeed topic."""
            try:
                new_speed = int(message.payload)
                if AC_FAN_MIN_VALUE <= new_speed <= AC_FAN_MAX_VALUE:
                    self._current_speed_value = new_speed
                    self.async_write_ha_state()
                else:
                    _LOGGER.warning("Received A/C fan speed %s is outside the range [%s, %s]", new_speed, AC_FAN_MIN_VALUE, AC_FAN_MAX_VALUE)
            except ValueError:
                _LOGGER.error("Received non-numeric payload on %s: %s", self._status_topic, message.payload)

        self.async_on_remove(
            await mqtt.async_subscribe(self._hass, self._status_topic, mqtt_message_received, qos=0)
        )


class BYDCarSeatVentilation(BYDCarACFan):
    """Representation of the BYD Car Seat Ventilation Setting (0-2)."""
    
    # Override speed constants and names
    _attr_speed_count = VENT_SPEED_COUNT 

    def __init__(self, hass, entry_id, command_topic, status_topic, car_unique_id, model_name_base, model_name_title, seat_name):
        """Initialize the seat ventilation fan entity."""
        # Initialize the base Fan class without calling the base __init__ to set custom properties
        self._hass = hass
        self._command_topic = command_topic
        self._status_topic = status_topic
        self._car_unique_id = car_unique_id
        self._seat_name = seat_name # "Driver" or "Passenger"
        self._current_speed_value = VENT_OFF_VALUE # Stored as 0-2 integer
        self._context = None 

        # Home Assistant properties
        self._attr_speed_count = VENT_SPEED_COUNT
        self._attr_unique_id = f"{DOMAIN}_{model_name_base}_{seat_name.lower()}_vent_set"
        self._attr_name = f"BYD {model_name_title} {seat_name} Vent"
        self._attr_icon = "mdi:air-filter"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": f"BYD {model_name_title}",
            "manufacturer": "BYD",
            "model": model_name_title,
        }
    
    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage (0-100) based on the 0-2 value."""
        if self._current_speed_value == VENT_OFF_VALUE:
            return 0
            
        # Custom mapping: Speed value (1-2) / Max speed (2) * 100
        return int(round((self._current_speed_value / VENT_MAX_VALUE) * 100))

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan speed as a percentage (0-100) and publish via MQTT."""
        
        if percentage == 0:
            speed_value = VENT_OFF_VALUE # 0
        else:
            # Custom mapping: Percentage / 100 * Max value (2)
            speed_value = int(ceil((percentage / 100) * VENT_MAX_VALUE))
            # Safety clamp (should be 1 or 2)
            speed_value = max(VENT_MIN_VALUE + 1, min(VENT_MAX_VALUE, speed_value))

        await self._send_fan_command(speed_value)

    async def _send_fan_command(self, speed_value: int) -> None:
        """Helper to send the MQTT command for Seat Ventilation."""
        
        # Build the specialized payload command
        model_part = self._attr_device_info['name'] 
        payload_command = self._get_ventilation_payload(speed_value)
        
        payload = f"{model_part}={self._car_unique_id}联动={payload_command}"

        _LOGGER.debug("Publishing %s vent command: Topic: %s, Payload: %s", self._seat_name, self._command_topic, payload)

        await self._hass.services.async_call(
            mqtt.DOMAIN, "publish", 
            {"topic": self._command_topic, "payload": payload, "qos": 0, "retain": False},
            blocking=True, context=self._context
        )
        
        # Optimistically update the state
        self._current_speed_value = speed_value
        self.async_write_ha_state()

    def _get_ventilation_payload(self, speed_value: int) -> str:
        """Returns the specific Chinese command string for the given speed and seat."""
        
        seat = "主驾" if self._seat_name == "Driver" else "副驾"
        
        if speed_value == 0:
            return f"关{seat}" # e.g., 关主驾
        if speed_value == 1:
            return f"{seat}通风一档" # e.g., 主驾通风一档
        
        # Speed 2 (or anything greater than 1, as per your description)
        return f"{seat}通风" # e.g., 主驾通风 (implicitly means high speed)
        
    async def async_added_to_hass(self):
        """Subscribe to the MQTT status topic when the entity is added."""
        @callback
        def mqtt_message_received(message):
            """Handle new MQTT messages received on the /drivervent or /passengervent topic."""
            try:
                # The payload is expected to be a simple string like "1" or "2"
                new_speed = int(message.payload)
                if VENT_MIN_VALUE <= new_speed <= VENT_MAX_VALUE:
                    self._current_speed_value = new_speed
                    self.async_write_ha_state()
                else:
                    _LOGGER.warning("Received %s vent speed %s is outside the range [%s, %s]", self._seat_name, new_speed, VENT_MIN_VALUE, VENT_MAX_VALUE)
            except ValueError:
                _LOGGER.error("Received non-numeric payload on %s: %s", self._status_topic, message.payload)

        self.async_on_remove(
            await mqtt.async_subscribe(self._hass, self._status_topic, mqtt_message_received, qos=0)
        )
