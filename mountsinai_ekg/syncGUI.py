from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox

from .sync import EKGSync


class SyncGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title('EKG <-> Holo Sync')
        self.geometry('560x210')
        self.sync = EKGSync()
        self.configure(bg="#2e2e2e")

        self.ecg_path_var = tk.StringVar(value='')
        # store multiple H5 paths; mirror a short label in the entry
        self.h5_display_var = tk.StringVar(value='')
        self.h5_paths: list[str] = []
        self.out_dir_var = tk.StringVar(value='')

        # --- Rows ---
        tk.Label(self, text='ECG CSV:', bg="#2e2e2e").grid(row=0, column=0, sticky='w', padx=8, pady=8)
        tk.Entry(self, textvariable=self.ecg_path_var, width=60).grid(row=0, column=1, padx=4)
        tk.Button(self, text='Browse...', command=self.browse_ecg, bg="#2e2e2e").grid(row=0, column=2, padx=4)

        tk.Label(self, text='Holo HDF5(s):', bg="#2e2e2e").grid(row=1, column=0, sticky='w', padx=8, pady=8)
        tk.Entry(self, textvariable=self.h5_display_var, width=60).grid(row=1, column=1, padx=4)
        tk.Button(self, text='Browse...', command=self.browse_h5_multi, bg="#2e2e2e").grid(row=1, column=2, padx=4)

        tk.Label(self, text='Output Folder:', bg="#2e2e2e").grid(row=2, column=0, sticky='w', padx=8, pady=8)
        tk.Entry(self, textvariable=self.out_dir_var, width=60).grid(row=2, column=1, padx=4)
        tk.Button(self, text='Browse...', command=self.browse_outdir, bg="#2e2e2e").grid(row=2, column=2, padx=4)

        # Batch process button
        tk.Button(self, text='Process, Trim, and Plot (Batch)', command=self.process_batch, bg="#2e2e2e").grid(row=3, column=1, pady=12)

        self.status_var = tk.StringVar(value='Ready')
        tk.Label(self, textvariable=self.status_var, bg="#2e2e2e").grid(row=4, column=0, columnspan=3, sticky='w', padx=8)

        self.grid_columnconfigure(1, weight=1)

    def browse_ecg(self) -> None:
        path = filedialog.askopenfilename(title='Select ECG CSV', filetypes=[('CSV files', '*.csv'), ('All files', '*.*')])
        if path:
            self.ecg_path_var.set(path)
            self.status_var.set(f'Loaded ECG path: {os.path.basename(path)}')

    def browse_h5_multi(self) -> None:
        paths = filedialog.askopenfilenames(
            title='Select one or more HDF5 holo files',
            filetypes=[('HDF5 files', '*.h5;*.hdf5'), ('All files', '*.*')]
        )
        if paths:
            self.h5_paths = list(paths)
            if len(self.h5_paths) == 1:
                self.h5_display_var.set(os.path.basename(self.h5_paths[0]))
                self.status_var.set(f'Loaded H5 path: {os.path.basename(self.h5_paths[0])}')
            else:
                # show a compact summary in the entry
                first = os.path.basename(self.h5_paths[0])
                self.h5_display_var.set(f'{first} + {len(self.h5_paths)-1} more')
                self.status_var.set(f'Selected {len(self.h5_paths)} HDF5 files')

    def browse_outdir(self) -> None:
        path = filedialog.askdirectory(title='Select output folder')
        if path:
            self.out_dir_var.set(path)
            self.status_var.set(f'Output folder: {path}')

    def process_batch(self) -> None:
        ecg_path = self.ecg_path_var.get().strip()
        out_dir = self.out_dir_var.get().strip()

        if not ecg_path or not os.path.exists(ecg_path):
            messagebox.showerror('Missing ECG', 'Please choose a valid ECG CSV file.')
            return
        if not self.h5_paths:
            messagebox.showerror('Missing H5', 'Please choose at least one HDF5 holo file.')
            return
        if not out_dir:
            messagebox.showerror('Missing Output Folder', 'Please choose an output folder.')
            return

        try:
            self.status_var.set('Loading ECG CSV...')
            self.update_idletasks()
            # Load ECG once; reuse for all H5s
            self.sync.load_ecg_csv(ecg_path)

            ecg_stem = os.path.splitext(os.path.basename(ecg_path))[0]
            os.makedirs(out_dir, exist_ok=True)

            saved_lines = []

            for i, h5_path in enumerate(self.h5_paths, 1):
                if not os.path.exists(h5_path):
                    continue

                h5_stem = os.path.splitext(os.path.basename(h5_path))[0]
                self.status_var.set(f'[{i}/{len(self.h5_paths)}] Loading H5: {os.path.basename(h5_path)}')
                self.update_idletasks()
                self.sync.load_h5(h5_path)

                self.status_var.set(f'[{i}/{len(self.h5_paths)}] Trimming...')
                self.update_idletasks()
                trimmed, info = self.sync.trim_ecg_to_holo()

                # Add H5 stem so each output is distinct
                csv_path = os.path.join(out_dir, f'trimmedEKG_{ecg_stem}__{h5_stem}.csv')
                info_json_path = os.path.join(out_dir, f'trimmed_{ecg_stem}__{h5_stem}_info.json')
                arterial_json_path = os.path.join(out_dir, f'arterial_{ecg_stem}__{h5_stem}.json')
                plots_dir = os.path.join(out_dir, f'trimmed_{ecg_stem}__{h5_stem}_plots')

                self.status_var.set(f'[{i}/{len(self.h5_paths)}] Saving trimmed CSV...')
                self.update_idletasks()
                self.sync.save_trimmed_csv(trimmed, csv_path)

                self.status_var.set(f'[{i}/{len(self.h5_paths)}] Saving trim info JSON...')
                self.update_idletasks()
                self.sync.save_trim_info_json(info, info_json_path)

                self.status_var.set(f'[{i}/{len(self.h5_paths)}] Saving arterial flow JSON...')
                self.update_idletasks()
                # safe even if arterial not present; method raises if missing
                try:
                    self.sync.save_arterial_json(arterial_json_path)
                except Exception:
                    pass  # arterial signal may be absent; continue

                self.status_var.set(f'[{i}/{len(self.h5_paths)}] Rendering and saving plots...')
                self.update_idletasks()
                png_path = self.sync.plot_combined(trimmed, show=False, save_dir=plots_dir)

                line = f"- {os.path.basename(h5_path)}\n    CSV: {csv_path}\n    Info: {info_json_path}"
                if png_path:
                    line += f"\n    Plots: {png_path}"
                saved_lines.append(line)

            self.status_var.set('Done')
            messagebox.showinfo('Success', "Saved outputs for:\n\n" + "\n\n".join(saved_lines))

        except Exception as e:
            messagebox.showerror('Error', f'Processing failed: {e}')
            self.status_var.set(f'Error: {e}')


def main():
    app = SyncGUI()
    app.mainloop()


if __name__ == '__main__':
    main()
