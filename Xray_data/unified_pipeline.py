import os
import time
import sqlite3
import xml.etree.ElementTree as ET
import pandas as pd
import concurrent.futures
import logging
from tqdm import tqdm
from pandas.errors import EmptyDataError

# --- UNIFIED CONFIGURATION ---
# Source directories on the network
SOURCE_LOT_INFO_DIRS = [r'\\10.240.39.111\mips\Lot-Export', r'\\10.240.39.195\mips\Lot-Export']
SOURCE_VOID_RESULTS_DIRS = [r'\\10.240.39.111\mips\Void Result', r'\\10.240.39.195\mips\Void Result']

# Local database path
DB_PATH = r'C:\Users\zbrzyy\Documents\Onsemi VN\XrayDatabase\xray_data.db'
LOG_FILE = f'pipeline_log_{time.strftime("%Y%m%d")}.log'

# Processing parameters
BATCH_SIZE_LOTX = 100
BATCH_SIZE_CSV = 5000
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

# --- DATABASE SETUP ---
def setup_database():
    """Initializes the unified database with all necessary tables."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        
        # Table for Lot Info from .lotx files
        conn.execute("""
        CREATE TABLE IF NOT EXISTS Lot_info (
            LotId TEXT, Recipe TEXT, AllowSizeNull TEXT, CountUniqueBarcodesOnly TEXT, 
            Size INTEGER, CarrierIndex INTEGER, TrayId TEXT, TrayState INTEGER, 
            TrayCode TEXT, UnitId TEXT, UnitState INTEGER, UnitCode TEXT, UnitIdx INTEGER,
            UNIQUE(LotId, TrayId, UnitIdx)
        )""")
        
        # Table for Void Results from .csv files
        conn.execute(f"""
        CREATE TABLE IF NOT EXISTS Void_results (
            {', '.join(f'{col} TEXT' for col in CSV_STANDARD_HEADER)},
            UNIQUE(BoardBarcode, ModuleIndex, JointType, Pin)
        )""")
        
        # Unified table to track all processed files
        conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_files (
            filepath TEXT PRIMARY KEY,
            mtime REAL NOT NULL,
            size INTEGER NOT NULL,
            status TEXT NOT NULL, -- e.g., 'SUCCESS', 'ERROR'
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.commit()
    logger.info("Database setup complete.")

# --- FILE SCANNING ---
def get_files_to_process(conn, source_dirs, extension):
    """Scans source directories and identifies new or modified files."""
    files_to_process = []
    processed_files = {row[0]: (row[1], row[2]) for row in conn.execute("SELECT filepath, mtime, size FROM processed_files").fetchall()}
    
    for src_dir in source_dirs:
        if not os.path.exists(src_dir):
            logger.warning(f"Source directory not found: {src_dir}")
            continue
        
        for filename in os.listdir(src_dir):
            if filename.endswith(extension):
                file_path = os.path.join(src_dir, filename)
                try:
                    stat = os.stat(file_path)
                    mtime = stat.st_mtime
                    size = stat.st_size
                    
                    if file_path not in processed_files or processed_files[file_path] != (mtime, size):
                        files_to_process.append((file_path, mtime, size))
                except FileNotFoundError:
                    logger.warning(f"File not found during scan: {file_path}")
                    continue
    return files_to_process

# --- LOTX (.xml) PROCESSING LOGIC ---
def process_lotx_file(file_path):
    """Parses a single .lotx XML file and returns a list of records."""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        lot_attrs = {
            'lot_id': root.attrib.get('Id'), 'recipe': root.attrib.get('Recipe'),
            'allow_size_null': root.attrib.get('AllowSizeNull'),
            'count_unique_barcodes_only': root.attrib.get('CountUniqueBarcodesOnly'),
            'size': int(root.attrib.get('Size', 0)), 'carrier_index': int(root.attrib.get('CarrierIndex', 0))
        }
        
        batch = []
        trays = root.find('Trays') or []
        for tray in trays:
            tray_attrs = {'tray_id': tray.attrib.get('Id'), 'tray_state': int(tray.attrib.get('State', 0)), 'tray_code': tray.attrib.get('Code')}
            units = tray.find('Units') or []
            for unit in units:
                unit_attrs = {'unit_id': unit.attrib.get('Id'), 'unit_state': int(unit.attrib.get('State', 0)), 'unit_code': unit.attrib.get('Code'), 'unit_idx': int(unit.attrib.get('Idx', 0))}
                record = (
                    lot_attrs['lot_id'], lot_attrs['recipe'], lot_attrs['allow_size_null'], lot_attrs['count_unique_barcodes_only'],
                    lot_attrs['size'], lot_attrs['carrier_index'], tray_attrs['tray_id'], tray_attrs['tray_state'], tray_attrs['tray_code'],
                    unit_attrs['unit_id'], unit_attrs['unit_state'], unit_attrs['unit_code'], unit_attrs['unit_idx']
                )
                batch.append(record)
        return batch
    except ET.ParseError as e:
        logger.error(f"XML Parse Error in {os.path.basename(file_path)}: {e}")
        return None

# --- CSV PROCESSING LOGIC ---
def process_csv_file(file_path):
    """Parses a single .csv file and returns a pandas DataFrame."""
    try:
        df = pd.read_csv(file_path, low_memory=False)
        if df.empty:
            logger.info(f"Skipping empty file: {os.path.basename(file_path)}")
            return None
        
        missing_cols = set(CSV_STANDARD_HEADER) - set(df.columns)
        for col in missing_cols:
            df[col] = None
        df = df[CSV_STANDARD_HEADER]
        df = df.where(pd.notnull(df), None)
        return df
    except EmptyDataError:
        logger.info(f"Skipping empty file with EmptyDataError: {os.path.basename(file_path)}")
        return None
    except Exception as e:
        logger.error(f"Error processing CSV {os.path.basename(file_path)}: {e}")
        return None

# --- MAIN ORCHESTRATOR ---
def run_pipeline(files, process_func, insert_query, batch_size, desc):
    """Generic function to run a processing pipeline for a list of files."""
    all_records = []
    processed_metadata = []
    
    with tqdm(total=len(files), desc=desc) as pbar:
        for file_path, mtime, size in files:
            try:
                records = process_func(file_path)
                if records is not None and not records.empty if isinstance(records, pd.DataFrame) else records:
                    if isinstance(records, pd.DataFrame):
                        all_records.extend(records.to_records(index=False).tolist())
                    else:
                        all_records.extend(records)
                    processed_metadata.append((file_path, mtime, size, 'SUCCESS'))
                else:
                    # Mark as error if processing returns None or empty
                    processed_metadata.append((file_path, mtime, size, 'ERROR_EMPTY'))

            except Exception as e:
                logger.error(f"Failed to process {os.path.basename(file_path)}: {e}")
                processed_metadata.append((file_path, mtime, size, 'ERROR_PROCESS'))
            
            pbar.update(1)

            # Insert in batches
            if len(all_records) >= batch_size:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.executemany(insert_query, all_records)
                    conn.executemany("INSERT OR REPLACE INTO processed_files (filepath, mtime, size, status) VALUES (?, ?, ?, ?)", processed_metadata)
                    conn.commit()
                all_records.clear()
                processed_metadata.clear()

    # Insert any remaining records
    if all_records:
        with sqlite3.connect(DB_PATH) as conn:
            conn.executemany(insert_query, all_records)
            conn.executemany("INSERT OR REPLACE INTO processed_files (filepath, mtime, size, status) VALUES (?, ?, ?, ?)", processed_metadata)
            conn.commit()

def main():
    """Main function to orchestrate the entire unified pipeline."""
    start_time = time.time()
    print("Starting unified X-ray data pipeline...")
    logger.info("===== Starting Unified Pipeline =====")
    
    setup_database()
    
    with sqlite3.connect(DB_PATH) as conn:
        lotx_files = get_files_to_process(conn, SOURCE_LOT_INFO_DIRS, '.lotx')
        csv_files = get_files_to_process(conn, SOURCE_VOID_RESULTS_DIRS, '.csv')

    print(f"Found {len(lotx_files)} new/modified .lotx files.")
    print(f"Found {len(csv_files)} new/modified .csv files.")

    lot_info_query = f"INSERT OR IGNORE INTO Lot_info VALUES ({','.join(['?']*13)})"
    void_results_query = f"INSERT OR IGNORE INTO Void_results VALUES ({','.join(['?']*len(CSV_STANDARD_HEADER))})"

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_lotx = executor.submit(run_pipeline, lotx_files, process_lotx_file, lot_info_query, BATCH_SIZE_LOTX, "Processing LOTX")
        future_csv = executor.submit(run_pipeline, csv_files, process_csv_file, void_results_query, BATCH_SIZE_CSV, "Processing CSV")
        
        # Wait for both pipelines to complete
        concurrent.futures.wait([future_lotx, future_csv])

        # Check for exceptions
        if future_lotx.exception():
            logger.error(f"LOTX pipeline failed: {future_lotx.exception()}")
        if future_csv.exception():
            logger.error(f"CSV pipeline failed: {future_csv.exception()}")

    duration = time.time() - start_time
    print(f"\nPipeline finished in {duration:.2f} seconds.")
    logger.info(f"===== Pipeline finished in {duration:.2f} seconds =====\n")

if __name__ == "__main__":
    main()
