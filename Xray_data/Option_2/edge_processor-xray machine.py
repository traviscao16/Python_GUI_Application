#!/usr/bin/env python3
“””
Edge Processor for X-ray Machine
Processes files immediately after creation and maintains local database
“””

import os
import time
import sqlite3
import xml.etree.ElementTree as ET
import pandas as pd
import fnmatch
import logging
import threading
from datetime import datetime
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import json
import hashlib
import gzip
from contextlib import contextmanager

# Configuration

CONFIG = {
‘watch_dirs’: [
r’C:\mips\Lot-Export’,  # Adjust paths for X-ray machine
r’C:\mips\Void Result’
],
‘db_path’: r’C:\XrayData\xray_data.db’,
‘archive_path’: r’C:\XrayData\archive’,
‘log_path’: r’C:\XrayData\logs’,
‘sync_path’: r’C:\XrayData\sync’,
‘batch_size’: 1000,
‘archive_after_days’: 7,
‘compression’: True,
‘max_log_size’: 10 * 1024 * 1024,  # 10MB
‘backup_interval’: 3600,  # 1 hour
}

# Ensure directories exist

for path in [CONFIG[‘db_path’], CONFIG[‘archive_path’], CONFIG[‘log_path’], CONFIG[‘sync_path’]]:
Path(path).parent.mkdir(parents=True, exist_ok=True)

# Setup logging

logging.basicConfig(
level=logging.INFO,
format=’%(asctime)s - %(name)s - %(levelname)s - %(message)s’,
handlers=[
logging.FileHandler(os.path.join(CONFIG[‘log_path’], ‘edge_processor.log’)),
logging.StreamHandler()
]
)
logger = logging.getLogger(**name**)

class DatabaseManager:
“”“Manages SQLite database operations with connection pooling”””

```
def __init__(self, db_path):
    self.db_path = db_path
    self.lock = threading.Lock()
    self._init_database()

def _init_database(self):
    """Initialize database schema"""
    with self.get_connection() as conn:
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = 10000")
        
        # Lot Info table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS lot_info (
            lot_id TEXT,
            recipe TEXT,
            allow_size_null TEXT,
            count_unique_barcodes_only TEXT,
            size INTEGER,
            carrier_index INTEGER,
            tray_id TEXT,
            tray_state INTEGER,
            tray_code TEXT,
            unit_id TEXT,
            unit_state INTEGER,
            unit_code TEXT,
            unit_idx INTEGER,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source_file TEXT,
            UNIQUE(lot_id, tray_id, unit_idx)
        )
        """)
        
        # Void Results table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS void_results (
            board_barcode TEXT,
            module_index TEXT,
            joint_type TEXT,
            pin TEXT,
            total_void_ratio TEXT,
            largest_void_ratio TEXT,
            spread_x TEXT,
            spread_y TEXT,
            gv_mean TEXT,
            defect_code TEXT,
            system_defect TEXT,
            pin_status TEXT,
            lot TEXT,
            module_status TEXT,
            device_status TEXT,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source_file TEXT,
            UNIQUE(board_barcode, module_index, joint_type, pin)
        )
        """)
        
        # File tracking table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_files (
            filename TEXT PRIMARY KEY,
            file_path TEXT,
            file_size INTEGER,
            file_hash TEXT,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            record_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'completed'
        )
        """)
        
        # Sync metadata table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS sync_metadata (
            last_sync TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            records_synced INTEGER DEFAULT 0,
            db_version INTEGER DEFAULT 1
        )
        """)
        
        # Create indexes for better performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_lot_info_lot_id ON lot_info(lot_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_void_results_board ON void_results(board_barcode)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_processed_files_date ON processed_files(processed_at)")
        
        conn.commit()

@contextmanager
def get_connection(self):
    """Context manager for database connections"""
    conn = sqlite3.connect(self.db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()

def is_file_processed(self, filename, file_hash):
    """Check if file has been processed"""
    with self.get_connection() as conn:
        result = conn.execute(
            "SELECT file_hash FROM processed_files WHERE filename = ?",
            (filename,)
        ).fetchone()
        return result and result[0] == file_hash

def mark_file_processed(self, filename, file_path, file_size, file_hash, record_count=0):
    """Mark file as processed"""
    with self.get_connection() as conn:
        conn.execute("""
        INSERT OR REPLACE INTO processed_files 
        (filename, file_path, file_size, file_hash, record_count, processed_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (filename, file_path, file_size, file_hash, record_count, datetime.now()))
        conn.commit()

def insert_lot_info_batch(self, records):
    """Insert batch of lot info records"""
    with self.get_connection() as conn:
        conn.executemany("""
        INSERT OR REPLACE INTO lot_info 
        (lot_id, recipe, allow_size_null, count_unique_barcodes_only,
         size, carrier_index, tray_id, tray_state, tray_code,
         unit_id, unit_state, unit_code, unit_idx, source_file)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, records)
        conn.commit()

def insert_void_results_batch(self, records):
    """Insert batch of void results records"""
    with self.get_connection() as conn:
        conn.executemany("""
        INSERT OR REPLACE INTO void_results 
        (board_barcode, module_index, joint_type, pin, total_void_ratio,
         largest_void_ratio, spread_x, spread_y, gv_mean, defect_code,
         system_defect, pin_status, lot, module_status, device_status, source_file)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, records)
        conn.commit()

def get_stats(self):
    """Get database statistics"""
    with self.get_connection() as conn:
        stats = {}
        stats['lot_info_count'] = conn.execute("SELECT COUNT(*) FROM lot_info").fetchone()[0]
        stats['void_results_count'] = conn.execute("SELECT COUNT(*) FROM void_results").fetchone()[0]
        stats['files_processed'] = conn.execute("SELECT COUNT(*) FROM processed_files").fetchone()[0]
        stats['db_size'] = os.path.getsize(self.db_path)
        return stats
```

