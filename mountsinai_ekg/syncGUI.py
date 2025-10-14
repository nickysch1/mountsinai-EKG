from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox

from sync import EKGSync


class SyncGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title('EKG <-> Holo Sync')
        self.geometry('600x260')
        self.sync = EKGSync()
        self.configure(bg="#2e2e2e")

        self.ecg_path_var = tk.StringVar(value='')
        self.h5_display_var = tk.StringVar(value='')
        self.h5_paths: list[str] = []
        self.out_dir_var = tk.StringVar(value='')

        self.use_manual_cut_var = tk.BooleanVar(value=False)
        self.manual_start_var = tk.StringVar(value='')
        self.manual_end_var = tk.StringVar(value='')

        tk.Label(self, text='Manual Start', bg="#ffffff").grid(row=5, column=0, sticky='w', padx=8, pady=4) 
        tk.Entry(self, textvariable=self.manual_start_var, width=20).grid(row=5, column=1, sticky='w', padx=4)

        tk.Label(self, text='Manual End', bg="#ffffff").grid(row=6, column=0, sticky='w', padx=8, pady=4)
        tk.Entry(self, textvariable=self.manual_end_var, width=20).grid(row=6, column=1, sticky='w', padx=4)

        tk.Label(self, text='ECG CSV:', bg="#ffffff").grid(row=0, column=0, sticky='w', padx=8, pady=8)
        tk.Entry(self, textvariable=self.ecg_path_var, width=60).grid(row=0, column=1, padx=4)
        tk.Button(self, text='Browse...', command=self.browse_ecg, bg="#5d5d5d").grid(row=0, column=2, padx=4)

        tk.Label(self, text='Holo HDF5(s):', bg="#FFFFFF").grid(row=1, column=0, sticky='w', padx=8, pady=8)
        tk.Entry(self, textvariable=self.h5_display_var, width=60).grid(row=1, column=1, padx=4)
        tk.Button(self, text='Browse...', command=self.browse_h5_multi, bg="#5d5d5d").grid(row=1, column=2, padx=4)

        tk.Label(self, text='Output Folder:', bg="#ffffff").grid(row=2, column=0, sticky='w', padx=8, pady=8)
        tk.Entry(self, textvariable=self.out_dir_var, width=60).grid(row=2, column=1, padx=4)
        tk.Button(self, text='Browse...', command=self.browse_outdir, bg="#5d5d5d").grid(row=2, column=2, padx=4)

        tk.Checkbutton(self, text='Use manual start/end cut', variable=self.use_manual_cut_var, bg="#2e2e2e", fg="white", activebackground="#2e2e2e", activeforeground="white",selectcolor="#2e2e2e").grid(row=3, column=0, columnspan=3, sticky='w', padx=8)

        tk.Button(self, text='Process, Trim, and Plot', command=self.process_batch, bg="#5d5d5d").grid(row=3, column=1, pady=12)

        self.status_var = tk.StringVar(value='')
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
        use_manual = self.use_manual_cut_var.get()
        manual_start_txt = self.manual_start_var.get().strip()
        manual_end_txt = self.manual_end_var.get().strip()

        if not ecg_path or not os.path.exists(ecg_path):
            messagebox.showerror('Missing ECG', 'Please choose a valid ECG CSV file.')
            return
        if not self.h5_paths:
            messagebox.showerror('Missing H5', 'Please choose at least one HDF5 holo file.')
            return
        if not out_dir:
            messagebox.showerror('Missing Output Folder', 'Please choose an output folder.')
            return

        manual_start_s = manual_end_s = None
        if use_manual:
            if not manual_start_txt or not manual_end_txt:
                messagebox.showerror('Manual Cut', 'Provide BOTH Manual Start and Manual End.')
                return
            try:
                manual_start_s = self.sync._parse_time_to_seconds(manual_start_txt)
                manual_end_s   = self.sync._parse_time_to_seconds(manual_end_txt)
            except Exception as ex:
                messagebox.showerror('Manual Cut', f'Invalid time format: {ex}')
                return

        try:
            self.status_var.set('Loading ECG CSV...')
            self.update_idletasks()
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

                if use_manual:
                    trimmed, info = self.sync.trim_ecg_by_seconds(
                        manual_start_s, manual_end_s, relative_to_ecg_start=False
                    )
                else:
                    trimmed, info = self.sync.trim_ecg_to_holo()

                run_dir = os.path.join(out_dir, f'trimmed_{ecg_stem}__{h5_stem}')
                os.makedirs(run_dir, exist_ok=True)

                csv_path = os.path.join(run_dir, 'trimmed_ekg.csv')
                info_json_path = os.path.join(run_dir, 'trim_info.json')
                arterial_json_path = os.path.join(run_dir, 'arterial_flow.json')

                self.status_var.set(f'[{i}/{len(self.h5_paths)}] Saving trimmed CSV...')
                self.update_idletasks()
                self.sync.save_trimmed_csv(trimmed, csv_path)

                self.status_var.set(f'[{i}/{len(self.h5_paths)}] Saving trim info JSON...')
                self.update_idletasks()
                self.sync.save_trim_info_json(info, info_json_path)

                self.status_var.set(f'[{i}/{len(self.h5_paths)}] Saving arterial flow JSON...')
                self.update_idletasks()
                try:
                    self.sync.save_arterial_json(arterial_json_path)
                except Exception:
                    pass

                self.status_var.set(f'[{i}/{len(self.h5_paths)}] Rendering and saving plots...')
                self.update_idletasks()
                png_path = self.sync.plot_combined(trimmed, show=False, save_dir=run_dir)

                line = (
                    f"- {os.path.basename(h5_path)}\n"
                    f"    Folder: {run_dir}\n"
                    f"    CSV: {csv_path}\n"
                    f"    Trim Info: {info_json_path}\n"
                    f"    Arterial Flow: {arterial_json_path}"
                )
                if png_path:
                    line += f"\n    Plot: {png_path}"
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
