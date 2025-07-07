import os
import sys
import time
import sqlite3
import xml.etree.ElementTree as ET
import pandas as pd
import logging
import shutil
from pandas.errors import EmptyDataError

# --- EDGE PROCESSOR CONFIGURATION ---
# IMPORTANT: These paths are relative to the X-ray machine's local file system.
SOURCE_LOT_INFO_DIR = r'C:\path\on\xray\machine\Lot-Export'
SOURCE_VOID_RESULTS_DIR = r'C:\path\on\xray\machine\Void Result'
DB_PATH = r'C:\path\on\xray\machine\local_xray_data.db'
ARCHIVE_DIR = r'C:\path\on\xray\machine\processed_archive'
LOG_FILE = f'edge_log_{time.strftime("%Y%m%d")}.log'

# Processing parameters
CHECK_INTERVAL_SECONDS = 1800  # 30 minutes
CSV_STANDARD_HEADER = [
    'BoardBarcode', 'ModuleIndex', 'JointType', 'Pin', 'TotalVoidRatio', 
    'LargestVoidRatio', 'SpreadX', 'SpreadY', 'GVMean', 'DefectCode', 
    'SystemDefect', 'PinStatus', 'Lot', 'ModuleStatus', 'DeviceStatus'
]

# --- LOGGING SETUP ---
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

