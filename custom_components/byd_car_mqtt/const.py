"""Constants for the BYD Car MQTT integration."""
from homeassistant.const import Platform 

DOMAIN = "byd_car_mqtt"
BYD_UPDATE_EVENT = "byd_car_update"

# Configuration keys used in config_flow.py
CONF_MQTT_TOPIC_SUBSCRIBE = "mqtt_topic_subscribe"
DEFAULT_MQTT_TOPIC = "/dolphinc"

# --- Number/Climate Data Keys (Used by number.py and fan.py) ---
ATTR_AC_TEMP_CELSIUS = "ac_temp_celsius"

# Configuration Keys for A/C Temperature
DEFAULT_AC_TEMP_STATUS_SUBTOPIC = "actemp" # The subtopic portion
DEFAULT_AC_FAN_SPEED_SUBTOPIC = "fanspeed" 
DEFAULT_DRIVER_VENT_SUBTOPIC = "drivervent"
DEFAULT_PASSENGER_VENT_SUBTOPIC = "passengervent"
DEFAULT_SUNROOF_POS_SUBTOPIC = "sunroof/position"

# -------------------------------------------------------------
# --- NEW SOC-RELATED CONSTANTS (Updated for Configurability) ---
# The subtopic for the dedicated SOC feed (used in sensor.py)
DEFAULT_SOC_SUBTOPIC = "SOC" 

# CONFIGURATION KEY for Battery Capacity
# This key will be used in config_flow.py and sensor.py to store/retrieve the capacity.
CONF_MAX_BATTERY_CAPACITY_KWH = "max_battery_capacity_kwh"

# Default capacity (A common value like the Dolphin/Atto 3 Extended Range)
DEFAULT_MAX_BATTERY_CAPACITY_KWH = 60.48 

# -------------------------------------------------------------
# --- CUSTOM SERVICE CONSTANTS (Used by __init__.py and button.py) ---
# The service name registered in __init__.py
SERVICE_GET_DILAUNCHER_JSON = "get_dilauncher_json"
# The attribute used in the service call
ATTR_OUTPUT_PATH = "output_path"
# The default file path for the generated JSON, relative to the HA config folder.
# NOTE: Changed to the config root for easier access/discovery.
DEFAULT_OUTPUT_PATH = "dilauncher_automations.json"


# Platforms this integration supports
# Use the Platform enum constants instead of strings
PLATFORMS = [
    Platform.SENSOR, 
    Platform.BINARY_SENSOR, 
    Platform.FAN, 
    Platform.NUMBER, 
    Platform.COVER, 
    Platform.BUTTON
] 

# ======================================================================
# --- Sensor Data Keys (Used by sensor.py and parsing_logic.py) ---
# ... (existing sensor keys) ...

# ⬅️ FAN SENSOR KEY
ATTR_FAN_SPEED = "fan_speed"


# ======================================================================
# --- Binary Sensor Data Keys (Used by binary_sensor.py) ---
# ... (existing binary sensor keys) ...

# Configuration Keys for Config Flow (MUST BE PRESENT)
CONF_MQTT_TOPIC_COMMAND = "mqtt_topic_command"
CONF_CAR_UNIQUE_ID = "car_unique_id"
CONF_ENABLE_DRIVER_VENT = "enable_driver_vent"
CONF_ENABLE_PASSENGER_VENT = "enable_passenger_vent"