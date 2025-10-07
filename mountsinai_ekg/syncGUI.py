from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox

from sync import EKGSync


class SyncGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title('EKG <-> Holo Sync')
        self.geometry('520x180')
        self.sync = EKGSync()
        self.configure(bg="#2e2e2e")

        self.ecg_path_var = tk.StringVar(value='')
        self.h5_path_var = tk.StringVar(value='')
        self.out_dir_var = tk.StringVar(value='')


        tk.Label(self, text='ECG CSV:', bg="#2e2e2e").grid(row=0, column=0, sticky='w', padx=8, pady=8)
        tk.Entry(self, textvariable=self.ecg_path_var, width=56).grid(row=0, column=1, padx=4)
        tk.Button(self, text='Browse...', command=self.browse_ecg, bg="#2e2e2e").grid(row=0, column=2, padx=4)

        tk.Label(self, text='Holo HDF5:', bg="#2e2e2e").grid(row=1, column=0, sticky='w', padx=8, pady=8)
        tk.Entry(self, textvariable=self.h5_path_var, width=56).grid(row=1, column=1, padx=4)
        tk.Button(self, text='Browse...', command=self.browse_h5, bg="#2e2e2e").grid(row=1, column=2, padx=4)

        tk.Label(self, text='Output Folder:', bg="#2e2e2e").grid(row=2, column=0, sticky='w', padx=8, pady=8)
        tk.Entry(self, textvariable=self.out_dir_var, width=56).grid(row=2, column=1, padx=4)
        tk.Button(self, text='Browse...', command=self.browse_outdir, bg="#2e2e2e").grid(row=2, column=2, padx=4)

        tk.Button(self, text='Process, Trim, and Plot', command=self.process, bg="#2e2e2e").grid(row=3, column=1, pady=12)

        self.status_var = tk.StringVar(value='Ready')
        tk.Label(self, textvariable=self.status_var, bg="#2e2e2e").grid(row=4, column=0, columnspan=3, sticky='w', padx=8)

        self.grid_columnconfigure(1, weight=1)

    def browse_ecg(self) -> None:
        path = filedialog.askopenfilename(title='Select ECG CSV', filetypes=[('CSV files', '*.csv'), ('All files', '*.*')])
        if path:
            self.ecg_path_var.set(path)
            self.status_var.set(f'Loaded ECG path: {os.path.basename(path)}')

    def browse_h5(self) -> None:
        path = filedialog.askopenfilename(title='Select HDF5 holo file', filetypes=[('HDF5 files', '*.h5;*.hdf5'), ('All files', '*.*')])
        if path:
            self.h5_path_var.set(path)
            self.status_var.set(f'Loaded H5 path: {os.path.basename(path)}')

    def browse_outdir(self) -> None:
        path = filedialog.askdirectory(title='Select output folder')
        if path:
            self.out_dir_var.set(path)
            self.status_var.set(f'Output folder: {path}')

    def process(self) -> None:
        ecg_path = self.ecg_path_var.get().strip()
        h5_path = self.h5_path_var.get().strip()
        out_dir = self.out_dir_var.get().strip()

        if not ecg_path or not os.path.exists(ecg_path):
            messagebox.showerror('Missing ECG', 'Please choose a valid ECG CSV file.')
            return
        if not h5_path or not os.path.exists(h5_path):
            messagebox.showerror('Missing H5', 'Please choose a valid HDF5 holo file.')
            return
        if not out_dir:
            messagebox.showerror('Missing Output Folder', 'Please choose an output folder.')
            return

        try:
            self.status_var.set('Loading H5...')
            self.update_idletasks()
            self.sync.load_h5(h5_path)

            self.status_var.set('Loading ECG CSV...')
            self.update_idletasks()
            self.sync.load_ecg_csv(ecg_path)

            self.status_var.set('Trimming...')
            self.update_idletasks()
            trimmed, info = self.sync.trim_ecg_to_holo()

            ecg_stem = os.path.splitext(os.path.basename(ecg_path))[0]
            os.makedirs(out_dir, exist_ok=True)
            csv_path = os.path.join(out_dir, f'trimmedEKG_{ecg_stem}.csv')
            info_json_path = os.path.join(out_dir, f'trimmed_{ecg_stem}_info.json')
            plots_dir = os.path.join(out_dir, f'trimmed_{ecg_stem}_plots')

            self.status_var.set('Saving trimmed CSV...')
            self.update_idletasks()
            self.sync.save_trimmed_csv(trimmed, csv_path)

            self.status_var.set('Saving trim info JSON...')
            self.update_idletasks()
            self.sync.save_trim_info_json(info, info_json_path)

            arterial_json_path = os.path.join(out_dir, f'arterial_{ecg_stem}.json')
            self.status_var.set('Saving arterial flow JSON...')
            self.update_idletasks()
            self.sync.save_arterial_json(arterial_json_path)


            self.status_var.set('Rendering and saving plots...')
            self.update_idletasks()
            png_path = self.sync.plot_combined(trimmed, show=True, save_dir=plots_dir)

            self.status_var.set('Done')
            msg = f"Saved:\n- CSV: {csv_path}\n- Info: {info_json_path}"
            if png_path:
                msg += f"\n- Plots: {png_path}"
            messagebox.showinfo('Success', msg)

        except Exception as e:
            messagebox.showerror('Error', f'Processing failed: {e}')
            self.status_var.set(f'Error: {e}')


def main():
    app = SyncGUI()
    app.mainloop()


if __name__ == '__main__':
    main()
