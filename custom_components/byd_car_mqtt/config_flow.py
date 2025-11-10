import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv 
from homeassistant.config_entries import ConfigEntry

from .const import (
    DOMAIN, 
    # Import all necessary configuration constants
    CONF_MQTT_TOPIC_SUBSCRIBE, 
    CONF_MQTT_TOPIC_COMMAND, 
    CONF_CAR_UNIQUE_ID,
    CONF_ENABLE_DRIVER_VENT,
    CONF_ENABLE_PASSENGER_VENT,
    # --- NEW CONSTANTS FOR BATTERY CAPACITY ---
    CONF_MAX_BATTERY_CAPACITY_KWH, 
    DEFAULT_MAX_BATTERY_CAPACITY_KWH, 
)

# --- STEP 1: Core Setup Schema (Mandatory Fields) ---
CORE_SETUP_SCHEMA = vol.Schema({
    # The topic HA listens to for status updates
    vol.Required(CONF_MQTT_TOPIC_SUBSCRIBE, default="/dolphinc"): str,
    
    # The topic HA publishes commands to
    vol.Required(CONF_MQTT_TOPIC_COMMAND, default="BYD/Dolphin/command"): str, 
    
    # The unique ID required for the command payload
    vol.Required(CONF_CAR_UNIQUE_ID): str, 
    
    # The default name for the device
    vol.Required("model_name", default="BYD Dolphin"): str, 
    
    # --- NEW: Configurable Battery Capacity (e.g., 60.48 for Extended Range, 44.9 for Standard) ---
    vol.Required(
        CONF_MAX_BATTERY_CAPACITY_KWH, 
        default=DEFAULT_MAX_BATTERY_CAPACITY_KWH
    ): vol.All(vol.Coerce(float), vol.Range(min=20.0, max=100.0)), # Enforce float, set reasonable range
})


# --- STEP 2: Optional Features Schema (Optional Fields) ---
OPTIONAL_FEATURES_SCHEMA = vol.Schema({
    # Add optional boolean fields for ventilation
    vol.Optional(CONF_ENABLE_DRIVER_VENT, default=True): bool,
    vol.Optional(CONF_ENABLE_PASSENGER_VENT, default=True): bool,
})


class BYDCarMQTTConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BYD Car MQTT."""

    VERSION = 1
    # Storage for user input from the first step
    _config_data = {} 

    async def async_step_user(self, user_input=None):
        """Handle the initial step (Core Setup)."""
        errors = {}

        if user_input is not None:
            # Store data from step 1 and proceed to step 2
            self._config_data.update(user_input)
            
            # Use the car unique ID for the set_unique_id call, as the model_name may change
            car_unique_id = user_input.get(CONF_CAR_UNIQUE_ID)
            await self.async_set_unique_id(car_unique_id)
            self._abort_if_unique_id_configured()
            
            return await self.async_step_optional_features()

        # Show the form to the user
        return self.async_show_form(
            step_id="user", 
            data_schema=CORE_SETUP_SCHEMA, 
            errors=errors
        )

    async def async_step_optional_features(self, user_input=None):
        """Handle the second step (Optional Features)."""
        errors = {}

        if user_input is not None:
            # Combine data from both steps
            final_data = self._config_data.copy()
            final_data.update(user_input)

            # Create the config entry, storing all data
            return self.async_create_entry(
                title=final_data["model_name"], 
                data=final_data
            )

        # Show the form for optional features
        return self.async_show_form(
            step_id="optional_features", 
            data_schema=OPTIONAL_FEATURES_SCHEMA, 
            errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        """Get the options flow for this handler (Optional for minor changes)."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for BYD Car MQTT, managing toggles and battery capacity."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        # Fix 1: Call parent constructor with no arguments
        super().__init__() 
        
        # Store the config_entry locally
        self.config_entry = config_entry


    async def async_step_init(self, user_input=None):
        """Manage the options. Safe place to access self.options and self.config_entry."""
        
        # Consolidate data from both 'data' (initial setup) and 'options' (previous config changes)
        config_data = dict(self.config_entry.data)
        
        # FIX 2: Access options via self.config_entry.options, not self.options, 
        # to guarantee the property exists and is initialized.
        config_data.update(self.config_entry.options) 

        if user_input is not None:
            # Save the new input directly to the options dictionary
            # Returning user_input as data will save it to the entry's options
            return self.async_create_entry(title="", data=user_input)

        # --- Define the Options Form Schema ---
        options_schema = vol.Schema({
            # 1. Driver Vent Toggle
            vol.Optional(
                CONF_ENABLE_DRIVER_VENT, 
                # Use the combined config_data to get the current state
                default=config_data.get(CONF_ENABLE_DRIVER_VENT, True) 
            ): bool,
            
            # 2. Passenger Vent Toggle
            vol.Optional(
                CONF_ENABLE_PASSENGER_VENT, 
                # Use the combined config_data to get the current state
                default=config_data.get(CONF_ENABLE_PASSENGER_VENT, True)
            ): bool,

            # 3. Battery Capacity (NEW)
            vol.Required(
                CONF_MAX_BATTERY_CAPACITY_KWH,
                # Use the combined config_data to get the current state
                default=config_data.get(CONF_MAX_BATTERY_CAPACITY_KWH, DEFAULT_MAX_BATTERY_CAPACITY_KWH)
            ): vol.All(vol.Coerce(float), vol.Range(min=20.0, max=100.0)),
        })

        return self.async_show_form(
            step_id="init", 
            data_schema=options_schema,
            description_placeholders={"model": self.config_entry.title}
        )