#!/usr/bin/env python3
"""
Secure File Organizer - Full Tkinter GUI (Professional)
Run: python3 organizer_gui.py

This GUI calls your existing Bash scripts:
 - ./organize_files.sh <source_dir> <organized_dir>
 - ./verify_integrity.sh <organized_dir>

It streams stdout/stderr to the GUI, shows progress and logs, and lets you restore backups.

Requires: Pillow (for icon)
"""

import os
import sys
import threading
import queue
import subprocess
import time
import shutil
import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

# === CONFIG ===
# Path to icon image uploaded earlier — change if needed
ICON_PATH = "/mnt/data/2AF29F5A-0994-4BE9-91A5-B81724D7B6A2.jpeg"

# Default scripts (relative to GUI script directory)
BASE_DIR = Path.cwd()
ORGANIZE_SCRIPT = BASE_DIR / "organize_files.sh"
VERIFY_SCRIPT = BASE_DIR / "verify_integrity.sh"

# Poll interval for log viewer (ms)
LOG_POLL_MS = 2000

# ===========================
# Helper: run subprocess and stream output to a queue
# ===========================
def run_process(cmd_list, out_queue):
    """
    Runs subprocess and pushes output lines to out_queue.
    Returns process return code.
    """
    try:
        proc = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
        )
    except FileNotFoundError as e:
        out_queue.put(f"[ERROR] Script not found: {cmd_list[0]}\n{e}\n")
        return 127

    # stream output
    try:
        for line in proc.stdout:
            out_queue.put(line)
        proc.stdout.close()
        proc.wait()
        return proc.returncode
    except Exception as e:
        out_queue.put(f"[ERROR] Running command failed: {e}\n")
        return 1

