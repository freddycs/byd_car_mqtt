"""Sensor platform for the BYD Car MQTT integration."""
import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.core import callback
from homeassistant.helpers.typing import StateType
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfPressure,
    UnitOfTemperature,
)

# Import constants from your custom component's const.py file
from .const import DOMAIN, BYD_UPDATE_EVENT

_LOGGER = logging.getLogger(__name__)


# -----------------------------------------------------------------------------------------
# SENSOR TYPES: Maps the Python dictionary key to Home Assistant entity properties
# -----------------------------------------------------------------------------------------
SENSOR_TYPES = {
    # General/Timestamp Data
    # The car_status sensor now uses SensorDeviceClass.ENUM
    "car_status": ("Car Status", None, SensorDeviceClass.ENUM, None),
    "charge_time": ("Last Charge Timestamp", None, SensorDeviceClass.TIMESTAMP, None),
    "detection_time": ("Detection Timestamp", None, SensorDeviceClass.TIMESTAMP, None),
    "mileage_km": ("Total Mileage", UnitOfLength.KILOMETERS, None, SensorStateClass.TOTAL),
    
    # Charging Reminder Data
    "start_battery_pct": ("Charge Start Battery", PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT),
    "end_battery_pct": ("Charge End Battery", PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT),
    "charge_amount_kwh_total": ("Energy Charged (Total)", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),

    # Current Status Data
    "battery_percent": ("Current Battery Level", PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT),
    "battery_energy_kwh_current": ("Current Battery Energy", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL),
    "remaining_range_km": ("Remaining Range", UnitOfLength.KILOMETERS, None, SensorStateClass.MEASUREMENT),
    "battery_health": ("Battery Health", PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT),

    # --- NEW SENSORS ADDED (FIXED FOR RATE MEASUREMENT) ---
    # Energy Consumption (50km) is a rate (kWh/50km). DeviceClass is None to allow StateClass.MEASUREMENT.
    "consumption_kwh_50km": ("Energy Consumption (50km)", "kWh/50km", None, SensorStateClass.MEASUREMENT),
    # External Temperature
    "external_temperature_celsius": ("External Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    
    # Tire Pressure Data (Unit: kPa)
    "tpms_lf_kpa": ("Tire Pressure Left Front", UnitOfPressure.KPA, SensorDeviceClass.PRESSURE, SensorStateClass.MEASUREMENT),
    "tpms_rf_kpa": ("Tire Pressure Right Front", UnitOfPressure.KPA, SensorDeviceClass.PRESSURE, SensorStateClass.MEASUREMENT),
    "tpms_lr_kpa": ("Tire Pressure Left Rear", UnitOfPressure.KPA, SensorDeviceClass.PRESSURE, SensorStateClass.MEASUREMENT),
    "tpms_rr_kpa": ("Tire Pressure Right Rear", UnitOfPressure.KPA, SensorDeviceClass.PRESSURE, SensorStateClass.MEASUREMENT),

    # Tire Temperature Data (Unit: °C)
    "tt_lf_celsius": ("Tire Temp Left Front", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    "tt_rf_celsius": ("Tire Temp Right Front", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    "tt_lr_celsius": ("Tire Temp Left Rear", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    "tt_rr_celsius": ("Tire Temp Right Rear", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
}


# ----------------------------------------------------------------------
# Mandatory Setup Function 
# ----------------------------------------------------------------------
async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the BYD Car sensor platform."""
    _LOGGER.debug("Setting up BYD Car MQTT sensor platform.")
    
    # 1. Get the base name from the entry title (e.g., "dolphin" from "BYD Dolphin")
    model_name_base = entry.title.lower().replace("byd ", "").strip().replace(" ", "_")
    
    # 2. Get the clean Title for display (e.g., "Dolphin" from "BYD Dolphin")
    model_name_title = entry.title.replace("BYD ", "").strip().capitalize()

    entities = []
    
    # Iterate through the SENSOR_TYPES dictionary to create instances
    for key, (name, unit, device_class, state_class) in SENSOR_TYPES.items():
        entities.append(
            BYDCarSensor(
                hass, 
                entry.entry_id, 
                key, 
                model_name_base,    # Pass the sanitized model name for entity_id
                model_name_title,   # Pass the cleaned title for friendly names
                name,               # The generic sensor name (e.g., "Total Mileage")
                unit, 
                device_class, 
                state_class
            )
        )
        
    async_add_entities(entities, True)


# ----------------------------------------------------------------------
# Entity Class Definition (UPDATED)
# ----------------------------------------------------------------------
class BYDCarSensor(SensorEntity):
    """Representation of a BYD Car data sensor."""

    def __init__(self, hass, entry_id, data_key, model_name_base, model_name_title, name, unit, device_class, state_class):
        """Initialize the sensor."""
        self._hass = hass
        self._data_key = data_key
        self._state: StateType = None
        self._unit = unit
        self._device_class = device_class
        self._state_class = state_class
        
        # --- ENUM Options Logic ---
        if device_class == SensorDeviceClass.ENUM:
            # Define the limited set of possible states for the car_status sensor
            self._attr_options = ["Started", "Idle", "Driving", "Powered Off", "Unknown"]
        
        # Unique ID is essential for a Config Flow based integration
        self._attr_unique_id = f"{DOMAIN}_{model_name_base}_{data_key}"
        
        # Name: Example: BYD Dolphin Total Mileage
        self._attr_name = f"BYD {model_name_title} {name}"
        self._attr_device_class = device_class # Set the device class
        self._attr_state_class = state_class # Set the state class
        
        # Device information allows grouping entities under one device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": f"BYD {model_name_title}", # Device name (e.g., "BYD Dolphin")
            "manufacturer": "BYD",
            "model": model_name_title,
        }
        
    async def async_added_to_hass(self):
        """Run when entity is about to be added to Home Assistant."""
        # Subscribe to the custom event fired by the MQTT handler in __init__.py
        self._hass.bus.async_listen(BYD_UPDATE_EVENT, self._handle_update)

    @callback
    def _handle_update(self, event):
        """Update the sensor state when the custom event is received."""
        parsed_data = event.data
        new_state = parsed_data.get(self._data_key)
        
        if new_state is not None:
            self._state = new_state
            # Force the entity to update its state in HA
            self.async_write_ha_state()

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit
        
    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class # ⬅️ Ensure 8 spaces (2 indents) before 'return'

    @property
    def state_class(self):
        """Return the state class."""
        return self._state_class # ⬅️ Ensure 8 spaces (2 indents) before 'return'