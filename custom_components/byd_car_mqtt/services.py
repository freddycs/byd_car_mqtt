import logging
import json
import os
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN, 
    CONF_MQTT_TOPIC_SUBSCRIBE, 
    DEFAULT_OUTPUT_PATH,
    SERVICE_DILAUNCHER_JSON_GENERATE
)

_LOGGER = logging.getLogger(__name__)

# The full JSON template provided by the user (retained for completeness)
DILAUNCHER_JSON_TEMPLATE = [
    # AC Temperature Entries (17-33)
    {"name":"AC temperature 17","state":1,"delayTime":1,"runTask":"MQTT:/[status_topic]/actemp+17","conditions":[{"taskType":54,"compareType":4,"expect":17}]},
    {"name":"AC temperature 18","state":1,"delayTime":1,"runTask":"MQTT:/[status_topic]/actemp+18","conditions":[{"taskType":54,"compareType":4,"expect":18}]},
    {"name":"AC temperature 19","state":1,"delayTime":1,"runTask":"MQTT:/[status_topic]/actemp+19","conditions":[{"taskType":54,"compareType":4,"expect":19}]},
    {"name":"AC temperature 20","state":1,"delayTime":1,"runTask":"MQTT:/[status_topic]/actemp+20","conditions":[{"taskType":54,"compareType":4,"expect":20}]},
    {"name":"AC temperature 21","state":1,"delayTime":1,"runTask":"MQTT:/[status_topic]/actemp+21","conditions":[{"taskType":54,"compareType":4,"expect":21}]},
    {"name":"AC temperature 22","state":1,"delayTime":1,"runTask":"MQTT:/[status_topic]/actemp+22","conditions":[{"taskType":54,"compareType":4,"expect":22}]},
    {"name":"AC temperature 23","state":1,"delayTime":1,"runTask":"MQTT:/[status_topic]/actemp+23","conditions":[{"taskType":54,"compareType":4,"expect":23}]},
    {"name":"AC temperature 24","state":1,"delayTime":1,"runTask":"MQTT:/[status_topic]/actemp+24","conditions":[{"taskType":54,"compareType":4,"expect":24}]},
    {"name":"AC temperature 25","state":1,"delayTime":1,"runTask":"MQTT:/[status_topic]/actemp+25","conditions":[{"taskType":54,"compareType":4,"expect":25}]},
    {"name":"AC temperature 26","state":1,"delayTime":1,"runTask":"MQTT:/[status_topic]/actemp+26","conditions":[{"taskType":54,"compareType":4,"expect":26}]},
    {"name":"AC temperature 27","state":1,"delayTime":1,"runTask":"MQTT:/[status_topic]/actemp+27","conditions":[{"taskType":54,"compareType":4,"expect":27}]},
    {"name":"AC temperature 28","state":1,"delayTime":1,"runTask":"MQTT:/[status_topic]/actemp+28","conditions":[{"taskType":54,"compareType":4,"expect":28}]},
    {"name":"AC temperature 29","state":1,"delayTime":1,"runTask":"MQTT:/[status_topic]/actemp+29","conditions":[{"taskType":54,"compareType":4,"expect":29}]},
    {"name":"AC temperature 30","state":1,"delayTime":1,"runTask":"MQTT:/[status_topic]/actemp+30","conditions":[{"taskType":54,"compareType":4,"expect":30}]},
    {"name":"AC temperature 31","state":1,"delayTime":1,"runTask":"MQTT:/[status_topic]/actemp+31","conditions":[{"taskType":54,"compareType":4,"expect":31}]},
    {"name":"AC temperature 32","state":1,"delayTime":1,"runTask":"MQTT:/[status_topic]/actemp+32","conditions":[{"taskType":54,"compareType":4,"expect":32}]},
    {"name":"AC temperature 33","state":1,"delayTime":1,"runTask":"MQTT:/[status_topic]/actemp+33","conditions":[{"taskType":54,"compareType":4,"expect":33}]},
    # Fan Speed Entries (0-7)
    {"name":"fan speed 0","state":1,"delayTime":1,"runTask":"MQTT:/[status_topic]/fanspeed+0","conditions":[{"taskType":35,"compareType":4,"expect":0}]},
    {"name":"fan speed 1","state":1,"delayTime":1,"runTask":"MQTT:/[status_topic]/fanspeed+1","conditions":[{"taskType":35,"compareType":4,"expect":1}]},
    {"name":"fan speed 2","state":1,"delayTime":1,"runTask":"MQTT:/[status_topic]/fanspeed+2","conditions":[{"taskType":35,"compareType":4,"expect":2}]},
    {"name":"fan speed 3","state":1,"delayTime":1,"runTask":"MQTT:/[status_topic]/fanspeed+3","conditions":[{"taskType":35,"compareType":4,"expect":3}]},
    {"name":"fan speed 4","state":1,"delayTime":1,"runTask":"MQTT:/[status_topic]/fanspeed+4","conditions":[{"taskType":35,"compareType":4,"expect":4}]},
    {"name":"fan speed 5","state":1,"delayTime":1,"runTask":"MQTT:/[status_topic]/fanspeed+5","conditions":[{"taskType":35,"compareType":4,"expect":5}]},
    {"name":"fan speed 6","state":1,"delayTime":1,"runTask":"MQTT:/[status_topic]/fanspeed+6","conditions":[{"taskType":35,"compareType":4,"expect":6}]},
    {"name":"fan speed 7","state":1,"delayTime":1,"runTask":"MQTT:/[status_topic]/fanspeed+7","conditions":[{"taskType":35,"compareType":4,"expect":7}]}
]


