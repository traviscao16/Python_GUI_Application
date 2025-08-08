import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import sqlite3
import pandas as pd
import threading

# Function to query the database and get latest entry per LF_ID
def query_database():
    try:
        status_var.set("Querying database...")
        output_text.delete(1.0, tk.END)

        lf_ids = input_text.get(1.0, tk.END).strip().split('\n')
        lf_ids = [lf_id.strip() for lf_id in lf_ids if lf_id.strip()]

        if not lf_ids:
            messagebox.showwarning("Input Error", "Please enter at least one LF_ID.")
            return

        conn = sqlite3.connect(r"C:\Users\zbrzyy\Documents\Onsemi VN\XrayDatabase\LF_Info_database.db")
        placeholders = ','.join('?' for _ in lf_ids)
        query = f"SELECT * FROM LF_Info WHERE LF_ID IN ({placeholders})"
        df = pd.read_sql_query(query, conn, params=lf_ids)
        conn.close()

        # Convert Date to datetime for sorting
        df['Date'] = pd.to_datetime(df['Date'], format="%d/%m/%Y %I:%M:%S %p", errors='coerce')

        # Drop rows with invalid dates
        df = df.dropna(subset=['Date'])

        # Sort and get latest entry per LF_ID
        df_sorted = df.sort_values('Date', ascending=False)
        latest_df = df_sorted.groupby('LF_ID', as_index=False).first()

        # Select only required columns
        result_df = latest_df[['Date', 'Lotname', 'JIG_ID', 'LF_ID', '2D_RESULT']]

        global final_df
        final_df = result_df
        output_text.insert(tk.END, result_df.to_string(index=False))
        status_var.set("Query completed.")
    except Exception as e:
        status_var.set("Error occurred.")
        messagebox.showerror("Error", str(e))

# Threaded query execution
def threaded_query():
    threading.Thread(target=query_database).start()

# Export results to CSV
def export_to_csv():
    try:
        if final_df.empty:
            messagebox.showwarning("No Data", "No data to export.")
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if file_path:
            final_df.to_csv(file_path, index=False)
            messagebox.showinfo("Success", "Data exported successfully.")
    except Exception as e:
        messagebox.showerror("Error", str(e))

# Copy results to clipboard
def copy_to_clipboard():
    try:
        if final_df.empty:
            messagebox.showwarning("No Data", "No data to copy.")
            return
        final_df.to_clipboard(index=False)
        messagebox.showinfo("Success", "Data copied to clipboard.")
    except Exception as e:
        messagebox.showerror("Error", str(e))

# GUI setup
app = tk.Tk()
app.title("Leadframe_history")
app.geometry("800x600")

tk.Label(app, text="Enter LF_IDs (one per line):").pack(pady=5)
input_text = scrolledtext.ScrolledText(app, width=60, height=10)
input_text.pack(padx=10, pady=5)

status_var = tk.StringVar()
tk.Label(app, textvariable=status_var, fg="blue").pack(pady=5)

button_frame = tk.Frame(app)
button_frame.pack(pady=10)
tk.Button(button_frame, text="Get Data", command=threaded_query).grid(row=0, column=0, padx=10)
tk.Button(button_frame, text="Export to CSV", command=export_to_csv).grid(row=0, column=1, padx=10)
tk.Button(button_frame, text="Copy to Clipboard", command=copy_to_clipboard).grid(row=0, column=2, padx=10)

output_text = scrolledtext.ScrolledText(app, width=90, height=20)
output_text.pack(padx=10, pady=5)

final_df = pd.DataFrame()

app.mainloop()
