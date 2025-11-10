"""The component setup file for BYD Car MQTT integration."""
import logging
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
import homeassistant.components.mqtt as mqtt
from homeassistant.const import Platform

# Import local modules
from .const import (
    DOMAIN, 
    BYD_UPDATE_EVENT, 
    # Use the more explicit name for the subscribe topic
    CONF_MQTT_TOPIC_SUBSCRIBE, # ⬅️ Assuming this is the correct constant for the subscribe topic
    CONF_MQTT_TOPIC_COMMAND,   # ⬅️ NEW
    CONF_CAR_UNIQUE_ID,        # ⬅️ NEW
    PLATFORMS
)
from .parsing_logic import parse_byd_payload 

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BYD Car MQTT from a config entry."""
    
    # Store the component's global data (including configuration)
    hass.data.setdefault(DOMAIN, {})
    
    # -----------------------------------------------------------------
    # 1. Retrieve and Store Configuration Data
    # -----------------------------------------------------------------
    
    # Get the subscription topic from the UI configuration (using the corrected key)
    mqtt_topic_subscribe = entry.data.get(CONF_MQTT_TOPIC_SUBSCRIBE)
    mqtt_topic_command = entry.data.get(CONF_MQTT_TOPIC_COMMAND) # ⬅️ NEW
    car_unique_id = entry.data.get(CONF_CAR_UNIQUE_ID)           # ⬅️ NEW
    
    # Store all necessary configuration for other platforms (like fan.py) to access
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_MQTT_TOPIC_SUBSCRIBE: mqtt_topic_subscribe,
        CONF_MQTT_TOPIC_COMMAND: mqtt_topic_command,
        CONF_CAR_UNIQUE_ID: car_unique_id,
        "parsed_data": {} # Initial status data store
    }
    
    _LOGGER.debug("Starting BYD Car MQTT integration for topic: %s", mqtt_topic_subscribe)

    # -----------------------------------------------------------------
    # 2. Define the MQTT Message Handler Callback
    # -----------------------------------------------------------------
    @callback
    def mqtt_message_received(message):
        """Handle new MQTT messages received on the configured topic."""
        raw_payload = message.payload
        
        # --- Safely decode payload ---
        if isinstance(raw_payload, bytes):
            try:
                raw_payload = raw_payload.decode("utf-8")
            except UnicodeDecodeError:
                _LOGGER.error("Failed to decode MQTT payload as UTF-8.")
                return

        if not isinstance(raw_payload, str):
            _LOGGER.warning("MQTT payload received was not a string, ignoring.")
            return

        try:
            parsed_data = parse_byd_payload(raw_payload)
            
            # Use car_status check for better detection of a valid payload
            if parsed_data.get("car_status") is not None: 
                _LOGGER.debug("Parsed data: %s", parsed_data)
                
                # Fire the custom event with the clean data for all sensors to listen to
                hass.bus.async_fire(BYD_UPDATE_EVENT, parsed_data)
            else:
                _LOGGER.debug("Payload received but key data not found/parsed.")
                
        except Exception as err:
            _LOGGER.error("Error processing MQTT message: %s", err)

    # -----------------------------------------------------------------
    # 3. Subscribe to the MQTT Topic
    # -----------------------------------------------------------------
    # Use the subscribe topic variable
    entry.async_on_unload(
        await mqtt.async_subscribe(hass, mqtt_topic_subscribe, mqtt_message_received, qos=0)
    )

    # -----------------------------------------------------------------
    # 4. Forward Setup to All Platforms (including the new 'fan' platform)
    # -----------------------------------------------------------------
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry. Unloading platforms first."""
    
    # Unload platforms (sensor, binary_sensor, fan)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # MQTT subscription cleanup is handled automatically by entry.async_on_unload
    
    # Clean up stored data
    if unload_ok and entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
