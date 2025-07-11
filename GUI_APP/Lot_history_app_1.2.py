import requests
from requests_ntlm import HttpNtlmAuth
from bs4 import BeautifulSoup
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import threading
import bs4
import time

# Global variables
session = None
username = ""
password = ""
result_df = pd.DataFrame()
filtered_df = pd.DataFrame()
sort_state = []
filter_entries = {}

process_steps = [
    'DBC_CUTTING_AHPM4',
    'LF_ATTACH_AHPM4',
    'CLIP_ATTACH_AHPM4',
    'VACM_RFLW_AHPM4',
    'FLUX_CLEANING_AHPM4',
    'XRAY_AHPM4',
    'WIREBOND_AL_AHPM4',
    'VISUAL_INSP_AHPM4'
]
checkbox_vars = {}

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

def get_lot_history():
    login()
    if not session:
        messagebox.showerror("Error", "Please login first.")
        return

    console_output.delete("1.0", tk.END)
    input_text = lot_input_text.get("1.0", tk.END).strip()
    lot_ids = input_text.split('\n')
    all_data = []

    progress["maximum"] = len(lot_ids)

    for i, lot_id in enumerate(lot_ids, 1):
        current_status.set(f"Processing LotID: {lot_id}")
        progress["value"] = i
        root.update_idletasks()

        url = f"http://bhvnbiprd/CamstarLotTracking/Forms/ShopOrder/DetailedLotHistory?lotID={lot_id}"
        headers = {"User-Agent": "Edg/137.0.0.0"}

        try:
            response = session.get(url, headers=headers, timeout=10)
            if response.status_code == 401:
                console_output.insert(tk.END, f"Session expired. Re-authenticating for LotID: {lot_id}...\n")
                login()
                if not session:
                    console_output.insert(tk.END, "Re-login failed.\n")
                    continue
                response = session.get(url, headers=headers, timeout=10)

            response.raise_for_status()
        except requests.RequestException as e:
            console_output.insert(tk.END, f"Error fetching {lot_id}: {e}\n")
            continue

        time.sleep(0.1)  # Delay to avoid rate-limiting

        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table', {'id': 'MainContent_gridview'})

        if isinstance(table, bs4.element.Tag):
            thead = table.find('thead')
            tbody = table.find('tbody')
            if isinstance(thead, bs4.element.Tag) and isinstance(tbody, bs4.element.Tag):
                headers_row = [th.get_text().strip() for th in thead.find_all('th') if isinstance(th, bs4.element.Tag)]
                rows = []
                for tr in tbody.find_all('tr'):
                    if not isinstance(tr, bs4.element.Tag):
                        continue
                    cells = [td for td in tr.find_all('td') if isinstance(td, bs4.element.Tag)]
                    row = {headers_row[j]: cells[j].get_text().strip() for j in range(len(cells))}
                    rows.append(row)

                df = pd.DataFrame(rows)
                df['LotID'] = lot_id
                if not isinstance(df, pd.DataFrame):
                    console_output.insert(tk.END, f"Data extraction error for LotID: {lot_id}\n")
                    continue

                filtered = df[df['Transaction'].isin(['CreateFirstInsertion', 'TrackInLot', 'TrackOutLot', 'HoldLot', 'RejectLot'])]

                if not filtered.empty:
                    pivot = filtered.pivot_table(index=['LotID', 'Process Step'], columns='Transaction', values='Txn. Date', aggfunc='first').reset_index()

                    for col in ['CreateFirstInsertion', 'TrackInLot', 'TrackOutLot', 'HoldLot']:
                        if col in pivot.columns and not pd.api.types.is_datetime64_any_dtype(pivot[col]):
                            pivot[col] = pd.to_datetime(pivot[col], format='%m/%d/%Y %I:%M:%S %p', errors='coerce')

                    if isinstance(filtered, pd.DataFrame):
                        trackin = filtered[filtered['Transaction'] == 'TrackInLot'].groupby(['LotID', 'Process Step'])['Equipment'].first().reset_index()
                        trackin = trackin.rename(columns={'Equipment': 'TrackIn_machine'})
                        trackout = filtered[filtered['Transaction'] == 'TrackOutLot'].groupby(['LotID', 'Process Step'])['Equipment'].first().reset_index()
                        trackout = trackout.rename(columns={'Equipment': 'TrackOut_machine'})
                        pivot = pivot.merge(trackin, on=['LotID', 'Process Step'], how='left')
                        pivot = pivot.merge(trackout, on=['LotID', 'Process Step'], how='left')

                    if isinstance(df, pd.DataFrame):
                        reject_data = df[df['Transaction'] == 'RejectLot'][['LotID', 'Process Step', 'From Qty', 'To Qty']]
                        if isinstance(reject_data, pd.DataFrame):
                            reject_data = reject_data.rename(columns={'From Qty': 'Reject_From_Qty', 'To Qty': 'Reject_To_Qty'})
                            pivot = pivot.merge(reject_data, on=['LotID', 'Process Step'], how='left')

                        trackout_qty = df[df['Transaction'] == 'TrackOutLot'][['LotID', 'Process Step', 'From Qty', 'To Qty']]
                        if isinstance(trackout_qty, pd.DataFrame):
                            trackout_qty = trackout_qty.rename(columns={'From Qty': 'In_Qty', 'To Qty': 'Out_Qty'})
                            pivot = pivot.merge(trackout_qty, on=['LotID', 'Process Step'], how='left')

                    in_qty = pd.to_numeric(pivot.get('In_Qty', pd.Series()), errors='coerce').fillna(0).astype(float)
                    out_qty = pd.to_numeric(pivot.get('Out_Qty', pd.Series()), errors='coerce').fillna(0).astype(float)
                    pivot['Reject_Qty'] = (in_qty - out_qty).astype(int)

                    if 'RejectLot' in pivot.columns:
                        pivot.drop(columns=['RejectLot'], inplace=True)

                    all_data.append(pivot)
                else:
                    console_output.insert(tk.END, f"No table found for LotID: {lot_id}\n")
            else:
                console_output.insert(tk.END, f"Table structure missing thead or tbody for LotID: {lot_id}\n")

    if all_data:
        final_df = pd.concat(all_data, ignore_index=True)
        global result_df, filtered_df
        result_df = final_df
        filtered_df = final_df.copy()
        update_treeview(filtered_df)
        console_output.insert(tk.END, "Data loaded successfully.\n")
    else:
        console_output.insert(tk.END, "No data retrieved.\n")



