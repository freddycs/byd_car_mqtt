import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    DOMAIN, 
    # Import all necessary configuration constants
    CONF_MQTT_TOPIC_SUBSCRIBE, # <-- Added this missing import
    CONF_MQTT_TOPIC_COMMAND, 
    CONF_CAR_UNIQUE_ID,
    CONF_ENABLE_DRIVER_VENT,     # <-- NEW
    CONF_ENABLE_PASSENGER_VENT,  # <-- NEW
)

# --- STEP 1: Core Setup Schema (Mandatory Fields) ---
CORE_SETUP_SCHEMA = vol.Schema({
    # The topic HA listens to for status updates (using the imported const name)
    vol.Required(CONF_MQTT_TOPIC_SUBSCRIBE, default="/dolphinc"): str,
    
    # The topic HA publishes commands to
    vol.Required(CONF_MQTT_TOPIC_COMMAND, default="BYD/Dolphin/command"): str, 
    
    # The unique ID required for the command payload
    vol.Required(CONF_CAR_UNIQUE_ID): str, 
    
    # The default name for the device
    vol.Required("model_name", default="BYD Dolphin"): str, 
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

            # Create a stable unique ID for the config entry based on the model name
            model_unique_id = final_data["model_name"].lower().replace(" ", "_")
            await self.async_set_unique_id(model_unique_id)
            self._abort_if_unique_id_configured()

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
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler (Optional for minor changes)."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for BYD Car MQTT."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        # For now, we only show the new optional features here.
        
        # Load current options/data to pre-fill the form
        data = {
            CONF_ENABLE_DRIVER_VENT: self.config_entry.data.get(CONF_ENABLE_DRIVER_VENT, True),
            CONF_ENABLE_PASSENGER_VENT: self.config_entry.data.get(CONF_ENABLE_PASSENGER_VENT, True),
        }
        
        # Merge into a schema with current values as defaults
        options_schema = vol.Schema({
            vol.Optional(CONF_ENABLE_DRIVER_VENT, default=data[CONF_ENABLE_DRIVER_VENT]): bool,
            vol.Optional(CONF_ENABLE_PASSENGER_VENT, default=data[CONF_ENABLE_PASSENGER_VENT]): bool,
        })

        if user_input is not None:
            # Create a new entry with updated data
            new_data = self.config_entry.data.copy()
            new_data.update(user_input)
            return self.async_create_entry(title=self.config_entry.title, data=new_data)


        return self.async_show_form(step_id="init", data_schema=options_schema)