async def async_register_services(hass: HomeAssistant, entry: ConfigEntry):
    """Register the services for the BYD Car component."""
    
    config_data = hass.data[DOMAIN][entry.entry_id]
    
    if hass.services.has_service(DOMAIN, SERVICE_DILAUNCHER_JSON_GENERATE):
        return

    async def async_get_dilauncher_json(call: ServiceCall):
        """Generates the byd_dilauncher.json file using the configured MQTT topic."""
        
        base_topic = config_data.get(CONF_MQTT_TOPIC_SUBSCRIBE)
        if not base_topic:
            _LOGGER.error("MQTT Subscribe Topic is missing. Cannot generate DiLauncher JSON.")
            return

        # 1. Topic Substitution
        normalized_topic = base_topic.strip('/').rstrip('/')
        
        final_json_data = []
        for item in DILAUNCHER_JSON_TEMPLATE:
            new_item = item.copy()
            # Replace [status_topic] with the user's normalized topic
            new_item['runTask'] = new_item['runTask'].replace('[status_topic]', normalized_topic)
            final_json_data.append(new_item)

        # 2. Define output path
        output_path = call.data.get(cv.ATTR_PATH, DEFAULT_OUTPUT_PATH)
        filepath = hass.config.path(output_path)
        
        # 3. Define the blocking I/O function to run in the executor
        def write_file_blocking(path, data):
            """Blocking function to create directory and write JSON file."""
            # Use os.makedirs (blocking)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            # Use file writing (blocking)
            with open(path, 'w') as f:
                json.dump(data, f, indent=4)

        try:
            # 4. Execute the blocking operation in Home Assistant's thread pool
            # This is the crucial change that resolves the 'never awaited' RuntimeWarning
            await hass.async_add_executor_job(write_file_blocking, filepath, final_json_data)
            
            _LOGGER.info("Successfully generated DiLauncher JSON file at: %s", filepath)

        except Exception as err:
            _LOGGER.error("Failed to write DiLauncher JSON file to %s: %s", filepath, err)


    # Register the service
    hass.services.async_register(
        DOMAIN,
        SERVICE_DILAUNCHER_JSON_GENERATE,
        async_get_dilauncher_json,
        schema=vol.Schema({
            vol.Optional(cv.ATTR_PATH, default=DEFAULT_OUTPUT_PATH): cv.string,
        }),
    )