def threaded_get_lot_history():
    threading.Thread(target=get_lot_history).start()

def export_to_csv():
    if not isinstance(filtered_df, pd.DataFrame) or filtered_df.empty:
        messagebox.showerror("Error", "No data to export.")
        return
    output_file = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
    if output_file:
        filtered_df.to_csv(output_file, index=False)
        console_output.insert(tk.END, f"\nData exported to: {output_file}\n")

def update_treeview(df):
    global tree

    # Create a copy for display formatting
    display_df = df.copy()

    # Replace In_Qty and Out_Qty with Reject_From_Qty and Reject_To_Qty if present
    if 'Reject_From_Qty' in display_df.columns or 'Reject_To_Qty' in display_df.columns:
        for idx, row in display_df.iterrows():
            if 'Reject_From_Qty' in display_df.columns and pd.notnull(row.get('Reject_From_Qty')):
                display_df.at[idx, 'In_Qty'] = row['Reject_From_Qty']
            if 'Reject_To_Qty' in display_df.columns and pd.notnull(row.get('Reject_To_Qty')):
                display_df.at[idx, 'Out_Qty'] = row['Reject_To_Qty']
        # Recalculate Reject_Qty
        if not isinstance(display_df['In_Qty'], pd.Series):
            in_qty = pd.Series(display_df['In_Qty'])
        else:
            in_qty = display_df['In_Qty']
        if not isinstance(display_df['Out_Qty'], pd.Series):
            out_qty = pd.Series(display_df['Out_Qty'])
        else:
            out_qty = display_df['Out_Qty']
        in_qty = pd.to_numeric(in_qty, errors='coerce')
        if not isinstance(in_qty, pd.Series):
            in_qty = pd.Series(in_qty)
        in_qty = in_qty.fillna(0).astype(float)
        out_qty = pd.to_numeric(out_qty, errors='coerce')
        if not isinstance(out_qty, pd.Series):
            out_qty = pd.Series(out_qty)
        out_qty = out_qty.fillna(0).astype(float)
        display_df['Reject_Qty'] = (in_qty - out_qty).astype(int)
        # Drop the Reject_From_Qty and Reject_To_Qty columns for display
        display_df = display_df.drop(columns=['Reject_From_Qty', 'Reject_To_Qty','TrackOut_machine'], errors='ignore')

    # Format datetime columns for display (you can add more columns if needed)
    datetime_columns = ['CreateFirstInsertion', 'TrackInLot', 'TrackOutLot']
    for col in datetime_columns:
        if col in display_df.columns and pd.api.types.is_datetime64_any_dtype(display_df[col]):
            display_df[col] = display_df[col].dt.strftime('%d/%m/%Y %H:%M:%S')

    # Add index as the first column for display
    display_df.insert(0, 'Index', range(1, len(display_df) + 1))

    # Clear existing rows
    tree.delete(*tree.get_children())

    # Set up columns
    tree["columns"] = list(display_df.columns)
    tree["show"] = "headings"

    def sort_column(col):
        global sort_state, filtered_df
        existing = next((item for item in sort_state if item[0] == col), None)
        if existing:
            sort_state.remove(existing)
            sort_state.insert(0, (col, not existing[1]))
        else:
            sort_state.insert(0, (col, True))
        sort_by = [col for col, _ in sort_state]
        ascending = [asc for _, asc in sort_state]
        if isinstance(filtered_df, pd.DataFrame):
            filtered_df = filtered_df.sort_values(by=sort_by, ascending=ascending)
        update_treeview(filtered_df)

    # Set column headers and widths
    for col in display_df.columns:
        tree.heading(col, text=col, command=lambda _col=col: sort_column(_col))
        tree.column(col, width=120, anchor='center')

    # Insert rows
    for _, row in display_df.iterrows():
        tree.insert("", "end", values=list(row))

    # After tree is created and before button creation, define copy_selected globally

    def copy_selected(event=None):
        selected_items = tree.selection()
        if not selected_items:
            return
        headers = [tree.heading(col)["text"] for col in tree["columns"]]
        rows = ['\t'.join(headers)]
        for item in selected_items:
            row = tree.item(item)['values']
            row_str = [str(cell) if cell is not None else '' for cell in row]
            rows.append('\t'.join(row_str))
        root.clipboard_clear()
        root.clipboard_append('\n'.join(rows))

    def select_all(event=None):
        tree.selection_set(tree.get_children())
        return "break"

    # Button beside Clear View
    # (This replaces the previous lambda: copy_selected())
    tk.Button(action_frame, text="Copy Selected", command=copy_selected).grid(row=2, column=1, padx=5, pady=5)

    # Key bindings for Ctrl+C

    tree.unbind('<Control-c>')
    tree.unbind('<Control-C>')
    tree.bind('<Control-c>', copy_selected)
    tree.bind('<Control-C>', copy_selected)
    tree.bind('<Control-a>', select_all)
    tree.bind('<Control-A>', select_all)

