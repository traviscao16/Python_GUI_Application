import sqlite3
import pandas as pd

# Load data from CSV file
csv_file = 'input_data.csv'
data = pd.read_csv(csv_file)

# Connect to SQLite database (or create it if it doesn't exist)
conn = sqlite3.connect('lot_traceback.db')
cursor = conn.cursor()

# Create the table if it doesn't exist
cursor.execute('''
CREATE TABLE IF NOT EXISTS lot_traceback (
    Lot TEXT,
    internal2did_id TEXT,
    leadframe_id TEXT,
    leadframe_x INTEGER,
    dbc_id TEXT,
    singulation_id TEXT,
    LF_POS INTEGER
)
''')

# Insert data into the table
for _, row in data.iterrows():
    cursor.execute('''
    INSERT INTO lot_traceback (Lot, internal2did_id, leadframe_id, leadframe_x, dbc_id, singulation_id, LF_POS)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        row['Lot'],
        row['internal2did_id'],
        row['leadframe_id'],
        row['leadframe_x'],
        row['dbc_id'],
        row['singulation_id'],
        row['LF_POS']
    ))

# Commit changes and close the connection
conn.commit()
conn.close()

print("Data has been successfully inserted into the lot_traceback table.")
