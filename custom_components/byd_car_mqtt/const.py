"""Constants for the BYD Car MQTT integration."""
from homeassistant.const import Platform

# ----------------------------------------------------------------------
# --- DOMAIN AND GENERAL CONSTANTS ---
# ----------------------------------------------------------------------
DOMAIN = "byd_car_mqtt"
DEFAULT_MANUFACTURER = "BYD"
DEFAULT_DEVICE_MODEL = "BYD Vehicle" # Use this as a base, specific model can be added later

# --- Event Bus Names ---
BYD_UPDATE_EVENT = "byd_car_update" # Primary event for the main status payload
BYD_SPEED_UPDATE_EVENT = "byd_car_mqtt_speed_update" # For dedicated speed topic/sensor updates

# ----------------------------------------------------------------------
# --- CONFIGURATION KEYS (Used in config_flow.py and throughout the integration) ---
# ----------------------------------------------------------------------
CONF_CAR_UNIQUE_ID = "car_unique_id"
CONF_MAX_BATTERY_CAPACITY_KWH = "max_battery_capacity_kwh"
DEFAULT_MAX_BATTERY_CAPACITY_KWH = 60.48 # Default for Dolphin/Atto 3 Extended Range

# --- MQTT Topics ---
CONF_MQTT_TOPIC_SUBSCRIBE = "mqtt_topic_subscribe"
DEFAULT_MQTT_TOPIC = "/dolphinc"

CONF_MQTT_TOPIC_COMMAND = "mqtt_topic_command"
# Assuming commands are sent back to the main topic or a subtopic like '/dolphinc/command'
DEFAULT_MQTT_COMMAND_TOPIC = f"{DEFAULT_MQTT_TOPIC}/command" 

# --- Component Feature Enablement ---
CONF_ENABLE_DRIVER_VENT = "enable_driver_vent"
CONF_ENABLE_PASSENGER_VENT = "enable_passenger_vent"


# ----------------------------------------------------------------------
# --- SUBTOPIC IDENTIFIERS (Used for command/report parsing and entity creation) ---
# ----------------------------------------------------------------------

# Subtopics associated with number/climate entities
DEFAULT_AC_TEMP_STATUS_SUBTOPIC = "actemp"
DEFAULT_AC_FAN_SPEED_SUBTOPIC = "fanspeed" 
DEFAULT_DRIVER_VENT_SUBTOPIC = "drivervent"
DEFAULT_PASSENGER_VENT_SUBTOPIC = "passengervent"
DEFAULT_SUNROOF_POS_SUBTOPIC = "sunroof/position"

# Dedicated report subtopics (used for separate, high-frequency MQTT feeds)
DEFAULT_SOC_SUBTOPIC = "SOC" 
DEFAULT_SPEED_SUBTOPIC = "speed" 


# ----------------------------------------------------------------------
# --- CUSTOM SERVICE CONSTANTS (Used by __init__.py) ---
# ----------------------------------------------------------------------
SERVICE_GET_DILAUNCHER_JSON = "get_dilauncher_json"
ATTR_OUTPUT_PATH = "output_path"
DEFAULT_OUTPUT_PATH = "dilauncher_automations.json"


# ----------------------------------------------------------------------
# --- PLATFORM SUPPORT AND GROUPING ---
# ----------------------------------------------------------------------
PLATFORMS = [
    Platform.SENSOR, 
    Platform.BINARY_SENSOR, 
    Platform.FAN, 
    Platform.NUMBER, 
    Platform.COVER, 
    Platform.BUTTON
] 

# ----------------------------------------------------------------------
# --- SENSOR DATA KEYS (Used by sensor.py and parsing_logic.py) ---
# These keys are the result keys in the dictionary fired on the event bus
# ----------------------------------------------------------------------
DATA_KEY_MILEAGE = "mileage_km"
DATA_KEY_BATTERY_PCT = "battery_percent_report"
DATA_KEY_RANGE = "remaining_range_km"
DATA_KEY_CAR_STATUS = "car_status"
DATA_KEY_FAN_SPEED = "fan_speed"
DATA_KEY_SPEED = "speed_kmh"

# --- Attribute Keys for Sensors ---
ATTR_LAST_UPDATE_TIME = "last_update_time"
ATTR_SOURCE_TOPIC = "source_topic"
ATTR_AC_TEMP_CELSIUS = "ac_temp_celsius"