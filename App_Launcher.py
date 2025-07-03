import tkinter as tk
from tkinter import messagebox
import subprocess
import sys
import os

# Paths to your scripts
SCRIPTS = {
    'LF History': 'LF_history.py',
    'Reflow Reject Tracking': 'Reflow_Reject_tracking_GUI_1.2.py',
    'Void Data from DB': 'Void_data_fromDB.py',
}

# Function to launch a script
def launch_script(script_name):
    script_path = SCRIPTS[script_name]
    if not os.path.exists(script_path):
        messagebox.showerror('Error', f'Script not found: {script_path}')
        return
    try:
        # Use sys.executable to ensure the same Python is used
        subprocess.Popen([sys.executable, script_path], shell=False)
    except Exception as e:
        messagebox.showerror('Error', f'Failed to launch {script_name}:\n{e}')

# GUI setup
root = tk.Tk()
root.title('Python GUI App Launcher')
root.geometry('400x250')

label = tk.Label(root, text='Select an App to Launch:', font=('Arial', 14))
label.pack(pady=20)

for app_name in SCRIPTS:
    btn = tk.Button(root, text=app_name, font=('Arial', 12), width=30,
                   command=lambda name=app_name: launch_script(name))
    btn.pack(pady=10)

root.mainloop() 