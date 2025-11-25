"""The component setup file for BYD Car MQTT integration."""
import logging
import json 
from functools import partial
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
import homeassistant.components.mqtt as mqtt
from homeassistant.const import Platform
import voluptuous as vol
from datetime import datetime

# Import local modules
from .const import (
    DOMAIN, 
    BYD_UPDATE_EVENT, 
    CONF_MQTT_TOPIC_SUBSCRIBE,
    CONF_MQTT_TOPIC_COMMAND, 
    CONF_CAR_UNIQUE_ID,       
    PLATFORMS,
    # --- Subtopic Constants (NEWLY ADDED) ---
    DEFAULT_DRIVER_VENT_SUBTOPIC,
    DEFAULT_PASSENGER_VENT_SUBTOPIC,
    # --- Service Constants ---
    SERVICE_GET_DILAUNCHER_JSON,
    ATTR_OUTPUT_PATH,
    DEFAULT_OUTPUT_PATH
)
from .parsing_logic import parse_byd_payload 

_LOGGER = logging.getLogger(__name__)

# -----------------------------------------------------------------
# CUSTOM SERVICE DEFINITIONS
# -----------------------------------------------------------------

# Define the service schema for the DiLauncher JSON generation
SERVICE_DILAUNCHER_JSON_SCHEMA = vol.Schema({
    vol.Optional(
        ATTR_OUTPUT_PATH, 
        default=DEFAULT_OUTPUT_PATH
    ): str,
})

