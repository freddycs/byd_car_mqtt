"""Sensor platform for the BYD Car MQTT integration."""
import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
# Import State and async_track_state_change_event for tracking the speed entity
from homeassistant.core import callback, HomeAssistant, State
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import StateType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfSpeed,
)
# --- IMPORTS FOR MQTT & CONFIG ---
from homeassistant.components import mqtt
from .const import (
    DOMAIN,
    BYD_UPDATE_EVENT,
    CONF_MQTT_TOPIC_SUBSCRIBE,
    CONF_CAR_UNIQUE_ID,
    CONF_MAX_BATTERY_CAPACITY_KWH,
    DEFAULT_MAX_BATTERY_CAPACITY_KWH,
    DEFAULT_SOC_SUBTOPIC,
    DEFAULT_SPEED_SUBTOPIC,
    DATA_KEY_CAR_STATUS, # Key for Car Status
    DATA_KEY_SPEED, # Key for Speed Sensor
)
# -------------------------------------

_LOGGER = logging.getLogger(__name__)


# -----------------------------------------------------------------------------------------
# SENSOR TYPES: General sensors that rely on the main update event.
# The "car_status" key has been removed from this dictionary and is handled by a dedicated class.
# -----------------------------------------------------------------------------------------
SENSOR_TYPES = {
    # General/Timestamp Data
    "charge_time": ("Last Charge Timestamp", None, SensorDeviceClass.TIMESTAMP, None),
    "detection_time": ("Detection Timestamp", None, SensorDeviceClass.TIMESTAMP, None),
    "mileage_km": ("Total Mileage", UnitOfLength.KILOMETERS, None, SensorStateClass.TOTAL),

    # Car Status Data
    "remaining_range_km": ("Remaining Range", UnitOfLength.KILOMETERS, None, SensorStateClass.MEASUREMENT),
    "battery_health": ("Battery Health", PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT),

    # Status Report Battery Data (from the slow/detailed payload)
    "battery_percent_report": ("Status Report Battery Level", PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT),
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
# Helper Function for Decoding MQTT Payloads
# ----------------------------------------------------------------------
def _safe_decode_payload(payload):
    """
    Safely decodes the MQTT payload if it is a bytes object.
    Returns the payload as a string, or None if decoding fails or the payload is not bytes/str.
    """
    if isinstance(payload, bytes):
        try:
            # Decode using UTF-8, which is standard for MQTT payloads
            return payload.decode("utf-8").strip()
        except Exception:
            # Log error if decoding fails, but continue
            _LOGGER.error("Error decoding MQTT payload from bytes.", exc_info=True)
            return None
    elif isinstance(payload, str):
        # If it's already a string, strip and return it
        return payload.strip()

    # Unexpected type
    return None

# ----------------------------------------------------------------------
# Mandatory Setup Function
# ----------------------------------------------------------------------
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the BYD Car sensor platform."""
    _LOGGER.debug("Setting up BYD Car MQTT sensor platform.")

    config_data = hass.data[DOMAIN][entry.entry_id]

    # Use the entry's title to create a base name (e.g., 'dolphin_car')
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

    # 1. Create the specialized Car Status Sensor (Handles speed override)
    entities.append(
        BYDCarStatusSensor(
            hass, entry_id, DATA_KEY_CAR_STATUS, model_name_base, model_name_title
        )
    )

    # 2. Create all other general sensors that rely on the main update event
    for key, (name, unit, device_class, state_class) in SENSOR_TYPES.items():
        entities.append(
            BYDCarSensor(
                hass, entry_id, key, model_name_base, model_name_title,
                name, unit, device_class, state_class
            )
        )

    # Check if we have a base topic to subscribe to
    if base_status_topic:

        # 3. Create the Battery % and Energy sensors that use DIRECT MQTT SUBSCRIPTION (/SOC)
        soc_topic = f"{base_status_topic.rstrip('/')}/{DEFAULT_SOC_SUBTOPIC}"

        # Instantiate the shared updater class for Battery
        battery_updater = BYDBatteryUpdater(
            hass, entry_id, model_name_base, model_name_title,
            soc_topic, max_capacity
        )

        # Add the two consumer entities that link to the updater
        entities.extend([
            BYDBatteryPercentSensor(battery_updater),
            BYDBatteryEnergySensor(battery_updater)
        ])

        # 4. Create the Speed sensor that uses DIRECT MQTT SUBSCRIPTION (/speed)
        speed_topic = f"{base_status_topic.rstrip('/')}/{DEFAULT_SPEED_SUBTOPIC}"

        # Instantiate the shared updater class for Speed
        speed_updater = BYDSpeedUpdater(
            hass, entry_id, model_name_base, model_name_title,
            speed_topic
        )

        # Add the consumer entity
        entities.append(BYDSpeedSensor(speed_updater))

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

        # Set default options for ENUM/Status sensors
        if data_key == DATA_KEY_CAR_STATUS or device_class == SensorDeviceClass.ENUM:
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

        _LOGGER.debug(
            "BYDCarSensor (%s) received update event. Data found: %s. Full Event Keys: %s",
            self._data_key,
            new_state,
            list(parsed_data.keys())
        )

        if new_state is not None:
            if new_state != self.native_value:
                self._attr_native_value = new_state
                self.async_write_ha_state()
            else:
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
# NEW: Dedicated Car Status Sensor with Speed Override Logic
# ----------------------------------------------------------------------
class BYDCarStatusSensor(BYDCarSensor):
    """
    Specialized sensor for car status that listens to the main payload
    (for 'Powered Off', 'Started') and the dedicated speed sensor state
    (for 'Idle', 'Driving').
    """

    def __init__(self, hass, entry_id, data_key, model_name_base, model_name_title):
        """Initialize the car status sensor."""
        super().__init__(
            hass, entry_id, data_key, model_name_base, model_name_title,
            name="Car Status", unit=None, device_class=SensorDeviceClass.ENUM, state_class=None
        )
        # Construct the entity ID of the speed sensor it needs to track
        # Assumes the speed sensor is named like: sensor.byd_dolphin_car_speed_kmh
        self._speed_entity_id = f"sensor.{DOMAIN}_{model_name_base}_{DATA_KEY_SPEED}"

        # Store status from the main payload (used as fallback when speed is unavailable/unknown)
        self._main_payload_status = None
        self._attr_native_value = "Unknown"
        self._attr_icon = "mdi:car"

    async def async_added_to_hass(self):
        """Register listeners for both the main update event and the speed entity state change."""

        # 1. Register listener for the main payload event (inherits _handle_update via super)
        # We override _handle_update below to customize behavior.
        await super().async_added_to_hass()

        # 2. Register listener for speed entity state changes
        @callback
        def async_speed_state_listener(event):
            """Handle speed sensor state changes to update car status."""

            # The speed sensor is an HA entity, check its new state
            new_state: State | None = event.data.get("new_state")
            if not new_state or new_state.state in ('unknown', 'unavailable'):
                # If speed is unavailable, the state will eventually fall back to _main_payload_status
                # or remain at the last determined state.
                return

            self._check_and_set_speed_based_status(new_state, is_realtime_update=True)

        # Register the state change listener for the dedicated speed sensor
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._speed_entity_id], async_speed_state_listener
            )
        )

    @callback
    def _handle_update(self, event):
        """
        Overrides the base handler.
        Updates the internal main payload status and then forces a speed check
        to ensure consistency if the car is "Started".
        """
        parsed_data = event.data
        main_payload_status = parsed_data.get(self._data_key)

        if main_payload_status:
            self._main_payload_status = main_payload_status

            # 1. If the car is Powered Off, that is the definitive status.
            if self._main_payload_status == "Powered Off":
                if self.native_value != self._main_payload_status:
                    self._attr_native_value = self._main_payload_status
                    _LOGGER.debug("Car status set to definitive state: %s", self._main_payload_status)
                    self.async_write_ha_state()
                return

            # 2. If the car is 'Started' (or any other intermediate state),
            # we must check the speed sensor's current state right away.
            speed_state = self.hass.states.get(self._speed_entity_id)
            self._check_and_set_speed_based_status(speed_state, is_realtime_update=False)

        # Write state regardless of change to update other attributes if necessary
        self.async_write_ha_state()

    @callback
    def _check_and_set_speed_based_status(self, speed_state: State | None, is_realtime_update: bool):
        """Internal helper to determine Idle/Driving status from a State object."""
        if not speed_state or speed_state.state in ('unknown', 'unavailable'):
            # If speed is unknown, and the main payload state is 'Started', use that as a fallback.
            if self._main_payload_status in ["Started"] and self.native_value != self._main_payload_status and not is_realtime_update:
                 self._attr_native_value = self._main_payload_status
                 self.async_write_ha_state()
            return

        try:
            current_speed = float(speed_state.state)

            new_status = None
            if current_speed > 0:
                new_status = "Driving"
            elif current_speed == 0:
                new_status = "Idle"

            if new_status and self.native_value != new_status:
                self._attr_native_value = new_status
                _LOGGER.debug("Car status finalized to %s based on current speed (%s km/h)", new_status, current_speed)
                self.async_write_ha_state()

        except (ValueError, TypeError):
            _LOGGER.debug("Speed state is non-numeric, cannot determine Idle/Driving.")


# ----------------------------------------------------------------------
# DIRECT MQTT UPDATER CLASS (Handles subscription and state storage)
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
        self._is_subscribed = False # Track subscription status

        # Device info for consumers to reuse
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": f"BYD {model_name_title}",
            "manufacturer": "BYD",
            "model": model_name_title,
        }

    async def async_added_to_hass(self):
        """Subscribe to the dedicated SOC MQTT topic."""
        if self._is_subscribed:
            return

        _LOGGER.debug("BYDBatteryUpdater subscribing to topic: %s", self._soc_topic)

        @callback
        def mqtt_message_received(message):
            """Handle new MQTT messages received on the SoC topic."""

            try:
                # --- FIX: Use the safe decoder helper function ---
                payload_str = _safe_decode_payload(message.payload)
                if payload_str is None:
                    _LOGGER.warning("Received unprocessable payload on %s: %s", self._soc_topic, message.payload)
                    return
                # --- END FIX ---

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
        if not self._updater._is_subscribed:
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


# ----------------------------------------------------------------------
# DIRECT MQTT UPDATER CLASS for Speed (Handles subscription and state storage)
# ----------------------------------------------------------------------
class BYDSpeedUpdater:
    """A shared component to subscribe to the /speed topic and update vehicle speed."""

    def __init__(self, hass, entry_id, model_name_base, model_name_title, speed_topic):
        self.hass = hass
        self._speed_topic = speed_topic

        # Store for consumers to build unique IDs and names
        self.model_name_base = model_name_base
        self.model_name_title = model_name_title

        # State storage for the sensor
        self.vehicle_speed = None

        # List of callbacks to notify consumers (the speed sensor entity)
        self._callbacks = []
        self._is_subscribed = False # Track subscription status

        # Device info for consumers to reuse
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": f"BYD {model_name_title}",
            "manufacturer": "BYD",
            "model": model_name_title,
        }

    async def async_added_to_hass(self):
        """Subscribe to the dedicated speed MQTT topic."""
        if self._is_subscribed:
            return

        _LOGGER.debug("BYDSpeedUpdater subscribing to topic: %s", self._speed_topic)

        @callback
        def mqtt_message_received(message):
            """Handle new MQTT messages received on the speed topic."""

            try:
                # --- FIX: Use the safe decoder helper function ---
                payload_str = _safe_decode_payload(message.payload)
                if payload_str is None:
                    _LOGGER.warning("Received unprocessable payload on %s: %s", self._speed_topic, message.payload)
                    return
                # --- END FIX ---

                # Speed is typically an integer or float representing km/h
                new_speed = int(float(payload_str))

                # 1. Update internal state
                self.vehicle_speed = new_speed

                # 2. Notify all listening sensor entities
                for callback_fn in self._callbacks:
                    callback_fn()

            except ValueError:
                _LOGGER.error("Received non-numeric payload on %s: '%s'", self._speed_topic, message.payload)
            except Exception as e:
                _LOGGER.error("Unexpected error processing MQTT message on %s: %s", self._speed_topic, e)

        # Start subscription as a task
        self.hass.async_create_task(
            mqtt.async_subscribe(self.hass, self._speed_topic, mqtt_message_received, qos=0)
        )

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
# Sensor: Vehicle Speed (Consumer)
# ----------------------------------------------------------------------
class BYDSpeedSensor(SensorEntity):
    """Vehicle speed sensor updated via direct MQTT subscription."""

    def __init__(self, updater: BYDSpeedUpdater):
        """Initialize the sensor."""
        self._updater = updater

        # Use attributes from the updater for naming and IDs
        self._attr_unique_id = f"{DOMAIN}_{updater.model_name_base}_{DATA_KEY_SPEED}"
        self._attr_name = f"BYD {updater.model_name_title} Vehicle Speed"
        self._attr_device_class = SensorDeviceClass.SPEED
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfSpeed.KILOMETERS_PER_HOUR
        self._attr_device_info = updater._attr_device_info # Reuse device info

    async def async_added_to_hass(self):
        """Register the entity's callback with the shared updater and start subscription."""

        # Ensure the updater is initialized and starts its subscription
        if not self._updater._is_subscribed:
             await self._updater.async_added_to_hass()

        # Register the callback to update this sensor using the standard HA pattern
        self.async_on_remove(self._updater.register_callback(self.async_write_ha_state))

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._updater.vehicle_speed