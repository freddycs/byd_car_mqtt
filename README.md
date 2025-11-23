# 🚗 BYD Car MQTT Integration for Home Assistant
[releases-shield]: https://img.shields.io/github/release/freddycs/byd_car_mqtt.svg
[version-shield]: https://img.shields.io/badge/version-0.1.0-blue.svg
[license-shield]: https://img.shields.io/github/license/freddycs/byd_car_mqtt.svg

[releases]: https://github.com/freddycs/byd_car_mqtt
[license]: https://github.com/freddycs/byd_car_mqtt/blob/main/LICENSE

[![GitHub Release][releases-shield]][releases]
[![Version][version-shield]][releases]
[![License][license-shield]][license]
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

This is a custom Home Assistant integration that connects to a **BYD vehicle** (such as Dolphin, Atto 3/Yuan Plus, Seal, etc.) via an **external MQTT telemetry sender/bridge**.

Specifically, this integration is designed to consume the telemetry data published by the third-party car launcher **DiLauncher** (also known as **迪粉桌面**).

This integration is purely a **data consumer** and does not directly poll or communicate with the BYD servers or the car itself. It relies on a separate process (the "telemetry sender") publishing structured data to your local MQTT broker.

---

## ✨ Features

The integration processes the telemetry data and exposes the following entities in Home Assistant. Note the distinction between real-time data and data that is only updated during power cycles.

| Sensor | Description | Unit | Update Frequency |
| :--- | :--- | :--- | :--- |
| **Battery Level** | Real-time State of Charge (SoC). | % | **Real-Time** (Direct MQTT `/SOC` topic) |
| **Current Battery Energy** | Estimated current energy remaining based on SoC and configured max capacity. | kWh | **Real-Time** (Direct MQTT `/SOC` topic) |
| **Total Mileage** | Vehicle odometer reading. | km | Asynchronous (On Power Cycle / Status Report) |
| **Remaining Range** | Estimated remaining driving range. | km | Asynchronous (On Power Cycle / Status Report) |
| **Car Status** | Current state (Idle, Driving, Powered Off, etc.). | Enum | Asynchronous (On Power Cycle / Status Report) |
| **TPMS (4 Tires)** | Individual tire pressures. | kPa | Asynchronous (On Power Cycle / Status Report) |
| **Tire Temperatures (4 Tires)** | Individual tire temperatures. | °C | Asynchronous (On Power Cycle / Status Report) |
| **External Temperature** | Current outside temperature. | °C | Asynchronous (On Power Cycle / Status Report) |

---

## ⚙️ Prerequisites

Before installing this integration, you **must** have the following running:

1.  **Home Assistant** (running core/superviser).

2.  **An MQTT Broker** (e.g., Mosquitto, set up via the Home Assistant Add-on Store).
    * **CRITICAL:** The MQTT broker **must be externally accessible from the internet** and properly secured, as the DiLauncher application running inside the car sends data back to this broker over the internet. Using a secure VPN or an encrypted connection is highly recommended.

3.  **The DiLauncher (迪粉桌面) Application running in your car** and configured to publish data to your external MQTT broker. *This integration is useless without the data feed from this launcher.*

---

## ⬇️ Installation (HACS)

1.  Open **HACS** in your Home Assistant interface.

2.  Navigate to **Integrations**.

3.  Click the three dots (`...`) in the top right corner and select **Custom repositories**.

4.  Enter the URL of this GitHub repository (`https://github.com/freddycs/byd_car_mqtt`).

5.  Select **Integration** as the category.

6.  Click **ADD**.

7.  HACS will download the repository content. Restart Home Assistant for the component to become available.

---

## 🛠️ Configuration

After installation via HACS, configure the integration via the Home Assistant UI:

1.  Navigate to **Settings** > **Devices & Services**.

2.  Click **ADD INTEGRATION**.

3.  Search for **BYD Car MQTT**.

4.  You will be prompted to enter the following mandatory details:

| Field | Description | Example Value |
| :--- | :--- | :--- |
| **Car Name** | A friendly name for your car (e.g., Dolphin, Atto 3). | `BYD Dolphin` |
| **MQTT Subscribe Topic** | The **base topic** the external telemetry sender uses. | `homeassistant/car/dolphinc` |
| **MQTT Command Topic** | The topic used by Home Assistant to send control commands back to the car (e.g., setting A/C temperature). | `homeassistant/car/command` |
| **Car Unique ID** | A unique identifier for your car (can be VIN or any persistent ID). | `V-1234567890` |
| **Max Battery Capacity (kWh)** | The nominal capacity of your vehicle's battery pack. | `60.48` |

5.  Click **SUBMIT** to complete the setup. The integration will automatically subscribe to the necessary subtopics (`/SOC` for real-time updates and the main topic for status reports).

---
## 🔧 DiLauncher Automations Setup (AC Temp & Fan Speed)

This integration provides a dedicated service to generate a complete JSON file containing all necessary "Conditional Tasks" for the DiLauncher application to enable control over **AC Temperature** and **Fan Speed** via MQTT.
     
**1. Generating the JSON File**
   1. Navigate to Developer Tools in Home Assistant.
   
   2. Go to the Services tab.
  
   3. In the "Service" field, select: `byd_car_mqtt.get_dilauncher_json`.
 
   4. (Optional) You can specify the output file path in the **YAML mode**. If left blank, it defaults to `/config/dilauncher_automations.json`.
  
   `
output_path: dilauncher_automations.json
` 

   5. Click CALL SERVICE.


This action will create a file named `dilauncher_automations.json` (or the name you specified) in your Home Assistant configuration directory (`/config`). This file contains 25 entries: 17 for AC temperatures (17°C to 33°C) and 8 for fan speeds (0 to 7).

## 2. Retrieving and Importing the File

1. **Retrieve the File**: Access the file you just generated (`/config/dilauncher_automations.json`).

   - If you use the **File Editor** add-on, you can navigate directly to the file and download it.

   - If you use **Samba/SSH**, you can copy the file from the root of your Home Assistant configuration directory.

2. **Transfer to Car**: Transfer the downloaded `dilauncher_automations.json` file onto a USB drive.

3. **Import in DiLauncher**:

   - Insert the USB drive into your car's head unit.
 
   - Copy the `dilauncher_automations.json` file to `\download\s` folder in local storage.

   - Open the DiLauncher application.

   - Navigate to the **Conditional Tasks** (or **Task List**) settings.

   - Find the **Import** or **Restore** function and select the JSON file from the USB drive.

Once imported, DiLauncher will have all the necessary conditional tasks configured to listen for the MQTT commands published by Home Assistant, allowing you to control the climate entities.

---

## ⚠️ Disclaimer

This software is provided "as is" under the MIT License. I assume no liability for any damage to you or any other person or equipment resulting from the use or misuse of this integration or the third-party launcher it relies upon.

---

## 🪲 Debugging and Logging

If you encounter issues, you can increase the logging level for this component by adding the following to your `configuration.yaml` file:

```yaml
logger:
  default: warning
  logs:
    custom_components.byd_car_mqtt: debug


