import tkinter as tk
from tkinter import messagebox, ttk
import subprocess
import sys
import os

# Grouped scripts: {Group Name: {App Name: Script Path}}
SCRIPT_GROUPS = {
    'Leadframe Attach': {
        'LF History': 'LF_history.py',
    },
    'Reflow': {
        'Reflow Reject Tracking': 'Reflow_Reject_tracking_GUI_1.2.py',
    },
    'Xray': {
        'Void Data from DB': 'Void_data_fromDB.py',
    },
    # Add more groups here as needed:
    # 'New Group Name': {
    #     'App Name': 'script_file.py',
    # },
}

def launch_script(script_path, app_name):
    if not os.path.exists(script_path):
        messagebox.showerror('Error', f'Script not found: {script_path}')
        return
    try:
        subprocess.Popen([sys.executable, script_path], shell=False)
    except Exception as e:
        messagebox.showerror('Error', f'Failed to launch {app_name}:\n{e}')

# GUI setup
root = tk.Tk()
root.title('Python GUI App Launcher')
root.geometry('400x350')

label = tk.Label(root, text='Select an App to Launch:', font=('Arial', 14))
label.pack(pady=10)

notebook = ttk.Notebook(root)
notebook.pack(fill='both', expand=True, padx=10, pady=10)

for group, scripts in SCRIPT_GROUPS.items():
    frame = tk.Frame(notebook)
    notebook.add(frame, text=group)
    for app_name, script_path in scripts.items():
        btn = tk.Button(frame, text=app_name, font=('Arial', 12), width=30,
                        command=lambda sp=script_path, an=app_name: launch_script(sp, an))
        btn.pack(pady=8)

root.mainloop()