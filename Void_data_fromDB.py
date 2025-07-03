import pandas as pd
import sqlite3
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading

# Process data in batches
def process_batches(lot_df, void_results_conn):
    batch_size = 50
    final_df = pd.DataFrame()
    num_batches = (len(lot_df) + batch_size - 1) // batch_size
    
    progress["maximum"] = num_batches

    for batch_num in range(num_batches):
        start_idx = batch_num * batch_size
        end_idx = min((batch_num + 1) * batch_size, len(lot_df))
        batch = lot_df.iloc[start_idx:end_idx]

        container_names = batch['ContainerName'].tolist()
        query = f"""
        SELECT *
        FROM Void_results
        WHERE {" OR ".join([f"Lot LIKE '%{name}%'" for name in container_names])}
        """
        batch_result = pd.read_sql_query(query, void_results_conn)
        final_df = pd.concat([final_df, batch_result])

        # Update progress
        progress["value"] = batch_num + 1
        current_status.set(f"Processing batch {batch_num + 1}/{num_batches}")
        root.update_idletasks()

    return final_df

# Get data
def get_data():
    try:
        current_status.set("Processing...")
        console_output.delete(1.0, tk.END)

        lot_ids = lot_input_text.get(1.0, tk.END).strip().split('\n')
        lot_ids = [lot_id.strip() for lot_id in lot_ids if lot_id.strip()]
        lot_df = pd.DataFrame(lot_ids, columns=['ContainerName'])

        void_results_conn = sqlite3.connect(db_file_path.get())
        global final_df
        final_df = process_batches(lot_df, void_results_conn)
        void_results_conn.close()
        final_df.drop_duplicates(inplace=True)

        console_output.insert(tk.END, final_df.to_string())
        current_status.set("Processing completed.")
    except Exception as e:
        current_status.set("Error occurred.")
        messagebox.showerror("Error", str(e))

# Export to CSV
def export_data():
    try:
        export_file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if export_file_path:
            final_df.to_csv(export_file_path, index=False)
            messagebox.showinfo("Success", "Data exported successfully.")
    except Exception as e:
        messagebox.showerror("Error", str(e))

# Copy to clipboard
def copy_to_clipboard():
    try:
        final_df.to_clipboard(index=False)
        messagebox.showinfo("Success", "Data copied to clipboard.")
    except Exception as e:
        messagebox.showerror("Error", str(e))

# Threaded data fetch
def threaded_get_data():
    threading.Thread(target=get_data).start()

# Update Lot ID count
def update_lot_count(event=None):
    lot_ids = lot_input_text.get(1.0, tk.END).strip().split('\n')
    lot_ids = [lot_id.strip() for lot_id in lot_ids if lot_id.strip()]
    lot_count.set(f"Lot IDs Count: {len(lot_ids)}")

# GUI setup
root = tk.Tk()
root.title("Data Processing App")
root.geometry("900x700")
root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(0, weight=1)

main_frame = tk.Frame(root)
main_frame.grid(sticky="nsew")
main_frame.grid_rowconfigure(9, weight=1)
main_frame.grid_columnconfigure(0, weight=1)

main_frame.grid_rowconfigure(8, weight=1) # row 8 is the console_output


tk.Label(main_frame, text="Enter Lot IDs (one per line):").grid(row=0, column=0, padx=10, pady=5, sticky="w")
lot_input_text = scrolledtext.ScrolledText(main_frame, width=50, height=10)
lot_input_text.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
lot_input_text.bind("<KeyRelease>", update_lot_count)

tk.Label(main_frame, text="Database File Path:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
db_file_path = tk.Entry(main_frame, width=50)
db_file_path.insert(0, r"C:\Users\zbrzyy\Documents\Onsemi VN\XrayDatabase\Void_results_database.db")
db_file_path.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

lot_count = tk.StringVar()
tk.Label(main_frame, textvariable=lot_count, fg="purple").grid(row=4, column=0, padx=10, pady=5, sticky="w")

current_status = tk.StringVar()
tk.Label(main_frame, textvariable=current_status, fg="blue").grid(row=5, column=0, padx=10, pady=5, sticky="w")

progress = ttk.Progressbar(main_frame, orient="horizontal", length=400, mode="determinate")
progress.grid(row=6, column=0, padx=10, pady=5, sticky="ew")

action_frame = tk.Frame(main_frame)
action_frame.grid(row=7, column=0, padx=10, pady=10, sticky="ew")

tk.Button(action_frame, text="Get Data", command=threaded_get_data).grid(row=0, column=0, padx=15)
tk.Button(action_frame, text="Export Data", command=export_data).grid(row=0, column=1, padx=15)
tk.Button(action_frame, text="Copy to Clipboard", command=copy_to_clipboard).grid(row=0, column=2, padx=15)

console_output = scrolledtext.ScrolledText(main_frame, width=80, height=10)
console_output.grid(row=8, column=0, padx=10, pady=5, sticky="nsew")

root.mainloop()
