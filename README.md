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
| **MQTT Subscribe Topic** | The **base topic** the external telemetry sender uses. | `/dolphin_status` |
| **MQTT Command Topic** | The topic used by Home Assistant to send control commands back to the car (e.g., setting A/C temperature). | `/dolphin_command` |
| **Car Unique ID** | A unique identifier for your car (can be VIN or any persistent ID). | `V-1234567890` |
| **Max Battery Capacity (kWh)** | The nominal capacity of your vehicle's battery pack. | `60.48` |

5.   Click **SUBMIT** to go to the next page, check on the `enable_driver_vent` or `enable_passenger_vent` checkbox if your car is equipped with seat ventilation.

6.    Click **SUBMIT** to complete the setup. The integration will automatically subscribe to the necessary subtopics (`/SOC` for real-time updates and the main topic for status reports).
---

## ⬇️Download & install DiLauncher 迪粉桌面
1. Download `迪粉桌面-v2.5.1122.86.66-0900_sign.apk` or the latest version from the developer's official repository https://drive.uc.cn/s/bc4778b7d0db4#/list/share.

2. Transfer the downloaded `迪粉桌面-v2.5.1122.86.66-0900_sign.apk` or the latest version file onto a USB drive. Sideload and install the apk in your BYD head unit. Refer to the official installation guide https://shorturl.at/3TIQG.

## Configure MQTT Connection in DiLauncher 迪粉桌面
1. Go to `Settings (设置）`then select `Add-ins (插件扩展）`from the settings menu.

2. On the right side of the Add-ins Configuration screen, enter the following details:

| Field | Description | Example Value |
| :--- | :--- | :--- |
| **启动MQTT功能（关闭打开可以重新连接)** | Toggle switch to enable or disable MQTT function | `turn off and turn on will reconnect to the MQTT broker` |
| **爱车别名** | A friendly name for your car (e.g., Dolphin, Atto 3). | `BYD Dolphin` |
| **服务器** | Your Home Assistant server address. | `https://homeassistant.duckdns.org` |
| **端口** | Your MQTT broker port number. | `1883` |
| **账号** | Your MQTT username. | `byd` |
| **密码** | Your MQTT password. | `abc123` |
| **接收信息的主题** | **MQTT Subscribe Topic** - The **base topic** the external telemetry sender uses. | `/dolphin_status` |
| **发送信息的主题** | **MQTT Command Topic** - The topic used by Home Assistant to send control commands back to the car (e.g., setting A/C temperature). | `/dolphin_command` |
| **链接方式** | Toggle switch for connection type (TCP or SSL) | `TCP` |

---
## 🔧 DiLauncher Automations Setup (Battery SOC, AC Temperature & Fan Speed)

This integration provides a dedicated service to generate a complete JSON file containing all necessary "Conditional Tasks" for the DiLauncher application to send the latest state of **Battery SOC**, **AC Temperature** and **Fan Speed** via MQTT to Home Assistant.
     
**1. Generating the JSON File**
   1. Navigate to `Settings` in Home Assistant.
   
   2. Select `Devices & Services`.
  
   3. Go to `BYD Car MQTT Status` integration and select your car model.
 
   4. Under the Controls section, click on the `Generate DiLauncher Automations JSON` button.
   
This action will create a file named `dilauncher_automations.json` in your Home Assistant configuration directory (`/config`). This file contains 25 entries: 17 for AC temperatures (17°C to 33°C) and 8 for fan speeds (0 to 7).

## 2. Retrieving and Importing the File

1. **Retrieve the File**: Access the file you just generated (`/config/dilauncher_automations.json`).

   - If you use the **File Editor** add-on, you can navigate directly to the file and download it.

   - If you use **Samba/SSH**, you can copy the file from the root of your Home Assistant configuration directory.

2. **Transfer to Car**: Transfer the downloaded `dilauncher_automations.json` file onto a USB drive.

3. **Import in DiLauncher**:

   - Insert the USB drive into your car's head unit.
 
   - Copy the `dilauncher_automations.json` file to `\download\s` folder in the local storage.

   - Open the DiLauncher application.

   - Navigate to the **Settings 设置** menu and select **Conditional Tasks 条件联动**.

   - Click on **Import Automation 导入智能场景** button and select the JSON file from `/download/s` folder.

Once imported, DiLauncher will have all the necessary conditional tasks configured to send MQTT message to Home Assistant, updating the state of the AC Temperature, Battery SOC and Fan Speed.

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