# ===========================
# GUI App
# ===========================
class OrganizerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Secure File Organizer — GUI")
        # optionally set icon if pillow available and file exists
        if Image and os.path.isfile(ICON_PATH):
            try:
                img = Image.open(ICON_PATH)
                img = img.resize((64, 64))
                self.icon_img = ImageTk.PhotoImage(img)
                self.iconphoto(False, self.icon_img)
            except Exception:
                pass

        self.geometry("900x680")
        self.minsize(800, 600)

        # Notebook (tabs)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab frames
        self.tab_organize = ttk.Frame(self.notebook)
        self.tab_integrity = ttk.Frame(self.notebook)
        self.tab_backups = ttk.Frame(self.notebook)
        self.tab_logs = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_organize, text="Organizer")
        self.notebook.add(self.tab_integrity, text="Integrity")
        self.notebook.add(self.tab_backups, text="Backups")
        self.notebook.add(self.tab_logs, text="Logs")

        # Build tabs
        self.build_organizer_tab()
        self.build_integrity_tab()
        self.build_backups_tab()
        self.build_logs_tab()

        # output streaming queue and thread handle
        self.out_queue = queue.Queue()
        self.proc_thread = None

    # -------------------------
    # Organizer Tab
    # -------------------------
    def build_organizer_tab(self):
        frm = self.tab_organize

        topfrm = ttk.Frame(frm)
        topfrm.pack(fill=tk.X, padx=10, pady=10)

        # Source folder
        ttk.Label(topfrm, text="Source Folder:").grid(row=0, column=0, sticky=tk.W)
        self.src_var = tk.StringVar()
        self.src_entry = ttk.Entry(topfrm, textvariable=self.src_var, width=70)
        self.src_entry.grid(row=0, column=1, padx=6)
        ttk.Button(topfrm, text="Browse", command=self.browse_source).grid(row=0, column=2)

        # Output folder
        ttk.Label(topfrm, text="Organized Output Folder:").grid(row=1, column=0, sticky=tk.W, pady=(8,0))
        self.out_var = tk.StringVar()
        self.out_entry = ttk.Entry(topfrm, textvariable=self.out_var, width=70)
        self.out_entry.grid(row=1, column=1, padx=6, pady=(8,0))
        ttk.Button(topfrm, text="Browse", command=self.browse_output).grid(row=1, column=2, pady=(8,0))

        # Buttons
        btnfrm = ttk.Frame(frm)
        btnfrm.pack(fill=tk.X, padx=10, pady=(0,6))
        self.run_btn = ttk.Button(btnfrm, text="Run Organizer", command=self.run_organizer)
        self.run_btn.grid(row=0, column=0, padx=4)
        ttk.Button(btnfrm, text="Open Output Folder", command=self.open_output_folder).grid(row=0, column=1, padx=4)
        self.clear_btn = ttk.Button(btnfrm, text="Clear Output", command=self.clear_output_text)
        self.clear_btn.grid(row=0, column=2, padx=4)

        # Progress and status
        statusfrm = ttk.Frame(frm)
        statusfrm.pack(fill=tk.X, padx=10, pady=(6,6))
        ttk.Label(statusfrm, text="Status:").pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(statusfrm, textvariable=self.status_var).pack(side=tk.LEFT, padx=(6,0))
        self.progress = ttk.Progressbar(statusfrm, mode="indeterminate")
        self.progress.pack(fill=tk.X, padx=6, pady=6)

        # Output text area
        out_frame = ttk.Frame(frm)
        out_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)
        self.text_out = tk.Text(out_frame, wrap=tk.NONE)
        self.text_out.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # scrollbars
        ybar = ttk.Scrollbar(out_frame, orient=tk.VERTICAL, command=self.text_out.yview)
        ybar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_out.configure(yscrollcommand=ybar.set)

    # -------------------------
    # Integrity Tab
    # -------------------------
    def build_integrity_tab(self):
        frm = self.tab_integrity
        topfrm = ttk.Frame(frm)
        topfrm.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(topfrm, text="Organized Directory:").grid(row=0, column=0, sticky=tk.W)
        self.verify_dir_var = tk.StringVar()
        self.verify_entry = ttk.Entry(topfrm, textvariable=self.verify_dir_var, width=70)
        self.verify_entry.grid(row=0, column=1, padx=6)
        ttk.Button(topfrm, text="Browse", command=self.browse_verify_dir).grid(row=0, column=2)

        btnfrm = ttk.Frame(frm)
        btnfrm.pack(fill=tk.X, padx=10, pady=(0,6))
        self.verify_btn = ttk.Button(btnfrm, text="Run Integrity Check", command=self.run_integrity)
        self.verify_btn.grid(row=0, column=0, padx=4)
        ttk.Button(btnfrm, text="Open Checksum Log", command=self.open_checksum_log).grid(row=0, column=1, padx=4)

        # Progress and status
        statusfrm = ttk.Frame(frm)
        statusfrm.pack(fill=tk.X, padx=10, pady=(6,6))
        ttk.Label(statusfrm, text="Integrity Status:").pack(side=tk.LEFT)
        self.integrity_status = tk.StringVar(value="Idle")
        ttk.Label(statusfrm, textvariable=self.integrity_status).pack(side=tk.LEFT, padx=(6,0))
        self.integrity_progress = ttk.Progressbar(statusfrm, mode="indeterminate")
        self.integrity_progress.pack(fill=tk.X, padx=6, pady=6)

        # Output area
        out_frame = ttk.Frame(frm)
        out_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)
        self.text_verify = tk.Text(out_frame, wrap=tk.NONE)
        self.text_verify.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ybar = ttk.Scrollbar(out_frame, orient=tk.VERTICAL, command=self.text_verify.yview)
        ybar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_verify.configure(yscrollcommand=ybar.set)

    # -------------------------
    # Backups Tab
    # -------------------------
    def build_backups_tab(self):
        frm = self.tab_backups
        topfrm = ttk.Frame(frm)
        topfrm.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(topfrm, text="Organized Directory (for backups):").grid(row=0, column=0, sticky=tk.W)
        self.back_dir_var = tk.StringVar()
        self.back_dir_entry = ttk.Entry(topfrm, textvariable=self.back_dir_var, width=70)
        self.back_dir_entry.grid(row=0, column=1, padx=6)
        ttk.Button(topfrm, text="Browse", command=self.browse_back_dir).grid(row=0, column=2)

        btnfrm = ttk.Frame(frm)
        btnfrm.pack(fill=tk.X, padx=10, pady=(6,6))
        ttk.Button(btnfrm, text="Refresh Backups", command=self.refresh_backups).grid(row=0, column=0)
        ttk.Button(btnfrm, text="Restore Selected Backup", command=self.restore_selected_backup).grid(row=0, column=1, padx=6)

        listfrm = ttk.Frame(frm)
        listfrm.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)
        self.backups_list = tk.Listbox(listfrm)
        self.backups_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ybar = ttk.Scrollbar(listfrm, orient=tk.VERTICAL, command=self.backups_list.yview)
        ybar.pack(side=tk.RIGHT, fill=tk.Y)
        self.backups_list.configure(yscrollcommand=ybar.set)

    # -------------------------
    # Logs Tab
    # -------------------------
    def build_logs_tab(self):
        frm = self.tab_logs
        topfrm = ttk.Frame(frm)
        topfrm.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(topfrm, text="Organized Directory (for logs):").grid(row=0, column=0, sticky=tk.W)
        self.log_dir_var = tk.StringVar()
        self.log_dir_entry = ttk.Entry(topfrm, textvariable=self.log_dir_var, width=70)
        self.log_dir_entry.grid(row=0, column=1, padx=6)
        ttk.Button(topfrm, text="Browse", command=self.browse_log_dir).grid(row=0, column=2)

        btnfrm = ttk.Frame(frm)
        btnfrm.pack(fill=tk.X, padx=10, pady=(6,6))
        ttk.Button(btnfrm, text="Start Live Logs", command=self.start_live_logs).grid(row=0, column=0)
        ttk.Button(btnfrm, text="Stop Live Logs", command=self.stop_live_logs).grid(row=0, column=1, padx=6)
        ttk.Button(btnfrm, text="Clear Log View", command=self.clear_log_view).grid(row=0, column=2, padx=6)

        out_frame = ttk.Frame(frm)
        out_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)
        self.text_logs = tk.Text(out_frame, wrap=tk.NONE)
        self.text_logs.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ybar = ttk.Scrollbar(out_frame, orient=tk.VERTICAL, command=self.text_logs.yview)
        ybar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_logs.configure(yscrollcommand=ybar.set)

        self._live_logs_running = False
        self._live_log_paths = []

    # -------------------------
    # Browse helpers
    # -------------------------
    def browse_source(self):
        p = filedialog.askdirectory(title="Select Source Folder")
        if p:
            self.src_var.set(p)

    def browse_output(self):
        p = filedialog.askdirectory(title="Select Output Folder (existing) or Cancel to type new")
        if p:
            self.out_var.set(p)
        else:
            # allow user to type a new path in the entry
            pass

    def open_output_folder(self):
        path = self.out_var.get().strip()
        if not path:
            messagebox.showwarning("No Output", "Please select an output folder first.")
            return
        if sys.platform == "win32":
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path])

    def browse_verify_dir(self):
        p = filedialog.askdirectory(title="Select Organized Folder to Verify")
        if p:
            self.verify_dir_var.set(p)

    def browse_back_dir(self):
        p = filedialog.askdirectory(title="Select Organized Folder (contains backups/)")
        if p:
            self.back_dir_var.set(p)
            self.refresh_backups()

    def browse_log_dir(self):
        p = filedialog.askdirectory(title="Select Organized Folder (for logs)")
        if p:
            self.log_dir_var.set(p)

    # -------------------------
    # Run Organizer
    # -------------------------
    def run_organizer(self):
        src = self.src_var.get().strip()
        out = self.out_var.get().strip()
        if not src or not out:
            messagebox.showwarning("Missing paths", "Please select both source and output folders.")
            return
        if not os.path.isdir(src):
            messagebox.showerror("Invalid source", f"Source folder does not exist: {src}")
            return

        # If output doesn't exist, create it
        os.makedirs(out, exist_ok=True)

        # disable UI controls
        self.run_btn.config(state=tk.DISABLED)
        self.status_var.set("Running organizer...")
        self.progress.start(10)
        self.clear_output_text()

        # start thread to run script
        cmd = [str(ORGANIZE_SCRIPT), src, out]
        self.proc_thread = threading.Thread(target=self._background_run_and_stream, args=(cmd, self.text_out, self._organizer_complete))
        self.proc_thread.daemon = True
        self.proc_thread.start()

    def _organizer_complete(self, returncode):
        self.progress.stop()
        self.run_btn.config(state=tk.NORMAL)
        if returncode == 0:
            self.status_var.set("Organizer completed successfully")
            messagebox.showinfo("Done", "Organizer finished successfully.")
        else:
            self.status_var.set("Organizer finished with errors")
            messagebox.showwarning("Completed with errors", f"Organizer returned code {returncode}. Check logs.")

    # -------------------------
    # Run Integrity
    # -------------------------
    def run_integrity(self):
        d = self.verify_dir_var.get().strip()
        if not d:
            messagebox.showwarning("Missing path", "Select organized directory to verify.")
            return
        if not os.path.isdir(d):
            messagebox.showerror("Invalid directory", f"Directory does not exist: {d}")
            return

        self.verify_btn.config(state=tk.DISABLED)
        self.integrity_status.set("Running integrity check...")
        self.integrity_progress.start(10)
        self.text_verify.delete("1.0", tk.END)

        cmd = [str(VERIFY_SCRIPT), d]
        self.proc_thread = threading.Thread(target=self._background_run_and_stream, args=(cmd, self.text_verify, self._integrity_complete))
        self.proc_thread.daemon = True
        self.proc_thread.start()

    def _integrity_complete(self, returncode):
        self.integrity_progress.stop()
        self.verify_btn.config(state=tk.NORMAL)
        if returncode == 0:
            self.integrity_status.set("Integrity OK")
            messagebox.showinfo("Integrity", "All files match their checksums.")
        else:
            self.integrity_status.set("Integrity FAILED")
            messagebox.showwarning("Integrity", "Some files failed verification. Check logs.")

    # -------------------------
    # Background runner & stream
    # -------------------------
    def _background_run_and_stream(self, cmd, text_widget, on_complete_cb):
        q = queue.Queue()
        def worker():
            rc = run_process(cmd, q)
            q.put(None)  # sentinel
            q.put(("__RC__", rc))

        th = threading.Thread(target=worker, daemon=True)
        th.start()

        # periodically poll the queue and append to text_widget
        def poll():
            try:
                while True:
                    item = q.get_nowait()
                    if item is None:
                        # finished
                        pass
                    if isinstance(item, tuple) and item and item[0] == "__RC__":
                        rc = item[1]
                        on_complete_cb(rc)
                        return
                    if item is None:
                        # sentinel - ignore
                        continue
                    text_widget.insert(tk.END, item)
                    text_widget.see(tk.END)
                    q.task_done()
            except queue.Empty:
                self.after(100, poll)
        self.after(100, poll)

    # -------------------------
    # Clear output
    # -------------------------
    def clear_output_text(self):
        self.text_out.delete("1.0", tk.END)

    # -------------------------
    # Open checksum log
    # -------------------------
    def open_checksum_log(self):
        d = self.verify_dir_var.get().strip()
        if not d:
            messagebox.showwarning("Missing path", "Select organized directory first.")
            return
        chk = os.path.join(d, "organized_files_checksum.log")
        if not os.path.isfile(chk):
            messagebox.showerror("Not found", f"Checksum log not found: {chk}")
            return
        # open in default editor/viewer
        if sys.platform == "win32":
            os.startfile(chk)
        else:
            subprocess.Popen(["xdg-open", chk])

    # -------------------------
    # Backups list & restore
    # -------------------------
    def refresh_backups(self):
        d = self.back_dir_var.get().strip()
        self.backups_list.delete(0, tk.END)
        if not d:
            return
        backups_dir = os.path.join(d, "backups")
        if not os.path.isdir(backups_dir):
            return
        files = sorted(os.listdir(backups_dir), reverse=True)
        for f in files:
            if f.lower().endswith(".zip"):
                self.backups_list.insert(tk.END, f)

    def restore_selected_backup(self):
        sel = self.backups_list.curselection()
        if not sel:
            messagebox.showwarning("Select backup", "Choose a backup to restore.")
            return
        name = self.backups_list.get(sel[0])
        d = self.back_dir_var.get().strip()
        backups_dir = os.path.join(d, "backups")
        backup_path = os.path.join(backups_dir, name)
        if not os.path.isfile(backup_path):
            messagebox.showerror("Not found", backup_path)
            return

        # ask where to restore (target folder)
        dest = filedialog.askdirectory(title="Select folder to restore backup into")
        if not dest:
            return

        # confirm
        if not messagebox.askyesno("Confirm restore", f"Restore {name} into {dest}? This may overwrite files."):
            return

        try:
            with zipfile.ZipFile(backup_path, 'r') as z:
                z.extractall(dest)
            messagebox.showinfo("Restored", f"Backup restored into {dest}")
        except Exception as e:
            messagebox.showerror("Restore failed", f"Failed to restore: {e}")

    # -------------------------
    # Live logs
    # -------------------------
    def start_live_logs(self):
        d = self.log_dir_var.get().strip()
        if not d:
            messagebox.showwarning("Select directory", "Select organized directory to read logs from.")
            return
        organizer_log = os.path.join(d, "organizer.log")
        integrity_log = os.path.join(d, "integrity_check.log")
        paths = []
        if os.path.isfile(organizer_log):
            paths.append(organizer_log)
        if os.path.isfile(integrity_log):
            paths.append(integrity_log)
        if not paths:
            messagebox.showwarning("No logs", "No log files found in the selected directory.")
            return
        self._live_log_paths = paths
        self._live_logs_running = True
        self.text_logs.delete("1.0", tk.END)
        self._tail_positions = {p: 0 for p in paths}
        self._do_tail()

    def _do_tail(self):
        if not self._live_logs_running:
            return
        parts = []
        for p in self._live_log_paths:
            try:
                with open(p, 'r') as fh:
                    fh.seek(self._tail_positions.get(p, 0))
                    data = fh.read()
                    if data:
                        parts.append(f"--- {os.path.basename(p)} ---\n{data}\n")
                    self._tail_positions[p] = fh.tell()
            except Exception:
                pass
        if parts:
            self.text_logs.insert(tk.END, "\n".join(parts))
            self.text_logs.see(tk.END)
        self.after(LOG_POLL_MS, self._do_tail)

    def stop_live_logs(self):
        self._live_logs_running = False

    def clear_log_view(self):
        self.text_logs.delete("1.0", tk.END)

# ===========================
# Entry point
# ===========================
def main():
    # quick checks
    if not ORGANIZE_SCRIPT.exists():
        print(f"[ERROR] organize script not found: {ORGANIZE_SCRIPT}")
    if not VERIFY_SCRIPT.exists():
        print(f"[WARNING] verify script not found: {VERIFY_SCRIPT} (integrity check will not run)")

    app = OrganizerApp()
    app.mainloop()

if __name__ == "__main__":
    main()