# --- DATABASE SETUP (Identical to previous script) ---
def setup_database():
    """Initializes the local database on the edge machine."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS Lot_info (
            LotId TEXT, Recipe TEXT, AllowSizeNull TEXT, CountUniqueBarcodesOnly TEXT, 
            Size INTEGER, CarrierIndex INTEGER, TrayId TEXT, TrayState INTEGER, 
            TrayCode TEXT, UnitId TEXT, UnitState INTEGER, UnitCode TEXT, UnitIdx INTEGER,
            source_filename TEXT, UNIQUE(LotId, TrayId, UnitIdx)
        )""")
        conn.execute(f"""
        CREATE TABLE IF NOT EXISTS Void_results (
            {', '.join(f'{col} TEXT' for col in CSV_STANDARD_HEADER)},
            source_filename TEXT, UNIQUE(BoardBarcode, ModuleIndex, JointType, Pin)
        )""")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_files (
            filepath TEXT PRIMARY KEY, mtime REAL NOT NULL, size INTEGER NOT NULL,
            status TEXT NOT NULL, processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.commit()
    logger.info("Local database setup complete.")

# --- FILE SCANNING (Slightly modified for single directories) ---
def get_files_to_process(conn, source_dir, extension):
    """Scans a source directory and identifies new or modified files."""
    files_to_process = []
    processed_files = {row[0]: (row[1], row[2]) for row in conn.execute("SELECT filepath, mtime, size FROM processed_files").fetchall()}
    
    if not os.path.exists(source_dir):
        logger.warning(f"Source directory not found: {source_dir}")
        return []
    
    for filename in os.listdir(source_dir):
        if filename.endswith(extension):
            file_path = os.path.join(source_dir, filename)
            try:
                stat = os.stat(file_path)
                if file_path not in processed_files or processed_files[file_path] != (stat.st_mtime, stat.st_size):
                    files_to_process.append((file_path, stat.st_mtime, stat.st_size))
            except FileNotFoundError:
                continue
    return files_to_process

# --- PARSING LOGIC (Identical to previous script) ---
def process_lotx_file(file_path):
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        lot_attrs = {'lot_id': root.attrib.get('Id'), 'recipe': root.attrib.get('Recipe'), 'size': int(root.attrib.get('Size', 0))}
        batch = []
        trays = root.find('Trays') or []
        for tray in trays:
            tray_attrs = {'tray_id': tray.attrib.get('Id'), 'tray_state': int(tray.attrib.get('State', 0))}
            units = tray.find('Units') or []
            for unit in units:
                unit_attrs = {'unit_idx': int(unit.attrib.get('Idx', 0))}
                record = (
                    lot_attrs['lot_id'], lot_attrs['recipe'], None, None, lot_attrs['size'], None,
                    tray_attrs['tray_id'], tray_attrs['tray_state'], None, None, None, None, unit_attrs['unit_idx']
                )
                batch.append(record)
        return batch
    except ET.ParseError: return None

def process_csv_file(file_path):
    try:
        df = pd.read_csv(file_path, low_memory=False)
        if df.empty: return None
        missing_cols = set(CSV_STANDARD_HEADER) - set(df.columns)
        for col in missing_cols: df[col] = None
        df = df[CSV_STANDARD_HEADER]
        return df.where(pd.notnull(df), None)
    except (EmptyDataError, Exception): return None

# --- ARCHIVING ---
def archive_file(file_path):
    """Moves a processed file to the archive directory."""
    try:
        if not os.path.exists(ARCHIVE_DIR):
            os.makedirs(ARCHIVE_DIR)
        
        archive_path = os.path.join(ARCHIVE_DIR, os.path.basename(file_path))
        shutil.move(file_path, archive_path)
        logger.info(f"Archived {os.path.basename(file_path)}")
    except Exception as e:
        logger.error(f"Failed to archive {os.path.basename(file_path)}: {e}")

# --- MAIN PROCESSING LOOP ---
def main():
    """Main function to run the edge processing loop."""
    print("Starting Edge Processor...")
    logger.info("===== Starting Edge Processor =====")
    setup_database()
    
    archive_processed_files = '--archive' in sys.argv
    if archive_processed_files:
        print("Archiving mode is ON. Processed files will be moved.")
        logger.info("Archiving mode is ON.")

    while True:
        print(f"\n[{time.ctime()}] Checking for new files...")
        
        with sqlite3.connect(DB_PATH) as conn:
            lotx_files = get_files_to_process(conn, SOURCE_LOT_INFO_DIR, '.lotx')
            csv_files = get_files_to_process(conn, SOURCE_VOID_RESULTS_DIR, '.csv')

        if not lotx_files and not csv_files:
            print("No new files found.")
        else:
            print(f"Found {len(lotx_files)} new .lotx files and {len(csv_files)} new .csv files.")
            
            # Process LOTX files
            lot_info_query = f"INSERT OR IGNORE INTO Lot_info VALUES ({','.join(['?']*14)})"
            for file_path, mtime, size in lotx_files:
                records = process_lotx_file(file_path)
                if records:
                    filename = os.path.basename(file_path)
                    records_with_filename = [r + (filename,) for r in records]
                    with sqlite3.connect(DB_PATH) as conn:
                        conn.executemany(lot_info_query, records_with_filename)
                        conn.execute("INSERT OR REPLACE INTO processed_files (filepath, mtime, size, status) VALUES (?, ?, ?, ?)", (file_path, mtime, size, 'SUCCESS'))
                        conn.commit()
                    if archive_processed_files: archive_file(file_path)

            # Process CSV files
            void_results_query = f"INSERT OR IGNORE INTO Void_results VALUES ({','.join(['?']*(len(CSV_STANDARD_HEADER)+1))})"
            for file_path, mtime, size in csv_files:
                df = process_csv_file(file_path)
                if df is not None:
                    df['source_filename'] = os.path.basename(file_path)
                    with sqlite3.connect(DB_PATH) as conn:
                        df.to_sql('Void_results', conn, if_exists='append', index=False, method='multi', chunksize=1000)
                        conn.execute("INSERT OR REPLACE INTO processed_files (filepath, mtime, size, status) VALUES (?, ?, ?, ?)", (file_path, mtime, size, 'SUCCESS'))
                        conn.commit()
                    if archive_processed_files: archive_file(file_path)
            
            print("Processing complete.")

        print(f"Sleeping for {CHECK_INTERVAL_SECONDS / 60:.0f} minutes...")
        time.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
