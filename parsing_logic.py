"""
Core parsing logic for the BYD Car MQTT integration.
This module contains the function to extract data from the raw, non-JSON 
MQTT payload using regular expressions.
"""
import re
from datetime import datetime, timezone, timedelta 

def parse_byd_payload(raw_payload: str) -> dict:
    """
    Parses the raw BYD notification text using regular expressions 
    and returns a dictionary of clean data points.
    """
    
    # 1. Define the regex patterns for properties common to most payloads
    patterns = {
        # Time fields (compatible with both message types)
        "charge_time": r"充能时间：\s*([\d\-\s:]+)",
        "detection_time": r"检测时间：\s*([\d\-\s:]+)",
        
        # Mileage (compatible with most message types)
        "mileage_km": r"总里程\(km\)：\s*([\d\.]+)", 
        
        # Status Detection Data (from the second message type, likely '能耗提醒' or general update)
        # --- UPDATED KEYS TO MATCH 'sensor.py' STATUS REPORT SENSORS ---
        "battery_percent_report": r"电量\(%\)：\s*([\d\.]+)",
        "battery_energy_kwh_report": r"电量\(kwh\)：\s*([\d\.]+)",
        "remaining_range_km": r"电量剩余里程\(km\)：\s*([\d\.]+)",
        "battery_health": r"电池健康：\s*(\d+)",
        
        # --- NEW SENSORS FROM POWERED OFF PAYLOAD (or general status) ---
        "consumption_kwh_50km": r"近50KM电耗\(kWh\)：\s*([\d\.]+)", 
        "external_temperature_celsius": r"车外温度：\s*([\d\.]+)", 
        
        # ⬅️ NEW: FAN SPEED (0-7)
        # Using a likely Chinese label (空调风量: Air Conditioning Air Volume)
        "fan_speed": r"空调风量：\s*(\d)", 
    }
    
    # 2. Define patterns specific to the CHARGING SESSION ('补能提醒')
    charge_patterns = {
        "start_battery_pct": r"起始电量\(%\)：\s*([\d\.]+)",
        "end_battery_pct": r"结束电量\(%\)：\s*([\d\.]+)",
        "charge_amount_pct": r"充电量\(%\)：\s*([\d\.]+)", 
        "charge_amount_kwh_total": r"充电量\(kWh\)：\s*([\d\.]+)", 
        "charge_distance_km": r"充电里程\(km\)：\s*([\d\.]+)",
    }
    
    parsed_data = {}
    is_charging_session = False 
    
    # --- 1. DETECT CAR STATUS EVENT (PRIORITY) ---
    
    # Check for Car Powered Off event (熄火提醒)
    if "熄火提醒" in raw_payload:
        parsed_data["car_status"] = "Powered Off"
    
    # Check for Car Started event (启动提醒)
    elif re.search(r"启动提醒", raw_payload):
        parsed_data["car_status"] = "Started"
        
    # Check for Charging Reminder (补能提醒)
    if "补能提醒" in raw_payload: 
        is_charging_session = True
        
    
    # --- 2. Parse Single-Value Properties (Conditional Parsing) ---
    has_numeric_data = False
    
    # A. Always parse the general patterns
    for key, pattern in patterns.items(): # This now includes 'fan_speed'
        match = re.search(pattern, raw_payload)
        if match:
            value_str = match.group(1).strip()
            
            # Timestamp conversion logic
            if 'time' in key:
                try:
                    naive_dt = datetime.strptime(value_str, "%Y-%m-%d %H:%M:%S")
                    utc_offset = timezone(timedelta(hours=8)) 
                    parsed_data[key] = naive_dt.replace(tzinfo=utc_offset)
                except ValueError:
                    parsed_data[key] = None
            else:
                try:
                    # Integer conversion is suitable for fan speed (0-7)
                    parsed_data[key] = float(value_str) if '.' in value_str else int(value_str)
                    has_numeric_data = True
                except ValueError:
                    parsed_data[key] = None

    # B. ONLY parse the charging session patterns if the payload is a '补能提醒'
    if is_charging_session:
        for key, pattern in charge_patterns.items():
            match = re.search(pattern, raw_payload)
            if match:
                value_str = match.group(1).strip()
                try:
                    parsed_data[key] = float(value_str) if '.' in value_str else int(value_str)
                    has_numeric_data = True
                except ValueError:
                    parsed_data[key] = None

    # --- 3. Parse Grouped Properties (Tire Pressure, Temp, Window) ---
    
    # Tire Pressure (kpa)
    tpms_pattern = r"各项胎压\(kpa\)：\s*左前：(\d+)\s*右前：(\d+)\s*左后：(\d+)\s*右后：(\d+)"
    tpms_match = re.search(tpms_pattern, raw_payload)
    if tpms_match:
        lf, rf, lr, rr = tpms_match.groups()
        parsed_data["tpms_lf_kpa"] = int(lf)
        parsed_data["tpms_rf_kpa"] = int(rf)
        parsed_data["tpms_lr_kpa"] = int(lr)
        parsed_data["tpms_rr_kpa"] = int(rr)
        has_numeric_data = True

    # Tire Temperature (℃)
    tt_pattern = r"轮胎温度\(℃\)：\s*左前：(\d+)\s*右前：(\d+)\s*左后：(\d+)\s*右后：(\d+)"
    tt_match = re.search(tt_pattern, raw_payload)
    if tt_match:
        lf, rf, lr, rr = tt_match.groups()
        parsed_data["tt_lf_celsius"] = int(lf)
        parsed_data["tt_rf_celsius"] = int(rf)
        parsed_data["tt_lr_celsius"] = int(lr)
        parsed_data["tt_rr_celsius"] = int(rr)
        has_numeric_data = True
        
    # Window Status (0/1)
    win_pattern = r"车窗状态：\s*左前：(\d+)\s*右前：(\d+)\s*左后：(\d+)\s*右后：(\d+)\s*天窗：(\d+)"
    win_match = re.search(win_pattern, raw_payload)
    if win_match:
        lf, rf, lr, rr, sunroof = win_match.groups()
        parsed_data["win_lf_open"] = int(lf) == 1
        parsed_data["win_rf_open"] = int(rf) == 1
        parsed_data["win_lr_open"] = int(lr) == 1
        parsed_data["win_rr_open"] = int(rr) == 1
        parsed_data["sunroof_open"] = int(sunroof) == 1
        has_numeric_data = True

    # --- 4. DEFAULT CAR STATUS LOGIC ---
    if "car_status" not in parsed_data:
        if has_numeric_data:
            parsed_data["car_status"] = "Idle"
        else:
            parsed_data["car_status"] = "Unknown"
            
    return parsed_data