class FileProcessor:
“”“Handles file processing logic”””

```
def __init__(self, db_manager):
    self.db_manager = db_manager
    self.standard_void_headers = [
        'BoardBarcode', 'ModuleIndex', 'JointType', 'Pin', 'TotalVoidRatio',
        'LargestVoidRatio', 'SpreadX', 'SpreadY', 'GVMean', 'DefectCode',
        'SystemDefect', 'PinStatus', 'Lot', 'ModuleStatus', 'DeviceStatus'
    ]

def calculate_file_hash(self, file_path):
    """Calculate MD5 hash of file"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def process_lotx_file(self, file_path):
    """Process .lotx (XML) file"""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        # Extract lot attributes
        lot_attrs = {
            'lot_id': root.attrib.get('Id', ''),
            'recipe': root.attrib.get('Recipe', ''),
            'allow_size_null': root.attrib.get('AllowSizeNull', ''),
            'count_unique_barcodes_only': root.attrib.get('CountUniqueBarcodesOnly', ''),
            'size': int(root.attrib.get('Size', 0)),
            'carrier_index': int(root.attrib.get('CarrierIndex', 0))
        }
        
        records = []
        trays = root.find('Trays')
        if trays is not None:
            for tray in trays:
                tray_attrs = {
                    'tray_id': tray.attrib.get('Id', ''),
                    'tray_state': int(tray.attrib.get('State', 0)),
                    'tray_code': tray.attrib.get('Code', '')
                }
                
                units = tray.find('Units')
                if units is not None:
                    for unit in units:
                        unit_attrs = {
                            'unit_id': unit.attrib.get('Id', ''),
                            'unit_state': int(unit.attrib.get('State', 0)),
                            'unit_code': unit.attrib.get('Code', ''),
                            'unit_idx': int(unit.attrib.get('Idx', 0))
                        }
                        
                        record = (
                            lot_attrs['lot_id'],
                            lot_attrs['recipe'],
                            lot_attrs['allow_size_null'],
                            lot_attrs['count_unique_barcodes_only'],
                            lot_attrs['size'],
                            lot_attrs['carrier_index'],
                            tray_attrs['tray_id'],
                            tray_attrs['tray_state'],
                            tray_attrs['tray_code'],
                            unit_attrs['unit_id'],
                            unit_attrs['unit_state'],
                            unit_attrs['unit_code'],
                            unit_attrs['unit_idx'],
                            os.path.basename(file_path)
                        )
                        records.append(record)
        
        if records:
            self.db_manager.insert_lot_info_batch(records)
            logger.info(f"Processed {len(records)} lot info records from {os.path.basename(file_path)}")
        
        return len(records)
        
    except Exception as e:
        logger.error(f"Error processing lotx file {file_path}: {str(e)}")
        return 0

def process_csv_file(self, file_path):
    """Process CSV file"""
    try:
        df = pd.read_csv(file_path, low_memory=False)
        
        if df.empty:
            logger.warning(f"Empty CSV file: {os.path.basename(file_path)}")
            return 0
        
        # Add missing columns
        for col in self.standard_void_headers:
            if col not in df.columns:
                df[col] = None
        
        # Reorder columns and clean data
        df = df[self.standard_void_headers]
        df = df.where(pd.notnull(df), None)
        
        # Convert to records and add source file
        records = []
        for _, row in df.iterrows():
            record = tuple(row.values) + (os.path.basename(file_path),)
            records.append(record)
        
        if records:
            self.db_manager.insert_void_results_batch(records)
            logger.info(f"Processed {len(records)} void results from {os.path.basename(file_path)}")
        
        return len(records)
        
    except Exception as e:
        logger.error(f"Error processing CSV file {file_path}: {str(e)}")
        return 0

def process_file(self, file_path):
    """Process a single file"""
    filename = os.path.basename(file_path)
    
    # Calculate file hash
    file_hash = self.calculate_file_hash(file_path)
    file_size = os.path.getsize(file_path)
    
    # Check if already processed
    if self.db_manager.is_file_processed(filename, file_hash):
        logger.debug(f"File already processed: {filename}")
        return
    
    # Process based on file type
    record_count = 0
    if filename.endswith('.lotx'):
        record_count = self.process_lotx_file(file_path)
    elif filename.endswith('.csv') and fnmatch.fnmatch(filename, 'XRAY_SIC_*.csv'):
        record_count = self.process_csv_file(file_path)
    else:
        logger.debug(f"Skipping unsupported file: {filename}")
        return
    
    # Mark as processed
    self.db_manager.mark_file_processed(filename, file_path, file_size, file_hash, record_count)
    
    # Archive original file if configured
    if CONFIG['compression']:
        self.archive_file(file_path)

def archive_file(self, file_path):
    """Archive and compress processed file"""
    try:
        filename = os.path.basename(file_path)
        archive_path = os.path.join(CONFIG['archive_path'], f"{filename}.gz")
        
        with open(file_path, 'rb') as f_in:
            with gzip.open(archive_path, 'wb') as f_out:
                f_out.writelines(f_in)
        
        # Remove original file after successful archival
        os.remove(file_path)
        logger.info(f"Archived and removed: {filename}")
        
    except Exception as e:
        logger.error(f"Error archiving file {file_path}: {str(e)}")
```

