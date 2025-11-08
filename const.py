"""Constants for the BYD Car MQTT integration."""
from homeassistant.const import Platform # <-- ADD THIS IMPORT

DOMAIN = "byd_car_mqtt"
BYD_UPDATE_EVENT = "byd_car_update"

# Configuration keys used in config_flow.py
CONF_MQTT_TOPIC_SUBSCRIBE = "mqtt_topic_subscribe"
DEFAULT_MQTT_TOPIC = "/dolphinc"

# --- Number/Climate Data Keys (Used by number.py and fan.py) ---
ATTR_AC_TEMP_CELSIUS = "ac_temp_celsius"

# Configuration Keys for A/C Temperature
DEFAULT_AC_TEMP_STATUS_SUBTOPIC = "actemp" # The subtopic portion
DEFAULT_AC_FAN_SPEED_SUBTOPIC = "fanspeed" # <--- CORRECTLY ADDED
DEFAULT_DRIVER_VENT_SUBTOPIC = "drivervent" # Assuming status subtopic
DEFAULT_PASSENGER_VENT_SUBTOPIC = "passengervent" # Assuming status subtopic
DEFAULT_SUNROOF_POS_SUBTOPIC = "sunroof/position"

# Platforms this integration supports
# Use the Platform enum constants instead of strings
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.FAN, Platform.NUMBER,Platform.COVER] 

# ======================================================================
# --- Sensor Data Keys (Used by sensor.py and parsing_logic.py) ---
# ======================================================================
# ... (existing sensor keys) ...

# ⬅️ NEW FAN SENSOR KEY
ATTR_FAN_SPEED = "fan_speed" # <--- CORRECTLY ADDED (though only used internally by fan.py for now)


# ======================================================================
# --- Binary Sensor Data Keys (Used by binary_sensor.py) ---
# ======================================================================
# ... (existing binary sensor keys) ...

# Configuration Keys for Config Flow (MUST BE PRESENT)
CONF_MQTT_TOPIC_COMMAND = "mqtt_topic_command"
CONF_CAR_UNIQUE_ID = "car_unique_id"
CONF_ENABLE_DRIVER_VENT = "enable_driver_vent" # <--- ADD THIS
CONF_ENABLE_PASSENGER_VENT = "enable_passenger_vent" # <--- ADD THIS