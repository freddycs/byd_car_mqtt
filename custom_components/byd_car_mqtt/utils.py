"""Utility functions for generating the DiLauncher automation JSON."""
import json
from homeassistant.config_entries import ConfigEntry
from .const import (
    CONF_MQTT_TOPIC_SUBSCRIBE, 
    DEFAULT_AC_TEMP_STATUS_SUBTOPIC, 
    DEFAULT_AC_FAN_SPEED_SUBTOPIC
)

def generate_dilauncher_automation_json(entry: ConfigEntry) -> str:
    """
    Generates the full list of DiLauncher automation entries (as a JSON string) 
    required to monitor AC Temperature and Fan Speed.
    
    This function retrieves the configured MQTT status topic and inserts it 
    into the automation templates.
    """
    
    # 1. Get the latest configuration
    config = dict(entry.data)
    config.update(entry.options)
    # The base topic HA subscribes to, e.g., "/dolphinc"
    base_status_topic = config.get(CONF_MQTT_TOPIC_SUBSCRIBE, "/dolphinc")

    # 2. Define the list that will hold all automations
    automations = []

    # --- AC Temperature Automations (17°C to 33°C) ---
    # taskType 54 corresponds to AC Temperature
    for temp in range(17, 34):
        # Constructs the runTask string: e.g., "MQTT:/dolphinc/actemp+17"
        run_task = f"MQTT:{base_status_topic.rstrip('/')}/{DEFAULT_AC_TEMP_STATUS_SUBTOPIC}+{temp}"
        automations.append({
            "name": f"AC temperature {temp}",
            "state": 1,
            "delayTime": 1,
            "runTask": run_task,
            "conditions": [{
                "taskType": 54, # AC Temperature task type
                "compareType": 4, # Equals
                "expect": temp
            }]
        })

    # --- AC Fan Speed Automations (0 to 7) ---
    # taskType 35 corresponds to Fan Speed
    for speed in range(0, 8):
        # Constructs the runTask string: e.g., "MQTT:/dolphinc/fanspeed+0"
        run_task = f"MQTT:{base_status_topic.rstrip('/')}/{DEFAULT_AC_FAN_SPEED_SUBTOPIC}+{speed}"
        automations.append({
            "name": f"fan speed {speed}",
            "state": 1,
            "delayTime": 1,
            "runTask": run_task,
            "conditions": [{
                "taskType": 35, # Fan Speed task type
                "compareType": 4, # Equals
                "expect": speed
            }]
        })
        
    # 3. Return the JSON array as a formatted string
    return json.dumps(automations, indent=4)