class FileWatcher(FileSystemEventHandler):
“”“Watches for new files and processes them”””

```
def __init__(self, processor):
    self.processor = processor
    self.processing_queue = set()
    self.queue_lock = threading.Lock()

def on_created(self, event):
    if not event.is_directory:
        self.process_file_delayed(event.src_path)

def on_modified(self, event):
    if not event.is_directory:
        self.process_file_delayed(event.src_path)

def process_file_delayed(self, file_path):
    """Process file with delay to ensure it's fully written"""
    def delayed_process():
        time.sleep(2)  # Wait for file to be fully written
        
        with self.queue_lock:
            if file_path in self.processing_queue:
                return
            self.processing_queue.add(file_path)
        
        try:
            if os.path.exists(file_path):
                self.processor.process_file(file_path)
        finally:
            with self.queue_lock:
                self.processing_queue.discard(file_path)
    
    threading.Thread(target=delayed_process).start()
```

class SyncManager:
“”“Handles database synchronization”””

```
def __init__(self, db_manager):
    self.db_manager = db_manager

def create_sync_package(self):
    """Create synchronization package"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    sync_file = os.path.join(CONFIG['sync_path'], f"sync_package_{timestamp}.db")
    
    # Copy database for sync
    import shutil
    shutil.copy2(self.db_manager.db_path, sync_file)
    
    # Create metadata
    stats = self.db_manager.get_stats()
    metadata = {
        'timestamp': timestamp,
        'stats': stats,
        'version': 1
    }
    
    metadata_file = os.path.join(CONFIG['sync_path'], f"sync_metadata_{timestamp}.json")
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    logger.info(f"Created sync package: {sync_file}")
    return sync_file, metadata_file
```

def main():
“”“Main entry point”””
logger.info(“Starting Edge Processor”)

```
# Initialize components
db_manager = DatabaseManager(CONFIG['db_path'])
processor = FileProcessor(db_manager)
sync_manager = SyncManager(db_manager)

# Process existing files
logger.info("Processing existing files...")
for watch_dir in CONFIG['watch_dirs']:
    if os.path.exists(watch_dir):
        for filename in os.listdir(watch_dir):
            file_path = os.path.join(watch_dir, filename)
            if os.path.isfile(file_path):
                processor.process_file(file_path)

# Start file watchers
observers = []
for watch_dir in CONFIG['watch_dirs']:
    if os.path.exists(watch_dir):
        observer = Observer()
        observer.schedule(FileWatcher(processor), watch_dir, recursive=False)
        observer.start()
        observers.append(observer)
        logger.info(f"Started watching: {watch_dir}")

# Periodic sync and cleanup
def periodic_tasks():
    while True:
        time.sleep(CONFIG['backup_interval'])
        try:
            sync_manager.create_sync_package()
            stats = db_manager.get_stats()
            logger.info(f"Database stats: {stats}")
        except Exception as e:
            logger.error(f"Error in periodic tasks: {str(e)}")

# Start periodic tasks
threading.Thread(target=periodic_tasks, daemon=True).start()

try:
    logger.info("Edge Processor running. Press Ctrl+C to stop.")
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    logger.info("Stopping Edge Processor...")
    for observer in observers:
        observer.stop()
        observer.join()
    logger.info("Edge Processor stopped.")
```

if **name** == “**main**”:
main()