"""Binary Sensor platform for the BYD Car MQTT integration."""
import logging
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.core import callback
from homeassistant.config_entries import ConfigEntry # <-- Added missing import

# Import constants from your custom component's const.py file
from .const import DOMAIN, BYD_UPDATE_EVENT # Assuming these are defined in const.py

_LOGGER = logging.getLogger(__name__)

# List of binary sensors to create
BINARY_SENSOR_TYPES = {
    # Key:                  Name:                       HA Device Class:
    "win_lf_open":          ("Window Left Front Open",  BinarySensorDeviceClass.WINDOW),
    "win_rf_open":          ("Window Right Front Open", BinarySensorDeviceClass.WINDOW),
    "win_lr_open":          ("Window Left Rear Open",   BinarySensorDeviceClass.WINDOW),
    "win_rr_open":          ("Window Right Rear Open",  BinarySensorDeviceClass.WINDOW),
    "sunroof_open":         ("Sunroof Panel Open",      BinarySensorDeviceClass.WINDOW),
    # "sunroof_open" entity REMOVED as requested.
}

# ----------------------------------------------------------------------
# Mandatory Setup Function 
# ----------------------------------------------------------------------
async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities): # <-- Added type hint for entry
    """Set up the BYD Car binary sensor platform."""
    _LOGGER.debug("Setting up BYD Car MQTT binary sensor platform.")

    model_name_base = entry.title.lower().replace("byd ", "").strip().replace(" ", "_")
    model_name_title = entry.title.replace("BYD ", "").strip().capitalize()
    
    entities = []
    
    for key, (name, device_class) in BINARY_SENSOR_TYPES.items():
        entities.append(
            BYDCarBinarySensor(
                hass, 
                entry.entry_id, 
                key, 
                model_name_base,
                model_name_title,
                name,
                device_class
            )
        )
    async_add_entities(entities, True)


# ----------------------------------------------------------------------
# Entity Class Definition 
# ----------------------------------------------------------------------
class BYDCarBinarySensor(BinarySensorEntity):
    """Representation of a BYD Car binary status."""

    def __init__(self, hass, entry_id, data_key, model_name_base, model_name_title, name, device_class):
        """Initialize the sensor."""
        self._hass = hass
        self._data_key = data_key
        self._is_on = None # Use _is_on for binary sensors
        
        self._attr_device_class = device_class

        self._attr_unique_id = f"{DOMAIN}_{model_name_base}_{data_key}"
        self._attr_name = f"BYD {model_name_title} {name}"
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": f"BYD {model_name_title}", 
            "manufacturer": "BYD",
            "model": model_name_title,
        }
        

    async def async_added_to_hass(self):
        """Run when entity is about to be added to Home Assistant."""
        # Use async_listen to correctly subscribe to the custom event
        self.async_on_remove(self._hass.bus.async_listen(BYD_UPDATE_EVENT, self._handle_update))

    @callback
    def _handle_update(self, event):
        """Update the sensor state when the custom event is received."""
        parsed_data = event.data
        new_state = parsed_data.get(self._data_key) # This will be True/False
        
        if new_state is not None:
            self._is_on = new_state
            self.async_write_ha_state()

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._is_on
