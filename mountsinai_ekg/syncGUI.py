

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox

from .sync import EKGSync


class SyncGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title('EKG <-> Holo Sync')
        self.geometry('520x200')
        self.sync = EKGSync()
        self.configure(bg="#2e2e2e")
        self.ecg_path_var = tk.StringVar(value='')
        self.h5_path_var = tk.StringVar(value='')
        self.out_path_var = tk.StringVar(value='')

        btn_style = {
            "bg": "#444444",
            "fg": "white",
            "activebackground": "#666666",
            "activeforeground": "white",
            "relief": tk.RAISED,
            "bd": 2,
        }
        tk.Label(self, text='ECG CSV:', bg="#2e2e2e").grid(row=0, column=0, sticky='w', padx=8, pady=8)
        tk.Entry(self, textvariable=self.ecg_path_var, width=56).grid(row=0, column=1, padx=4)
        tk.Button(self, text='Browse...', command=self.browse_ecg, bg="#2e2e2e").grid(row=0, column=2, padx=4)

        tk.Label(self, text='Holo HDF5:', bg="#2e2e2e").grid(row=1, column=0, sticky='w', padx=8, pady=8)
        tk.Entry(self, textvariable=self.h5_path_var, width=56).grid(row=1, column=1, padx=4)
        tk.Button(self, text='Browse...', command=self.browse_h5, bg="#2e2e2e").grid(row=1, column=2, padx=4)

        tk.Label(self, text='Trimmed CSV Out:', bg="#2e2e2e").grid(row=2, column=0, sticky='w', padx=8, pady=8)
        tk.Entry(self, textvariable=self.out_path_var, width=56).grid(row=2, column=1, padx=4)
        tk.Button(self, text='Browse...', command=self.browse_out, bg="#2e2e2e").grid(row=2, column=2, padx=4)

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

    def browse_out(self) -> None:
        path = filedialog.asksaveasfilename(title='Save trimmed CSV as', defaultextension='.csv', filetypes=[('CSV files', '*.csv'), ('All files', '*.*')])
        if path:
            self.out_path_var.set(path)

    def process(self) -> None:
        ecg_path = self.ecg_path_var.get().strip()
        h5_path = self.h5_path_var.get().strip()
        out_path = self.out_path_var.get().strip()

        if not ecg_path or not os.path.exists(ecg_path):
            messagebox.showerror('Missing ECG', 'Please choose a valid ECG CSV file.')
            return
        if not h5_path or not os.path.exists(h5_path):
            messagebox.showerror('Missing H5', 'Please choose a valid HDF5 holo file.')
            return

        if not out_path:
            out_path = os.path.join(os.path.dirname(ecg_path), f'trimmed_{os.path.basename(ecg_path)}')
            self.out_path_var.set(out_path)

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

            self.status_var.set('Saving trimmed CSV...')
            self.update_idletasks()
            self.sync.save_trimmed_csv(trimmed, out_path)

            self.status_var.set('Plotting...')
            self.update_idletasks()
            self.sync.plot_combined(trimmed)

            self.status_var.set(f'Done — wrote {out_path}')
            messagebox.showinfo('Success', f'Trimmed CSV written to:\n{out_path}')
        except Exception as e:
            messagebox.showerror('Error', f'Processing failed: {e}')
            self.status_var.set(f'Error: {e}')


def main():
    app = SyncGUI()
    app.mainloop()


if __name__ == '__main__':
    main()
