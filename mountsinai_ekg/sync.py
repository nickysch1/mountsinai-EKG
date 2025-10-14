

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
            except Exception as e:
                raise RuntimeError(f"Failed to read UnixTimestampFirst/Last: {e}")

            try:
                self.arterial_velocity = np.array(h5f['/SignalsArterialVelocity_y'][:])
            except Exception:
                self.arterial_velocity = None

        self.h5_path = path

    @staticmethod
    def _parse_time_to_seconds(txt):
        return int(txt.strip()) * 1e-6


    def trim_ecg_by_seconds(
        self,
        start_time_s: float,
        end_time_s: float,
        *,
        relative_to_ecg_start: bool = True
    ):

        if not self.ecg_samples:
            raise RuntimeError("ECG samples not loaded")

        if start_time_s > end_time_s:
            start_time_s, end_time_s = end_time_s, start_time_s

        t0 = self.ecg_samples[0].timestamp_seconds
        if relative_to_ecg_start:
            start_abs_s = t0 + start_time_s
            end_abs_s   = t0 + end_time_s
        else:
            start_abs_s = start_time_s
            end_abs_s   = end_time_s

        start_ns = int(start_abs_s * 1_000_000_000)
        end_ns   = int(end_abs_s   * 1_000_000_000)

        s_idx = self.find_nearest_sample_index(start_ns)
        e_idx = self.find_nearest_sample_index(end_ns)
        if s_idx is None or e_idx is None:
            raise RuntimeError("Could not locate indices for manual trim")
        if s_idx > e_idx:
            s_idx, e_idx = e_idx, s_idx

        trimmed = self.ecg_samples[s_idx:e_idx + 1]

        info = {
            "mode": "manual_seconds",
            "relative_to_ecg_start": relative_to_ecg_start,
            "input_start_s": start_time_s,
            "input_end_s": end_time_s,
            "resolved_start_abs_s": start_abs_s,
            "resolved_end_abs_s": end_abs_s,
            "start_idx": s_idx,
            "end_idx": e_idx,
            "start_sample": trimmed[0] if trimmed else None,
            "end_sample": trimmed[-1] if trimmed else None,
        }
        return trimmed, info


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

    def save_trim_info_json(self, info, path: str) -> None:
        def make_json_safe(obj):
            if hasattr(obj, "__dict__"):
                return {k: make_json_safe(v) for k, v in obj.__dict__.items()}
            elif isinstance(obj, (list, tuple)):
                return [make_json_safe(x) for x in obj]
            elif isinstance(obj, dict):
                return {k: make_json_safe(v) for k, v in obj.items()}
            else:
                return obj 

        safe_info = make_json_safe(info)

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(safe_info, f, indent=2)

    def save_arterial_json(self, path: str) -> None:
        import json, os
        import numpy as np

        if self.arterial_velocity is None or len(self.arterial_velocity) == 0:
            raise ValueError("No arterial velocity data loaded.")

        n = int(len(self.arterial_velocity))
        vel = [float(v) for v in self.arterial_velocity]

        unix_time_s = None
        t_rel_s = None

        if (
            getattr(self, "holo_unix_first", None) is not None
            and getattr(self, "holo_unix_last", None) is not None
            and self.holo_unix_last > self.holo_unix_first
        ):
            duration_s = float(self.holo_unix_last - self.holo_unix_first) / 1_000_000.0
            t_rel = np.linspace(0.0, duration_s, n, dtype=float)
            t_rel_s = t_rel.tolist()
            unix_start_s = float(self.holo_unix_first) / 1_000_000.0
            unix_time_s = (unix_start_s + t_rel).tolist()
        else:
            # No reliable timestamps; provide sample index as a fallback
            t_rel_s = list(range(n))
            unix_time_s = None

        payload = {
            "meta": {
                "count": n,
                "units": {"velocity": "a.u.", "time": "s"},
                "has_absolute_unix_time": unix_time_s is not None,
            },
            "t_rel_s": t_rel_s,
            "unix_time_s": unix_time_s,    # may be None if unavailable
            "velocity": vel,
        }

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)

    def plot_combined(
        self,
        trimmed_samples: List[ECGSample],
        show: bool = True,
        save_dir: Optional[str] = None,
    ) -> Optional[str]:
        import os
        import matplotlib.pyplot as plt
        plt.figure(figsize=(13, 8))

        duration_sec = None
        if self.holo_unix_first is not None and self.holo_unix_last is not None:
            duration_sec = float(self.holo_unix_last - self.holo_unix_first) / 1_000_000

        ax1 = plt.subplot(3, 1, 1)
        if self.arterial_velocity is not None and len(self.arterial_velocity) > 0:
            vel_t = (
                np.linspace(0, duration_sec, len(self.arterial_velocity))
                if duration_sec and duration_sec > 0
                else np.arange(len(self.arterial_velocity), dtype=float)
            )
            ax1.plot(vel_t, self.arterial_velocity, '-', color="red")
            ax1.set_ylabel('Arterial velocity')
            ax1.set_title('Arterial Velocity (HDF5)')
        ax1.set_xlabel('Time (s)')
        ax1.grid(True, alpha=0.3)


        ecg_t = []
        ecg_v = []
        if trimmed_samples:
            ecg_t0 = trimmed_samples[0].timestamp_seconds
            ecg_t = [s.timestamp_seconds - ecg_t0 for s in trimmed_samples]
            ecg_v = [s.analog_value for s in trimmed_samples]

        ax2 = plt.subplot(3, 1, 2)
        if ecg_t:
            ax2.plot(ecg_t, ecg_v, '-', color='green')
            ax2.set_ylabel('ECG')
            ax2.set_title('Trimmed ECG')
        ax2.set_xlabel('Time (s)')
        ax2.grid(True, alpha=0.3)

        ax3 = plt.subplot(3, 1, 3)
        if self.arterial_velocity is not None and len(self.arterial_velocity) > 0:
            vel_t = (
                np.linspace(0, duration_sec, len(self.arterial_velocity))
                if duration_sec and duration_sec > 0
                else np.arange(len(self.arterial_velocity), dtype=float)
            )
            ax3.plot(vel_t, self.arterial_velocity, '-', label='Arterial velocity', color="red")
            ax3.set_ylabel('Arterial velocity')
        ax3.set_xlabel('Time (s)')
        ax3.grid(True, alpha=0.3)

        if ecg_t:
            ax3r = ax3.twinx()
            ax3r.plot(ecg_t, ecg_v, '-', label='ECG', alpha=0.9, color='green')
            ax3r.set_ylabel('ECG')

            h1, l1 = ax3.get_legend_handles_labels()
            h2, l2 = ax3r.get_legend_handles_labels()
            if h1 or h2:
                ax3.legend(h1 + h2, l1 + l2, loc='upper right')

        ax3.set_title('Arterial Velocity combined with ECG')

        plt.tight_layout()

        out_png = None
        if save_dir:
            os.makedirs(save_dir, exist_ok=True)
            out_png = os.path.join(save_dir, 'combined_plots.png')
            plt.savefig(out_png, dpi=150, bbox_inches='tight')

        if show:
            plt.show()
        else:
            plt.close()

        return out_png



def _demo_cli():
    import argparse

    p = argparse.ArgumentParser(description='Simple EKG/Holo sync demo')
    p.add_argument('--h5', required=True, help='Path to holo HDF5 file')
    p.add_argument('--ecg', required=True, help='Path to ECG CSV file')
    p.add_argument('--out', help='Path to write trimmed CSV')
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


