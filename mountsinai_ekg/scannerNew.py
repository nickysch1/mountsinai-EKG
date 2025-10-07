# scanner.py
from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional

import pyfirmata2

_ecg_scan_stop_flag = threading.Event()


def _parse_analog_index(analog_pin: str) -> int:
    s = analog_pin.strip().lower()
    if s.startswith("a:"):
     
        try:
            return int(s.split(":")[1])
        except Exception:
            pass
    if s.startswith("a"):
        
        try:
            return int(s[1:])
        except Exception:
            pass
   
    return int(s)


def start_ecg_scan(
    board: "pyfirmata2.Arduino",
    analog_pin: str = "a:0:i",
    target_hz: int = 200,
    data_callback=None,
    analog_input: Optional[Any] = None,
):

    ECG_data: list[Dict[str, Any]] = []
    _ecg_scan_stop_flag.clear()

    sampling_interval_ms = max(1, int(1000 / max(1, int(target_hz))))

    if analog_input is not None:
        a_pin = analog_input
    else:
        idx = _parse_analog_index(analog_pin)
        a_pin = board.analog[idx]
    board.samplingOn(sampling_interval_ms)

    sample_counter = 0

    def _on_sample(value: float):
        nonlocal sample_counter
        sample_counter += 1
        ts_ns = time.time_ns()
        sample = {
            "sample_num": sample_counter,
            "analog_value": value,  
            "timestamp_ns": ts_ns,
            "timestamp_seconds": ts_ns / 1_000_000_000,
        }
        ECG_data.append(sample)
        if data_callback:
            try:
                data_callback(sample)
            except Exception as _:
                pass

    a_pin.register_callback(_on_sample)
    a_pin.enable_reporting()

    try:
        while not _ecg_scan_stop_flag.is_set():
            time.sleep(0.01) 
    finally:

        try:
            a_pin.disable_reporting()
        except Exception:
            pass
        try:
            board.samplingOff()
        except Exception:
            pass

    return ECG_data


def stop_ecg_scan():

    _ecg_scan_stop_flag.set()


def connect_to_arduino(port: str | None = None):
    try:
        if port is None or (isinstance(port, str) and port.strip().lower() == "auto"):
            port_to_use = pyfirmata2.Arduino.AUTODETECT
        else:
            port_to_use = str(port).strip()
        board = pyfirmata2.Arduino(port_to_use)
        print(f"Connected to Arduino on {port_to_use}!")
        return board
    except Exception as e:
        print(f"Failed to connect to Arduino on {port!r}: {e}")
        return None
