import os
import fnmatch
import sqlite3
import pandas as pd
from tqdm import tqdm
from pandas.errors import EmptyDataError

# Configuration
csv_folder = r'C:\Users\zbrzyy\Documents\Onsemi VN\XrayDatabase\Void_results'
db_path = r'C:\Users\zbrzyy\Documents\Onsemi VN\XrayDatabase\Void_results_database.db'
standard_header = [
    'BoardBarcode', 'ModuleIndex', 'JointType', 'Pin', 'TotalVoidRatio', 
    'LargestVoidRatio', 'SpreadX', 'SpreadY', 'GVMean', 'DefectCode', 
    'SystemDefect', 'PinStatus', 'Lot', 'ModuleStatus', 'DeviceStatus'
]
batch_size = 5000
file_pattern = 'XRAY_SIC_*.csv'

def setup_database(conn):
    """Initialize database structure"""
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = OFF")
    
    conn.execute(f"""
    CREATE TABLE IF NOT EXISTS Void_results (
        {', '.join(f'{col} TEXT' for col in standard_header)},
        UNIQUE(BoardBarcode, ModuleIndex, JointType, Pin)
    )
    """)
    
    conn.execute("""
    CREATE TABLE IF NOT EXISTS processed_files (
        filename TEXT PRIMARY KEY,
        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

def process_files():
    with sqlite3.connect(db_path) as conn:
        setup_database(conn)
        processed = set(pd.read_sql("SELECT filename FROM processed_files", conn)['filename'])
        
        all_files = [f for f in os.listdir(csv_folder) 
                    if fnmatch.fnmatch(f, file_pattern) and f not in processed]
        
        with tqdm(total=len(all_files), desc="Processing files") as pbar:
            for i in range(0, len(all_files), batch_size):
                batch_files = all_files[i:i+batch_size]
                batch_data = []
                processed_files = []

                for filename in batch_files:
                    file_path = os.path.join(csv_folder, filename)
                    try:
                        # Attempt to read CSV file
                        df = pd.read_csv(file_path, low_memory=False)
                        
                        # Skip empty files
                        if df.empty:
                            print(f"Skipping empty file: {filename}")
                            continue
                            
                        # Check for required columns
                        if not set(df.columns).intersection(set(standard_header)):
                            print(f"Skipping file with no standard columns: {filename}")
                            continue

                        # Add missing columns and reorder
                        missing_cols = set(standard_header) - set(df.columns)
                        for col in missing_cols:
                            df[col] = None
                        df = df[standard_header]

                        # Clean data and add to batch
                        df = df.where(pd.notnull(df), None)
                        batch_data.extend(df.to_dict('records'))
                        processed_files.append(filename)

                    except EmptyDataError:
                        print(f"Skipping empty file: {filename}")
                    except Exception as e:
                        print(f"Error processing {filename}: {str(e)}")

                # Bulk insert valid data
                if batch_data:
                    try:
                        conn.executemany(
                            f"INSERT OR IGNORE INTO Void_results ({','.join(standard_header)}) VALUES ({','.join(['?']*len(standard_header))})",
                            [tuple(record.values()) for record in batch_data]
                        )
                        # Mark files as processed
                        if processed_files:
                            conn.executemany(
                                "INSERT OR IGNORE INTO processed_files (filename) VALUES (?)",
                                [(f,) for f in processed_files]
                            )
                        conn.commit()
                    except Exception as e:
                        conn.rollback()
                        print(f"Error inserting batch {i//batch_size}: {str(e)}")
                
                pbar.update(len(batch_files))

if __name__ == "__main__":
    process_files()