def apply_filters():
    global filtered_df
    df = result_df.copy()
    selected_steps = [step for step, var in checkbox_vars.items() if var.get()]
    if selected_steps:
        df = df[df['Process Step'].isin(selected_steps)]
    filtered_df = df
    update_treeview(filtered_df)

def search_table():
    global filtered_df
    query = search_entry.get().lower()
    df = result_df.copy()
    if query:
        df = df[df.apply(lambda row: row.astype(str).str.lower().str.contains(query).any(), axis=1)]
    for col, entry in filter_entries.items():
        val = entry.get().strip().lower()
        if val:
            col_series = df[col] if isinstance(df[col], pd.Series) else pd.Series(df[col])
            if not isinstance(col_series, pd.Series):
                col_series = pd.Series(col_series)
            df = df[col_series.astype(str).str.lower().str.contains(val)]
    filtered_df = df
    update_treeview(filtered_df)

def check_current_process():
    global filtered_df
    if result_df.empty:
        messagebox.showwarning("Warning", "No data available. Please load lot history first.")
        return

    df = result_df.copy()

    if 'CreateFirstInsertion' not in df.columns:
        messagebox.showerror("Error", "'CreateFirstInsertion' column not found.")
        return

    # Parse datetime with known format
    df['CreateFirstInsertion'] = pd.to_datetime(
        df['CreateFirstInsertion'],
        format='%m/%d/%Y %I:%M:%S %p',
        errors='coerce'
    )

    # Drop rows with invalid dates
    df = df.dropna(subset=['CreateFirstInsertion'])

    # Sort descending to get the latest, then group and take the first
    latest_df = df.sort_values('CreateFirstInsertion', ascending=False).groupby('LotID', as_index=False).head(1)

    filtered_df = latest_df

    # Just call update_treeview with filtered_df — it will format for display
    update_treeview(filtered_df)

