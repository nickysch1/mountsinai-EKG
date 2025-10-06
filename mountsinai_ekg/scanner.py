import threading
import time
import datetime
import struct
import os
import json
from typing import Dict, Any
import h5py
import matplotlib.pyplot as plt
import numpy as np 
import csv

_ecg_scan_stop_flag = threading.Event()

def start_ecg_scan(board, analog_pin='a:0:i', target_hz=200, data_callback=None, analog_input=None):
    import time
    ECG_data = []
    _ecg_scan_stop_flag.clear()
    try:
        it = pyfirmata2.util.Iterator(board)
        it.start()
        if analog_input is not None:
            analogInput = analog_input
        else:
            analogInput = board.get_pin(analog_pin)
        test = 0
        target_interval = 1.0 / target_hz
        perf_start_ns = time.perf_counter_ns()
        target_interval_ns = int(target_interval * 1_000_000_000)
        next_sample_time_ns = perf_start_ns
        print("Sample#, Analog Value, Timestamp (ns)")
        while not _ecg_scan_stop_flag.is_set():
            current_perf_ns = time.perf_counter_ns()
            if current_perf_ns >= next_sample_time_ns:
                test += 1
                analog_value = analogInput.value
                timestamp_ns = time.time_ns()
                current_time = timestamp_ns / 1_000_000_000
                sample = {
                    'sample_num': test,
                    'analog_value': analog_value,
                    'timestamp_ns': timestamp_ns,
                    'timestamp_seconds': current_time
                }
                ECG_data.append(sample)
                if data_callback:
                    data_callback(sample)
                print(f"{test}, {analog_value}, {timestamp_ns}")
                next_sample_time_ns += target_interval_ns
        print(f"Scan stopped. Total samples: {test}")
        return ECG_data
    except Exception as e:
        print(f"Error during ECG collection: {e}")
        return []

def stop_ecg_scan():
    _ecg_scan_stop_flag.set()
import pyfirmata2

def connect_to_arduino(port: str | None = None):
    try:
        if port is None:
            port_to_use = pyfirmata2.Arduino.AUTODETECT
        else:
            p = str(port).strip()
            if not p or p.lower() == "auto":
                port_to_use = pyfirmata2.Arduino.AUTODETECT
            else:
                port_to_use = p
        board = pyfirmata2.Arduino(port_to_use)
        print(f"Connected to Arduino on {port_to_use}!")
        return board
    except Exception as e:
        print(f"Failed to connect to Arduino on {port!r}: {e}")
        return None