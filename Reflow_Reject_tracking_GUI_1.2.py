import requests
from requests_ntlm import HttpNtlmAuth
from bs4 import BeautifulSoup
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import re
import threading
import sqlite3

def login():
    global session, username, password
    username = username_entry.get()
    password = password_entry.get()
    if username and password:
        username = f"ONSEMI\\{username}"
        session = requests.Session()
        session.auth = HttpNtlmAuth(username, password)
    else:
        messagebox.showwarning("Login", "Username or Password cannot be empty.")

def get_data():
    login()

    if not session:
        messagebox.showerror("Error", "Please login first.")
        return

    console_output.delete("1.0", tk.END)
    input_text = lot_input_text.get("1.0", tk.END).strip()
    lot_ids = input_text.split('\n')
    global all_filtered_rows
    all_filtered_rows = []

    progress["maximum"] = len(lot_ids)

    for i, lot_id in enumerate(lot_ids, 1):
        current_status.set(f"Processing LotID: {lot_id}")
        progress["value"] = i
        root.update_idletasks()

        url = f"http://bhvnbiprd/CamstarLotTracking/Forms/ShopOrder/DetailedLotHistory?lotID={lot_id}"
        try:
            response = session.get(url, headers={"User-Agent": "Edg/137.0.0.0"}, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            console_output.insert(tk.END, f"Error fetching {lot_id}: {e}\n")
            continue

        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table', {'id': 'MainContent_gridview'})

        if table:
            headers_row = [th.get_text().strip() for th in table.find('thead').find_all('th')]
            rows = []
            for tr in table.find('tbody').find_all('tr'):
                cells = tr.find_all('td')
                row = {}
                for j, cell in enumerate(cells):
                    if headers_row[j] == 'Details':
                        link = cell.find('a')
                        row[headers_row[j]] = link['href'] if link else cell.get_text().strip()
                    else:
                        row[headers_row[j]] = cell.get_text().strip()
                rows.append(row)

            df = pd.DataFrame(rows)

            filtered_df = df[
                (df['Process Step'] == 'FLUX_CLEANING_AHPM4') &
                (df['Transaction'] == 'LotAddComments') &
                (df['Comments'].str.startswith('Manual updated to reject'))
            ].copy()

            filtered_df['strip ID'] = filtered_df['Comments'].apply(
                lambda x: re.search(r'F\w{9}', x, re.IGNORECASE).group().upper() if re.search(r'F\w{9}', x, re.IGNORECASE) else ''
            )

            for k in range(1, 11):
                pattern = f"(1,{k})"
                filtered_df.loc[:, f"Count_(1,{k})"] = filtered_df['Comments'].apply(lambda x: 1 if pattern in x else 0)

            if not filtered_df.empty:
                filtered_df.insert(0, 'LotID', lot_id)
                all_filtered_rows.append(filtered_df)
        else:
            console_output.insert(tk.END, f"No table found for LotID: {lot_id}\n")

    current_status.set("Data fetching complete.")
    console_output.insert(tk.END, "Data fetching complete. You can now export the data.\n")

    if all_filtered_rows:
        final_df = pd.concat(all_filtered_rows, ignore_index=True)
        console_output.insert(tk.END, "\nlocation | count\n")
        for i in range(1, 11):
            pattern_col = f"Count_(1,{i})"
            total = final_df[pattern_col].sum() if pattern_col in final_df.columns else 0
            console_output.insert(tk.END, f"{i};{total}\n")

def threaded_get_data():
    threading.Thread(target=get_data).start()

def export_data():
    if not all_filtered_rows:
        messagebox.showerror("Error", "No data to export. Please fetch data first.")
        return

    final_df = pd.concat(all_filtered_rows, ignore_index=True)
    output_file = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
    if output_file:
        final_df.to_csv(output_file, index=False)
        console_output.insert(tk.END, f"Filtered data exported to: {output_file}\n")
    else:
        console_output.insert(tk.END, "Export cancelled.\n")

def get_strip_ids():
    if not all_filtered_rows:
        messagebox.showerror("Error", "No data available. Please fetch data first.")
        return

    console_output.insert(tk.END, "\nStrip ID Summary:\n")
    final_df = pd.concat(all_filtered_rows, ignore_index=True)

    for lot_id in final_df['LotID'].unique():
        lot_df = final_df[final_df['LotID'] == lot_id]
        strip_ids = lot_df['strip ID'].unique()
        for strip_id in strip_ids:
            strip_df = lot_df[lot_df['strip ID'] == strip_id]
            locations = [str(i) for i in range(1, 11) if strip_df[f"Count_(1,{i})"].sum() > 0]
            location_str = ",".join(locations)
            console_output.insert(tk.END, f"{lot_id};{strip_id};{location_str}\n")

def check_brass_jig():
    def run_check():
        if not all_filtered_rows:
            messagebox.showerror("Error", "No data available. Please fetch data first.")
            return

        #db_path = r"C:\Users\zbrzyy\Documents\Onsemi VN\XrayDatabase\LF_Info_database.db"
        db_path = r"\\saigon\OSV\Operations\Public_folder\42. Công việc hàng ngày\2. Other data\TRINH CAO\11.Database_Storage\LF_Attach\LF_Info_database.db"
        final_df = pd.concat(all_filtered_rows, ignore_index=True)

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            strip_ids = final_df['strip ID'].tolist()
            jig_ids = []

            progress["maximum"] = len(strip_ids)

            for i, strip_id in enumerate(strip_ids, 1):
                current_status.set(f"Checking Jig for Strip ID: {strip_id}")
                progress["value"] = i
                root.update_idletasks()

                cursor.execute("SELECT JIG_ID FROM LF_Info WHERE LF_ID = ?", (strip_id,))
                result = cursor.fetchone()
                jig_ids.append(result[0] if result else "Not Found")

            final_df['JIG_ID'] = jig_ids

            all_filtered_rows.clear()
            all_filtered_rows.append(final_df)

            console_output.insert(tk.END, "\nBrass Jig Check Results:\n")
            for _, row in final_df.iterrows():
                locations = [str(i) for i in range(1, 11) if row.get(f"Count_(1,{i})", 0) > 0]
                location_str = ",".join(locations)
                console_output.insert(tk.END, f"{row['LotID']};{row['strip ID']};{row['JIG_ID']};{location_str}\n")

            conn.close()
            current_status.set("Brass Jig check complete.")
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to query database:\n{e}")

    threading.Thread(target=run_check).start()


# GUI Setup
root = tk.Tk()
root.title("Insufficient Solder on LF Fetcher - Trinh Cao")

# Login Panel
login_frame = tk.Frame(root)
login_frame.pack(pady=5)

tk.Label(login_frame, text="Username:").grid(row=0, column=0, padx=5, pady=5)
username_entry = tk.Entry(login_frame)
username_entry.grid(row=0, column=1, padx=5, pady=5)
username_entry.insert(0, "zbrzyy") # Replace with your desired default

tk.Label(login_frame, text="Password:").grid(row=0, column=2, padx=5, pady=5)
password_entry = tk.Entry(login_frame, show='*')
password_entry.grid(row=0, column=3, padx=5, pady=5)

login_button = tk.Button(login_frame, text="Login", command=login)
login_button.grid(row=0, column=4, padx=10, pady=5)

# Lot Input
tk.Label(root, text="Enter Lot IDs (one per line):").pack()
lot_input_text = scrolledtext.ScrolledText(root, width=50, height=20)
lot_input_text.pack(pady=5)

# Status Label
current_status = tk.StringVar()
tk.Label(root, textvariable=current_status, fg="blue").pack()

# Progress Bar
progress = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate")
progress.pack(pady=5)


# Action Buttons
action_frame = tk.Frame(root)
action_frame.pack(pady=10)

get_data_button = tk.Button(action_frame, text="Get Data", command=threaded_get_data)
get_data_button.grid(row=0, column=0, padx=15)

get_strip_button = tk.Button(action_frame, text="Get Strip ID", command=get_strip_ids)
get_strip_button.grid(row=0, column=2, padx=15)

export_data_button = tk.Button(action_frame, text="Export Data", command=export_data)
export_data_button.grid(row=0, column=3, padx=15)

check_jig_button = tk.Button(action_frame, text="Check Brass Jig", command=check_brass_jig)
check_jig_button.grid(row=0, column=1, padx=15)

# Console Output
console_output = scrolledtext.ScrolledText(root, width=80, height=20)
console_output.pack(pady=5)

# Initialize session and data
session = None
all_filtered_rows = []

# Start the GUI loop
root.mainloop()
