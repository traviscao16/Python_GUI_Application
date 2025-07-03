# Requires: pip install ttkbootstrap
import ttkbootstrap as ttkb
from tkinter import messagebox
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
root = ttkb.Window(themename="darkly")  # Try "darkly", "superhero", etc.
root.title('Python GUI App Launcher')
root.geometry('400x350')

label = ttkb.Label(root, text='Select an App to Launch:', font=('Arial', 14, 'bold'))
label.pack(pady=10)

notebook = ttkb.Notebook(root)
notebook.pack(fill='both', expand=True, padx=10, pady=10)

for group, scripts in SCRIPT_GROUPS.items():
    frame = ttkb.Frame(notebook)
    notebook.add(frame, text=group)
    for app_name, script_path in scripts.items():
        btn = ttkb.Button(frame, text=app_name, width=30,
                          command=lambda sp=script_path, an=app_name: launch_script(sp, an))
        btn.pack(pady=8)

root.mainloop()