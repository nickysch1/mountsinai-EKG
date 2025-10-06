import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import time
import csv
import os

from scanner import connect_to_arduino, start_ecg_scan, stop_ecg_scan


class MountSinaiEKGApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mount Sinai EKG")
        self.geometry("1050x400")
        self.configure(bg="#2e2e2e")  


        self.arduino_board = None
        self.analog_input = None
        self.ecg_data = []
        self._scan_start_time = None
        self._runtime_updating = False
        self._live_plot_updating = False
        self.scan_thread = None
        self._scan_session_id = 0  
        # If True, automatically save CSV when a scan finishes
        self.autosave_on_stop = True

        top_frame = tk.Frame(self, bg="#2e2e2e")
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        btn_style = {
            "bg": "#444444",
            "fg": "white",
            "activebackground": "#666666",
            "activeforeground": "white",
            "relief": tk.RAISED,
            "bd": 2,
        }

        connect_frame = tk.Frame(top_frame, bg="#2e2e2e")
        connect_frame.pack(side=tk.LEFT, padx=(0, 10))
        self.connect_btn = tk.Button(
            connect_frame, text="Connect Arduino", command=self.connect_arduino, **btn_style
        )
        self.connect_btn.pack(side=tk.TOP, anchor="w")
        # COM port entry
        self.com_port_var = tk.StringVar(value="AUTO")
        com_label = tk.Label(connect_frame, text="Port:", bg="#2e2e2e", fg="white")
        com_label.pack(side=tk.TOP, anchor="w", pady=(6, 0))
        com_entry = tk.Entry(connect_frame, textvariable=self.com_port_var, width=10)
        com_entry.pack(side=tk.TOP, anchor="w")
        self.arduino_status = tk.Label(
            connect_frame,
            text="Arduino: Not connected",
            bg="#2e2e2e",
            fg="orange",
            anchor="w",
            justify="left",
        )
        self.arduino_status.pack(side=tk.TOP, anchor="w", pady=(2, 0))

        self.runtime_var = tk.StringVar(value="Runtime: 0.0 s")
        self.runtime_label = tk.Label(self, textvariable=self.runtime_var, bg="#2e2e2e", fg="white")
        self.runtime_label.pack(side=tk.TOP, anchor="w", padx=10)

        self.hz_var = tk.StringVar(value="200")
        self.hz_label = tk.Label(top_frame, text="Hz:", bg="#2e2e2e", fg="white")
        self.hz_label.pack(side=tk.LEFT, padx=(10, 0))
        self.hz_entry = tk.Entry(top_frame, textvariable=self.hz_var, width=6)
        self.hz_entry.pack(side=tk.LEFT, padx=(0, 10))

        self.start_btn = tk.Button(top_frame, text="Start Scan", command=self.start_scan, **btn_style)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.stop_btn = tk.Button(top_frame, text="Stop Scan", command=self.stop_scan, **btn_style)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.stop_btn.config(state=tk.DISABLED)

        self.save_btn = tk.Button(top_frame, text="Save CSV", command=self.save_csv, **btn_style)
        self.save_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.filename_var = tk.StringVar(value="output.csv")
        self.filename_label = tk.Label(top_frame, text="Filename:", bg="#2e2e2e", fg="white")
        self.filename_label.pack(side=tk.LEFT, padx=(20, 0))
        self.filename_entry = tk.Entry(top_frame, textvariable=self.filename_var, width=20)
        self.filename_entry.pack(side=tk.LEFT, padx=(0, 0))

        # Autosave directory controls
        self.autosave_dir_var = tk.StringVar(value=".")
        autosave_label = tk.Label(top_frame, text="Autosave dir:", bg="#2e2e2e", fg="white")
        autosave_label.pack(side=tk.LEFT, padx=(10, 0))
        self.autosave_entry = tk.Entry(top_frame, textvariable=self.autosave_dir_var, width=24)
        self.autosave_entry.pack(side=tk.LEFT, padx=(0, 4))
        browse_btn = tk.Button(top_frame, text="Browse...", command=self._browse_autosave_dir, **btn_style)
        browse_btn.pack(side=tk.LEFT, padx=(0, 10))
        # Autosave enable checkbox
        self.autosave_enabled_var = tk.BooleanVar(value=self.autosave_on_stop)
        autosave_check = tk.Checkbutton(top_frame, text="Autosave", variable=self.autosave_enabled_var, bg="#2e2e2e", fg="white", selectcolor="#444444", activebackground="#444444")
        autosave_check.pack(side=tk.LEFT, padx=(0, 10))

        import matplotlib
        matplotlib.use("TkAgg") 
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        self.fig = Figure(figsize=(6, 2.5), dpi=100, facecolor="#2e2e2e")
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor("#222222")
        self.ax.set_title("Live ECG", color="white")
        self.ax.set_xlabel("Time (s)", color="white")
        self.ax.set_ylabel("Value", color="white")
        self.ax.tick_params(axis="x", colors="white")
        self.ax.tick_params(axis="y", colors="white")
        self.ax.set_ylim(0, 1)
        self.ax.set_yticks([i / 5 for i in range(6)])
        (self.line,) = self.ax.plot([], [], color="cyan", linewidth=1)
        self.ax.set_xlim(0, 5)
        self.fig.tight_layout()

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.canvas.draw()

    def _extract_display_value(self, row):
        v = None
        for k in ("value", "analog_value", "volts"):
            if k in row:
                try:
                    v = float(row[k])
                    break
                except Exception:
                    pass
        if v is None:
            return 0.0

        if v < 0.0:
            return 0.0
        if v <= 1.5:            
            return v
        if v <= 6.0:             
            return min(1.0, v / 5.0)
        if v <= 2048:              
            return min(1.0, v / 1023.0)
        return 1.0             
    def save_csv(self):
        if not self.ecg_data:
            messagebox.showerror("No Data", "No ECG data to save. Please run a scan first.")
            return

        initialfile = self.filename_var.get() or "output.csv"
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=initialfile,
            title="Save ECG Data as CSV",
        )
        if not file_path:
            return

        try:
            fieldnames = sorted(set().union(*(d.keys() for d in self.ecg_data)))
            with open(file_path, "w", newline="") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for row in self.ecg_data:
                    writer.writerow(row)
            messagebox.showinfo("Success", f"ECG data saved to {file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save CSV: {e}")


    def connect_arduino(self):
        port = self.com_port_var.get().strip()
        if port == "" or port.lower() == "auto":
            port = None
        board = connect_to_arduino(port=port)
        if board:
            self.arduino_board = board
            try:
                self.analog_input = self.arduino_board.get_pin("a:0:i")
                self.arduino_status.config(text="Arduino: Connected", fg="lightgreen")
            except Exception as e:
                print(f"Error creating analog pin: {e}")
                self.arduino_status.config(text="Error creating analog pin!", fg="red")
                self.arduino_board = None
                self.analog_input = None
        else:
            self.arduino_status.config(text="Arduino: Not connected", fg="red")

    def start_scan(self):
        if not self.arduino_board:
            self.arduino_status.config(text="Connect Arduino first!", fg="red")
            return

        try:
            hz = int(float(self.hz_var.get()))
            if hz <= 0:
                raise ValueError
        except ValueError:
            self.arduino_status.config(text="Invalid Hz value!", fg="red")
            return

        self.arduino_status.config(text="Scanning...", fg="orange")

        if self.scan_thread is not None and self.scan_thread.is_alive():
            try:
                stop_ecg_scan()
                self.scan_thread.join(timeout=5)
            except Exception as e:
                print(f"Error stopping previous scan thread: {e}")

      
        self._scan_session_id += 1
        current_session = self._scan_session_id

        self._live_plot_updating = False
        self.line.set_data([], [])
        self.ax.set_xlim(0, 5)
        self.canvas.draw_idle()
        self.update_idletasks()

        self.ecg_data = []

        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.save_btn.config(state=tk.DISABLED)


        self._scan_start_time = time.time()
        self._runtime_updating = True
        self._live_plot_updating = True

        self.update_runtime_counter()  
        self.update_live_plot()       


        def data_callback(new_row):
            def append_only():
                if not self._live_plot_updating or self._scan_session_id != current_session:
                    return
                self.ecg_data.append(new_row) 
            try:
                self.after(0, append_only)
            except Exception as e:
                print(f"Tkinter callback scheduling error: {e}")


        def collect():
            data = start_ecg_scan(
                self.arduino_board,
                target_hz=hz,
                analog_input=self.analog_input,
                data_callback=data_callback
            )
            
            self.after(0, lambda: self._on_scan_finished(data, current_session))

        self.scan_thread = threading.Thread(target=collect, daemon=True)
        self.scan_thread.start()

    def _on_scan_finished(self, data, session_id):
        if session_id != self._scan_session_id:
            return
        try:
            self.ecg_data = data or [] 
            elapsed = 0.0
            if self._scan_start_time:
                elapsed = time.time() - self._scan_start_time
            print(f"Scan stopped. Total samples: {len(self.ecg_data)} | Runtime: {elapsed:.2f} s")

            self.arduino_status.config(text="Scan stopped.", fg="orange")
            self._runtime_updating = False
            self._live_plot_updating = False

            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.save_btn.config(state=tk.NORMAL)

            self.update_live_plot(force=True)
            #autoscve
            try:
                if self.autosave_enabled_var.get() and self.ecg_data:
                    # schedule the autosave so it runs in the Tk mainloop
                    self.after(0, lambda: self._autosave_csv())
            except Exception as e:
                print(f"Autosave scheduling error: {e}")
        except Exception as e:
            print(f"Error in _on_scan_finished: {e}")

    def stop_scan(self):
        try:
            stop_ecg_scan()
        except Exception as e:
            print(f"Error calling stop_ecg_scan: {e}")

        self.arduino_status.config(text="Stopping scan...", fg="orange")
        self._runtime_updating = False
        self._live_plot_updating = False

        self.stop_btn.config(state=tk.DISABLED)

    def update_live_plot(self, force: bool = False):
        if not self._live_plot_updating and not force:
            return

        if self.ecg_data:
            total_samples = len(self.ecg_data)
            start_idx = max(0, total_samples - 1000)

            try:
                hz = float(self.hz_var.get())
                if hz <= 0:
                    hz = 200.0
            except Exception:
                hz = 200.0

            y = []
            x = []
            append_y = y.append
            append_x = x.append

            for i, row in enumerate(self.ecg_data[start_idx:]):
                append_y(self._extract_display_value(row))
                append_x((start_idx + i) / hz)

            self.line.set_data(x, y)

            if x:
                xmax = x[-1]
                if xmax <= 5:
                    self.ax.set_xlim(0, 5)
                else:
                    self.ax.set_xlim(xmax - 5, xmax)
            else:
                self.ax.set_xlim(0, 5)
        else:
            self.line.set_data([], [])
            self.ax.set_xlim(0, 5)

        self.canvas.draw_idle()

        if self._live_plot_updating:
            self.after(200, self.update_live_plot)

    def update_runtime_counter(self):
        if self._runtime_updating and self._scan_start_time:
            elapsed = time.time() - self._scan_start_time
            self.runtime_var.set(f"Runtime: {elapsed:.1f} s")
            self.after(50, self.update_runtime_counter)  
        else:
            if self._scan_start_time:
                elapsed = time.time() - self._scan_start_time
                self.runtime_var.set(f"Runtime: {elapsed:.1f} s")
            else:
                self.runtime_var.set("Runtime: 0.0 s")

    def _autosave_csv(self):
        try:
            if not self.ecg_data:
                return
            ts = time.strftime('%Y%m%d_%H%M%S')
            filename = f"ecg_autosave_{ts}.csv"
            autosave_dir = self.autosave_dir_var.get() or "."
            # expanduser and make absolute
            autosave_dir = os.path.abspath(os.path.expanduser(autosave_dir))
            try:
                os.makedirs(autosave_dir, exist_ok=True)
            except Exception:
                autosave_dir = os.getcwd()
            filepath = os.path.join(autosave_dir, filename)
            fieldnames = sorted(set().union(*(d.keys() for d in self.ecg_data)))
            with open(filepath, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for row in self.ecg_data:
                    writer.writerow(row)
            print(f"Autosaved ECG data to {filepath}")
        except Exception as e:
            print(f"Failed to autosave CSV: {e}")

    def _browse_autosave_dir(self):
        try:
            d = filedialog.askdirectory(title="Select autosave directory")
            if d:
                self.autosave_dir_var.set(d)
        except Exception as e:
            print(f"Error selecting autosave directory: {e}")


def main():
    app = MountSinaiEKGApp()
    app.mainloop()

if __name__ == "__main__":
    main()