def clear_view():
    global filtered_df
    filtered_df = result_df.copy()
    update_treeview(filtered_df)

# GUI Setup
root = tk.Tk()
root.title("Lot History")
root.state('zoomed')  # Open the app in full screen (Windows)
#root.geometry("1200x800")
#root.attributes('-fullscreen', True)  # Alternative for true fullscreen (uncomment if needed)

main_frame = tk.Frame(root)
main_frame.pack(fill=tk.BOTH, expand=True)

left_frame = tk.Frame(main_frame, width=300)
left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
left_frame.pack_propagate(False)

right_frame = tk.Frame(main_frame)
right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

login_frame = tk.Frame(left_frame)
login_frame.pack(pady=5)
tk.Label(login_frame, text="Username:").grid(row=0, column=0, padx=5, pady=5)
username_entry = tk.Entry(login_frame, width=15)
username_entry.grid(row=0, column=1, padx=5, pady=5)
username_entry.insert(0, "zbrzyy")
tk.Label(login_frame, text="Password:").grid(row=1, column=0, padx=5, pady=5)
password_entry = tk.Entry(login_frame, show='*', width=15)
password_entry.grid(row=1, column=1, padx=5, pady=5)
tk.Button(login_frame, text="Login", command=login).grid(row=2, column=0, columnspan=2, pady=5)

tk.Label(left_frame, text="Enter Lot IDs (one per line):").pack()
lot_input_text = scrolledtext.ScrolledText(left_frame, width=35, height=10)
lot_input_text.pack(pady=5)

current_status = tk.StringVar()
tk.Label(left_frame, textvariable=current_status, fg="blue").pack()
progress = ttk.Progressbar(left_frame, orient="horizontal", length=250, mode="determinate")
progress.pack(pady=5)

action_frame = tk.Frame(left_frame)
action_frame.pack(pady=5)
tk.Button(action_frame, text="Get Lot History", command=threaded_get_lot_history).grid(row=0, column=0, padx=5)
tk.Button(action_frame, text="Export to CSV", command=export_to_csv).grid(row=0, column=1, padx=5)
tk.Button(action_frame, text="Check Current Process", command=check_current_process).grid(row=1, column=0, columnspan=2, pady=5)
tk.Button(action_frame, text="Clear View", command=clear_view).grid(row=2, column=0, padx=5, pady=5)

console_output = scrolledtext.ScrolledText(left_frame, width=35, height=10)
console_output.pack(pady=5)

search_frame = tk.Frame(left_frame)
search_frame.pack(pady=5)
tk.Label(search_frame, text="Search Table:").pack(side=tk.LEFT)
search_entry = tk.Entry(search_frame, width=20)
search_entry.pack(side=tk.LEFT, padx=5)
tk.Button(search_frame, text="Search", command=search_table).pack(side=tk.LEFT)

checkbox_frame = tk.LabelFrame(left_frame, text="Filter by Process Step")
checkbox_frame.pack(fill=tk.X, padx=5, pady=5)
for step in process_steps:
    var = tk.BooleanVar()
    cb = tk.Checkbutton(checkbox_frame, text=step, variable=var, command=apply_filters)
    cb.pack(anchor='w')
    checkbox_vars[step] = var

# Treeview with scrollbars inside a frame
tree_frame = tk.Frame(right_frame)
tree_frame.pack(fill=tk.BOTH, expand=True)

tree = ttk.Treeview(tree_frame)
tree.grid(row=0, column=0, sticky="nsew")

vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
vsb.grid(row=0, column=1, sticky="ns")
hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
hsb.grid(row=1, column=0, sticky="ew")

tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

tree_frame.rowconfigure(0, weight=1)
tree_frame.columnconfigure(0, weight=1)

root.mainloop()
# Ensure the script runs only if executed directly