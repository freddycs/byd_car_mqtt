"""Sensor platform for the BYD Car MQTT integration."""
import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.typing import StateType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfPressure,
    UnitOfTemperature,
)
# --- IMPORTS FOR MQTT & CONFIG ---
from homeassistant.components import mqtt
from .const import (
    DOMAIN, 
    BYD_UPDATE_EVENT, # Retained for other sensors (e.g. Mileage, Range)
    CONF_MQTT_TOPIC_SUBSCRIBE,
    CONF_CAR_UNIQUE_ID,
    CONF_MAX_BATTERY_CAPACITY_KWH, 
    DEFAULT_MAX_BATTERY_CAPACITY_KWH,
    DEFAULT_SOC_SUBTOPIC, # Topic used for direct subscription: /dolphinc/SOC
)
# -------------------------------------

_LOGGER = logging.getLogger(__name__)


# -----------------------------------------------------------------------------------------
# SENSOR TYPES: General sensors that rely on the main update event (not SOC/Energy).
# -----------------------------------------------------------------------------------------
SENSOR_TYPES = {
    # General/Timestamp Data
    "car_status": ("Car Status", None, SensorDeviceClass.ENUM, None),
    "charge_time": ("Last Charge Timestamp", None, SensorDeviceClass.TIMESTAMP, None),
    "detection_time": ("Detection Timestamp", None, SensorDeviceClass.TIMESTAMP, None),
    "mileage_km": ("Total Mileage", UnitOfLength.KILOMETERS, None, SensorStateClass.TOTAL),
    
    # Car Status Data
    "remaining_range_km": ("Remaining Range", UnitOfLength.KILOMETERS, None, SensorStateClass.MEASUREMENT),
    "battery_health": ("Battery Health", PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT),

    # Status Report Battery Data (from the slow/detailed payload)
    "battery_percent_report": ("Status Report Battery Level", PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT),
    # FIX: Device Class removed (was SensorDeviceClass.ENERGY) to comply with MEASUREMENT state class.
    "battery_energy_kwh_report": ("Status Report Energy (kWh)", UnitOfEnergy.KILO_WATT_HOUR, None, SensorStateClass.MEASUREMENT),

    # --- OTHER SENSORS ---
    "consumption_kwh_50km": ("Energy Consumption (50km)", "kWh/50km", None, SensorStateClass.MEASUREMENT),
    "external_temperature_celsius": ("External Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    "tpms_lf_kpa": ("Tire Pressure Left Front", UnitOfPressure.KPA, SensorDeviceClass.PRESSURE, SensorStateClass.MEASUREMENT),
    "tpms_rf_kpa": ("Tire Pressure Right Front", UnitOfPressure.KPA, SensorDeviceClass.PRESSURE, SensorStateClass.MEASUREMENT),
    "tpms_lr_kpa": ("Tire Pressure Left Rear", UnitOfPressure.KPA, SensorDeviceClass.PRESSURE, SensorStateClass.MEASUREMENT),
    "tpms_rr_kpa": ("Tire Pressure Right Rear", UnitOfPressure.KPA, SensorDeviceClass.PRESSURE, SensorStateClass.MEASUREMENT),
    "tt_lf_celsius": ("Tire Temp Left Front", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    "tt_rf_celsius": ("Tire Temp Right Front", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    "tt_lr_celsius": ("Tire Temp Left Rear", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    "tt_rr_celsius": ("Tire Temp Right Rear", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
}


# ----------------------------------------------------------------------
# Mandatory Setup Function 
# ----------------------------------------------------------------------
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the BYD Car sensor platform."""
    _LOGGER.debug("Setting up BYD Car MQTT sensor platform.")
    
    config_data = hass.data[DOMAIN][entry.entry_id] 
    
    model_name_base = entry.title.lower().replace("byd ", "").strip().replace(" ", "_")
    model_name_title = entry.title.replace("BYD ", "").strip().capitalize()
    entry_id = entry.entry_id

    # Retrieve configured battery capacity
    max_capacity = config_data.get(
        CONF_MAX_BATTERY_CAPACITY_KWH, 
        DEFAULT_MAX_BATTERY_CAPACITY_KWH 
    )
    base_status_topic = config_data.get(CONF_MQTT_TOPIC_SUBSCRIBE)
    
    entities = []
    
    # 1. Create all general sensors that rely on the main update event
    for key, (name, unit, device_class, state_class) in SENSOR_TYPES.items():
        entities.append(
            BYDCarSensor(
                hass, entry_id, key, model_name_base, model_name_title, 
                name, unit, device_class, state_class
            )
        )
    
    # 2. Create the Battery % and Energy sensors that use DIRECT MQTT SUBSCRIPTION
    if base_status_topic:
        soc_topic = f"{base_status_topic.rstrip('/')}/{DEFAULT_SOC_SUBTOPIC}"
        
        # Instantiate the shared updater class
        battery_updater = BYDBatteryUpdater(
            hass, entry_id, model_name_base, model_name_title, 
            soc_topic, max_capacity
        )
        
        # Add the two consumer entities that link to the updater
        entities.extend([
            BYDBatteryPercentSensor(battery_updater),
            BYDBatteryEnergySensor(battery_updater)
        ])
        
    async_add_entities(entities, True)


# ----------------------------------------------------------------------
# Core Sensor Class (Listens to the internal HA event for general data)
# ----------------------------------------------------------------------
class BYDCarSensor(SensorEntity):
    """Representation of a BYD Car data sensor that relies on the HA event bus."""

    def __init__(self, hass, entry_id, data_key, model_name_base, model_name_title, name, unit, device_class, state_class):
        """Initialize the sensor."""
        self.hass = hass
        self._data_key = data_key
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class 
        self._attr_state_class = state_class 
        
        if device_class == SensorDeviceClass.ENUM:
            self._attr_options = ["Started", "Idle", "Driving", "Powered Off", "Unknown"]
        
        self._attr_unique_id = f"{DOMAIN}_{model_name_base}_{data_key}"
        self._attr_name = f"BYD {model_name_title} {name}"
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": f"BYD {model_name_title}", 
            "manufacturer": "BYD",
            "model": model_name_title,
        }
        
    async def async_added_to_hass(self):
        """Register the custom event listener robustly."""
        
        @callback
        def _listen_to_update(event):
            """Internal callback function for the event listener."""
            self._handle_update(event)
            
        # Use async_on_remove to register the listener robustly
        self.async_on_remove(
            self.hass.bus.async_listen(BYD_UPDATE_EVENT, _listen_to_update)
        )

    @callback
    def _handle_update(self, event):
        """Update the sensor state when the custom event is received."""
        parsed_data = event.data
        new_state = parsed_data.get(self._data_key)
        
        # --- NEW DEBUG LOGGING ---
        # Debug Log (in English): Check if the sensor received the event and if its key is present.
        _LOGGER.debug(
            "BYDCarSensor (%s) received update event. Data found: %s. Full Event Keys: %s", 
            self._data_key, 
            new_state,
            list(parsed_data.keys())
        )
        # -------------------------

        if new_state is not None:
            if new_state != self.native_value:
                self._attr_native_value = new_state
                self.async_write_ha_state()
            else:
                 # Debug Log (in English): Also log if the value is the same.
                 _LOGGER.debug(
                     "BYDCarSensor (%s) received update but value is unchanged: %s", 
                     self._data_key, 
                     new_state
                 )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._attr_native_value


# ----------------------------------------------------------------------
# NEW: DIRECT MQTT UPDATER CLASS (Handles subscription and state storage)
# ----------------------------------------------------------------------
class BYDBatteryUpdater:
    """A shared component to subscribe to the /SOC topic and update battery state."""

    def __init__(self, hass, entry_id, model_name_base, model_name_title, soc_topic, max_capacity_kwh):
        self.hass = hass
        self._soc_topic = soc_topic
        self._max_capacity = max_capacity_kwh
        
        # Store for consumers to build unique IDs and names
        self.model_name_base = model_name_base
        self.model_name_title = model_name_title
        
        # State storage for the two sensors
        self.battery_percent = None
        self.battery_energy_kwh = None
        
        # List of callbacks to notify consumers (the two sensor entities)
        self._callbacks = []
        
        # Device info for consumers to reuse
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": f"BYD {model_name_title}", 
            "manufacturer": "BYD",
            "model": model_name_title,
        }
        
    async def async_added_to_hass(self):
        """Subscribe to the dedicated SOC MQTT topic."""
        _LOGGER.debug("BYDBatteryUpdater subscribing to topic: %s", self._soc_topic)

        @callback
        def mqtt_message_received(message):
            """Handle new MQTT messages received on the SoC topic."""
            
            try:
                payload_str = str(message.payload).strip()
                # Cast to float first to handle payloads like "90.0" then to int
                new_soc = int(float(payload_str)) 
                
                if 0 <= new_soc <= 100:
                    current_energy = round(self._max_capacity * (new_soc / 100.0), 2)
                    
                    # 1. Update internal state
                    self.battery_percent = new_soc
                    self.battery_energy_kwh = current_energy
                    
                    # 2. Notify all listening sensor entities
                    for callback_fn in self._callbacks:
                        callback_fn()
                    
                else:
                    _LOGGER.warning("Received SoC %s is outside the range [0, 100] on topic %s", new_soc, self._soc_topic)
                    
            except ValueError:
                _LOGGER.error("Received non-numeric payload on %s: '%s'", self._soc_topic, message.payload)
            except Exception as e:
                _LOGGER.error("Unexpected error processing MQTT message on %s: %s", self._soc_topic, e)

        # Start subscription as a task
        self.hass.async_create_task(
            mqtt.async_subscribe(self.hass, self._soc_topic, mqtt_message_received, qos=0)
        )
        
        # Mark as subscribed (used by the consumer entities)
        self._is_subscribed = True


    def register_callback(self, callback_fn):
        """Register a callback to be notified of new data."""
        self._callbacks.append(callback_fn)
        # Return a function to deregister
        def deregister():
            if callback_fn in self._callbacks:
                self._callbacks.remove(callback_fn)
        return deregister


# ----------------------------------------------------------------------
# Sensor: Battery Percentage (Consumer)
# ----------------------------------------------------------------------
class BYDBatteryPercentSensor(SensorEntity):
    """Battery percentage sensor updated via direct MQTT subscription."""

    def __init__(self, updater: BYDBatteryUpdater):
        """Initialize the sensor."""
        self._updater = updater
        
        # Use attributes from the updater for naming and IDs
        self._attr_unique_id = f"{DOMAIN}_{updater.model_name_base}_battery_percent"
        self._attr_name = f"BYD {updater.model_name_title} Battery Level"
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_info = updater._attr_device_info # Reuse device info

    async def async_added_to_hass(self):
        """Register the entity's callback with the shared updater and start subscription."""
        
        # The first battery sensor ensures the updater is initialized and starts its subscription
        if not hasattr(self._updater, '_is_subscribed'):
             await self._updater.async_added_to_hass()
             
        # Register the callback to update this sensor using the standard HA pattern
        self.async_on_remove(self._updater.register_callback(self.async_write_ha_state))

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._updater.battery_percent

# ----------------------------------------------------------------------
# Sensor: Battery Energy (Consumer)
# ----------------------------------------------------------------------
class BYDBatteryEnergySensor(SensorEntity):
    """Current battery energy sensor updated via direct MQTT subscription."""

    def __init__(self, updater: BYDBatteryUpdater):
        """Initialize the sensor."""
        self._updater = updater
        
        # Use attributes from the updater for naming and IDs
        self._attr_unique_id = f"{DOMAIN}_{updater.model_name_base}_battery_energy_kwh_current"
        self._attr_name = f"BYD {updater.model_name_title} Current Battery Energy"
        # FIX APPLIED: Device Class removed (was SensorDeviceClass.ENERGY)
        self._attr_device_class = None
        # State class is correctly set to MEASUREMENT as battery energy decreases when driving
        self._attr_state_class = SensorStateClass.MEASUREMENT 
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_info = updater._attr_device_info # Reuse device info

    async def async_added_to_hass(self):
        """Register the entity's callback with the shared updater."""
        # The updater's subscription is started by the first entity, we just register the listener
        self.async_on_remove(self._updater.register_callback(self.async_write_ha_state))

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._updater.battery_energy_kwh
