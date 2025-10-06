

from __future__ import annotations

import csv
import datetime
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import h5py
import matplotlib.pyplot as plt
import numpy as np


@dataclass
class ECGSample:
    sample_num: int
    analog_value: float
    timestamp_ns: int
    timestamp_seconds: float


class EKGSync:
    def __init__(self) -> None:
        self.h5_path: Optional[str] = None
        self.holo_unix_first: Optional[float] = None
        self.holo_unix_last: Optional[float] = None
        self.arterial_velocity: Optional[np.ndarray] = None

        self.ecg_samples: List[ECGSample] = []

    def load_h5(self, path: str) -> None:
        if not os.path.exists(path):
            raise FileNotFoundError(path)

        with h5py.File(path, 'r') as h5f:
            try:
                unix_first_arr = h5f['/UnixTimestampFirst'][:]
                unix_last_arr = h5f['/UnixTimestampLast'][:]
                self.holo_unix_first = float(unix_first_arr[0]) if len(unix_first_arr) > 0 else float(unix_first_arr)
                self.holo_unix_last = float(unix_last_arr[0]) if len(unix_last_arr) > 0 else float(unix_last_arr)
            except Exception as e:  # pragma: no cover - defensive
                raise RuntimeError(f"Failed to read UnixTimestampFirst/Last: {e}")

            try:
                self.arterial_velocity = np.array(h5f['/SignalsArterialVelocity_y'][:])
            except Exception:
                # store None if not present
                self.arterial_velocity = None

        self.h5_path = path

    # ------------------------- ECG Loading -------------------------
    def load_ecg_csv(self, path: str, timestamp_ns_field: str = 'timestamp_ns') -> None:
        if not os.path.exists(path):
            raise FileNotFoundError(path)

        samples: List[ECGSample] = []
        with open(path, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    sample_num = int(row.get('sample_num') or row.get('Sample#') or 0)
                except Exception:
                    sample_num = 0
                try:
                    analog_value = float(row.get('analog_value') or row.get('analog') or row.get('Analog') or 0.0)
                except Exception:
                    analog_value = 0.0
                try:
                    timestamp_ns = int(row.get('timestamp_ns') or row.get('Timestamp_ns') or 0)
                except Exception:
                    ts_seconds = float(row.get('timestamp_seconds') or row.get('Timestamp_seconds') or 0.0)
                    timestamp_ns = int(ts_seconds * 1_000_000_000)
                try:
                    timestamp_seconds = float(row.get('timestamp_seconds') or row.get('Timestamp_seconds') or (timestamp_ns / 1_000_000_000))
                except Exception:
                    timestamp_seconds = timestamp_ns / 1_000_000_000

                samples.append(ECGSample(sample_num=sample_num, analog_value=analog_value, timestamp_ns=timestamp_ns, timestamp_seconds=timestamp_seconds))

        samples.sort(key=lambda s: s.timestamp_ns)
        self.ecg_samples = samples

    def find_nearest_sample_index(self, target_ns: int) -> Optional[int]:
        if not self.ecg_samples:
            return None

        timestamps = [s.timestamp_ns for s in self.ecg_samples]
        idx = int(np.searchsorted(timestamps, target_ns))
        if idx <= 0:
            return 0
        if idx >= len(timestamps):
            return len(timestamps) - 1

        before = idx - 1
        # choose closer of before and idx
        if abs(timestamps[before] - target_ns) <= abs(timestamps[idx] - target_ns):
            return before
        return idx

    def trim_ecg_to_holo(self) -> Tuple[List[ECGSample], Dict[str, Any]]:
        if self.holo_unix_first is None or self.holo_unix_last is None:
            raise RuntimeError('HDF5 holo timestamps not loaded')
        if not self.ecg_samples:
            raise RuntimeError('ECG samples not loaded')

        holo_first_ns = int(self.holo_unix_first * 1_000)
        holo_last_ns = int(self.holo_unix_last * 1_000)

        start_idx = self.find_nearest_sample_index(holo_first_ns)
        end_idx = self.find_nearest_sample_index(holo_last_ns)

        if start_idx is None or end_idx is None:
            raise RuntimeError('Could not find nearest ECG samples')

        if start_idx > end_idx:
            start_idx, end_idx = end_idx, start_idx

        trimmed = self.ecg_samples[start_idx:end_idx + 1]

        info: Dict[str, Any] = {
            'start_idx': start_idx,
            'end_idx': end_idx,
            'start_sample': trimmed[0] if trimmed else None,
            'end_sample': trimmed[-1] if trimmed else None,
            'holo_first_ns': holo_first_ns,
            'holo_last_ns': holo_last_ns,
            'start_time_diff_ns': abs(trimmed[0].timestamp_ns - holo_first_ns) if trimmed else None,
            'end_time_diff_ns': abs(trimmed[-1].timestamp_ns - holo_last_ns) if trimmed else None,
        }

        return trimmed, info

    def save_trimmed_csv(self, samples: List[ECGSample], path: str) -> None:
        fieldnames = ['sample_num', 'analog_value', 'timestamp_ns', 'timestamp_seconds']
        with open(path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for s in samples:
                writer.writerow({'sample_num': s.sample_num, 'analog_value': s.analog_value, 'timestamp_ns': s.timestamp_ns, 'timestamp_seconds': s.timestamp_seconds})

    def save_trimmed_json(self, samples: List[ECGSample], path: str) -> None:
        out = [s.__dict__ for s in samples]
        with open(path, 'w') as f:
            json.dump(out, f, indent=2)

    def plot_combined(self, trimmed_samples: List[ECGSample], show: bool = True) -> None:
        """Quick plot: arterial velocity (if available) and ECG trimmed segment."""
        plt.figure(figsize=(12, 6))

        if self.arterial_velocity is not None:
            ax1 = plt.subplot(2, 1, 1)
            duration_sec = (self.holo_unix_last - self.holo_unix_first) / 1_000_000 if (self.holo_unix_last and self.holo_unix_first) else None
            vel_t = np.linspace(0, float(duration_sec), len(self.arterial_velocity)) if duration_sec else np.arange(len(self.arterial_velocity))
            ax1.plot(vel_t, self.arterial_velocity, 'r-')
            ax1.set_title('Arterial Velocity (HDF5)')
            ax1.set_xlabel('Time (s)')
            ax1.grid(True, alpha=0.3)

        ax2 = plt.subplot(2, 1, 2) if self.arterial_velocity is not None else plt.subplot(1, 1, 1)
        if trimmed_samples:
            ecg_t0 = trimmed_samples[0].timestamp_seconds
            t = [s.timestamp_seconds - ecg_t0 for s in trimmed_samples]
            v = [s.analog_value for s in trimmed_samples]
            ax2.plot(t, v, 'b-')
            ax2.set_title('Trimmed ECG')
            ax2.set_xlabel('Time (s)')
            ax2.grid(True, alpha=0.3)

        if show:
            plt.tight_layout()
            plt.show()


def _demo_cli():
    import argparse

    p = argparse.ArgumentParser(description='Simple EKG/Holo sync demo')
    p.add_argument('--h5', required=True, help='Path to holo HDF5 file')
    p.add_argument('--ecg', required=True, help='Path to ECG CSV file')
    p.add_argument('--out', help='Path to write trimmed CSV (optional)')
    args = p.parse_args()

    s = EKGSync()
    s.load_h5(args.h5)
    s.load_ecg_csv(args.ecg)
    trimmed, info = s.trim_ecg_to_holo()
    print('Trim info:', info)
    if args.out:
        s.save_trimmed_csv(trimmed, args.out)
        print('Wrote', args.out)
    s.plot_combined(trimmed)


if __name__ == '__main__':
    _demo_cli()