async def async_handle_get_dilauncher_json(hass: HomeAssistant, call):
    """
    Handles the service call to generate the complete DiLauncher Automations JSON file.
    
    Dynamically generates entries for AC Temp, Fan Speed, SOC, Speed, and Seat Ventilation.
    """
    output_path = call.data.get(ATTR_OUTPUT_PATH, DEFAULT_OUTPUT_PATH)
    
    # Get configuration data to use in JSON generation (using the first available entry)
    config_entry_id = next(iter(hass.data.get(DOMAIN, {})), None)
    if not config_entry_id or config_entry_id not in hass.data[DOMAIN]:
        _LOGGER.error("BYD Car MQTT is not configured. Cannot generate DiLauncher JSON.")
        return

    config_data = hass.data[DOMAIN][config_entry_id]
    # Ensure base_topic is clean for use in the MQTT runTask path
    base_topic = config_data.get(CONF_MQTT_TOPIC_SUBSCRIBE, "dolphinc").strip('/')
    
    # ------------------------------------------------------------
    # 1. Dynamic JSON Content Generation (Full Range)
    # ------------------------------------------------------------
    json_entries = []
    
    # Generate AC Temperature entries (17 to 33 inclusive)
    # taskType 54 = Climate Control Temperature
    for temp in range(17, 34): 
        json_entries.append({
            "name": f"AC temperature {temp}",
            "state": 1,
            "delayTime": 1,
            "runTask": f"MQTT:/{base_topic}/actemp+{temp}",
            "conditions": [{
                "taskType": 54,
                "compareType": 4,
                "expect": temp
            }]
        })

    # Generate Fan Speed entries (0 to 7 inclusive)
    # taskType 35 = Fan Speed
    for speed in range(0, 8):
        json_entries.append({
            "name": f"fan speed {speed}",
            "state": 1,
            "delayTime": 1,
            "runTask": f"MQTT:/{base_topic}/fanspeed+{speed}",
            "conditions": [{
                "taskType": 35,
                "compareType": 4,
                "expect": speed
            }]
        })
        
    # Generate State of Charge (SOC) entries (0 to 100 inclusive)
    # taskType 27 = State of Charge
    for soc in range(0, 101):
        json_entries.append({
            "name": f"soc{soc}",
            "state": 1,
            "delayTime": 1,
            "runTask": f"MQTT:/{base_topic}/SOC+{soc}",
            "conditions": [{
                "taskType": 27,
                "compareType": 4,
                "expect": soc
            }]
        })

    # Generate Speed entries (0 to 180 inclusive)
    # taskType 11 = Speed
    for speed in range(0, 181):
        json_entries.append({
            "name": f"speed{speed}",
            "state": 1,
            # Using 15 seconds delay as per your sample
            "delayTime": 15, 
            "runTask": f"MQTT:/{base_topic}/speed+{speed}",
            "conditions": [{
                "taskType": 11,
                "compareType": 4,
                "expect": speed
            }]
        })

    # --- NEW: Generate Driver Seat Ventilation entries (0=Off, 1=Low, 2=High) ---
    # taskType 21 = Driver Seat Ventilation
    VENT_LEVELS = {0: "off", 1: "low", 2: "high"}
    for level, name in VENT_LEVELS.items():
        delay = 1 # Using 1s for all driver vents as per your samples
        json_entries.append({
            "name": f"Driver ventilation {name}",
            "state": 1,
            "delayTime": delay, 
            "runDelayTime": 0,
            "runTask": f"MQTT:/{base_topic}/{DEFAULT_DRIVER_VENT_SUBTOPIC}+{level}",
            "conditions": [{
                "taskType": 21,
                "compareType": 4,
                "expect": level
            }]
        })

    # --- NEW: Generate Passenger Seat Ventilation entries (0=Off, 1=Low, 2=High) ---
    # taskType 22 = Passenger Seat Ventilation
    for level, name in VENT_LEVELS.items():
        # Using 10s delay only for passenger OFF, 1s for the rest, as per your samples
        delay = 10 if level == 0 else 1 
        json_entries.append({
            "name": f"passenger seat ventilation {name}",
            "state": 1,
            "delayTime": delay,
            "runDelayTime": 0,
            "runTask": f"MQTT:/{base_topic}/{DEFAULT_PASSENGER_VENT_SUBTOPIC}+{level}",
            "conditions": [{
                "taskType": 22,
                "compareType": 4,
                "expect": level
            }]
        })
    # ---------------------------------------------------------
    
    # Log total count for confirmation
    total_entries = len(json_entries)
    _LOGGER.info("Generated %d total DiLauncher automation entries (AC Temp, Fan Speed, SOC, Speed, Seat Ventilation).", total_entries)
        
    # ------------------------------------------------------------
    # 2. File Writing Logic (in executor thread)
    # ------------------------------------------------------------
    def write_file():
        """Synchronously writes the formatted JSON to the specified path, safely."""
        # Use hass.config.path() to resolve the path relative to the HA config folder.
        resolved_path = hass.config.path(output_path)
        
        _LOGGER.info("Attempting to write COMPLETE DiLauncher JSON to ABSOLUTE path: %s", resolved_path)
        
        try:
            # Write the formatted JSON to the file, using indent=4 for readability
            with open(resolved_path, "w", encoding="utf-8") as f:
                # We dump the list of dictionaries directly, ensuring proper JSON structure
                json.dump(json_entries, f, indent=4, ensure_ascii=False)
            
            _LOGGER.info("DiLauncher JSON successfully written to %s", output_path)
            
        except Exception as e:
            # Using _LOGGER.exception() is generally better for file I/O errors as it includes the stack trace.
            _LOGGER.exception("Failed to write DiLauncher JSON to %s (Absolute Path: %s): %s", output_path, resolved_path, e)
            
    # File I/O MUST be scheduled on the executor
    await hass.async_add_executor_job(write_file)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BYD Car MQTT from a config entry."""
    
    hass.data.setdefault(DOMAIN, {})
    
    # -----------------------------------------------------------------
    # 1. Retrieve and Store Configuration Data
    # -----------------------------------------------------------------
    
    mqtt_topic_subscribe = entry.data.get(CONF_MQTT_TOPIC_SUBSCRIBE)
    mqtt_topic_command = entry.data.get(CONF_MQTT_TOPIC_COMMAND) 
    car_unique_id = entry.data.get(CONF_CAR_UNIQUE_ID)
    
    # Store the essential data for platforms to access
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_MQTT_TOPIC_SUBSCRIBE: mqtt_topic_subscribe,
        CONF_MQTT_TOPIC_COMMAND: mqtt_topic_command,
        CONF_CAR_UNIQUE_ID: car_unique_id,
        # Pass through the rest of the configuration data
        **entry.data, 
        **entry.options
    }

    # -----------------------------------------------------------------
    # 2. Register Custom Service (DiLauncher JSON Generation)
    # -----------------------------------------------------------------
    
    # Use functools.partial to bind 'hass' to the first argument of the coroutine.
    service_handler_with_hass = partial(async_handle_get_dilauncher_json, hass)

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_DILAUNCHER_JSON,
        service_handler_with_hass,
        schema=SERVICE_DILAUNCHER_JSON_SCHEMA,
    )
    _LOGGER.debug("Registered custom service: %s.%s", DOMAIN, SERVICE_GET_DILAUNCHER_JSON)


    # -----------------------------------------------------------------
    # 3. Define the MQTT Message Handler
    # -----------------------------------------------------------------
    @callback
    def mqtt_message_received(message):
        """Handle new MQTT messages received on the status topic."""
        try:
            # Parse the raw text payload
            parsed_data = parse_byd_payload(message.payload)
            
            if parsed_data:
                _LOGGER.debug("Payload successfully parsed: %s", parsed_data)
                # Fire a Home Assistant event containing the parsed data
                hass.bus.async_fire(BYD_UPDATE_EVENT, parsed_data)
            else:
                _LOGGER.debug("Payload received but key data not found/parsed.")
                
        except Exception:
            # Use _LOGGER.exception() to log the full stack trace for better debugging
            _LOGGER.exception("Error processing MQTT message for topic: %s", message.topic)

    # -----------------------------------------------------------------
    # 4. Subscribe to the MQTT Topic
    # -----------------------------------------------------------------
    entry.async_on_unload(
        await mqtt.async_subscribe(hass, mqtt_topic_subscribe, mqtt_message_received, qos=0)
    )

    # -----------------------------------------------------------------
    # 5. Forward Setup to All Platforms
    # -----------------------------------------------------------------
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry. Unloading platforms first."""
    
    # 1. Unload platforms 
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # 2. Unregister custom service 
    if hass.services.has_service(DOMAIN, SERVICE_GET_DILAUNCHER_JSON):
        hass.services.async_remove(DOMAIN, SERVICE_GET_DILAUNCHER_JSON)
        _LOGGER.debug("Unregistered custom service: %s.%s", DOMAIN, SERVICE_GET_DILAUNCHER_JSON)

    # 3. Clean up stored data
    if unload_ok and entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok