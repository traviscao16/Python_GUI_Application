#!/usr/bin/env python3
“””
Sync Client for Laptop
Synchronizes data from X-ray machine edge processor
“””

import os
import time
import sqlite3
import json
import logging
import shutil
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
from contextlib import contextmanager
import threading
import schedule

# Configuration

CONFIG = {
‘local_db_path’: r’C:\Users\zbrzyy\Documents\Onsemi VN\XrayDatabase\unified_xray_data.db’,
‘sync_source_path’: r’\10.240.39.111\XrayData\sync’,  # Network path to X-ray machine sync folder
‘backup_path’: r’C:\Users\zbrzyy\Documents\Onsemi VN\XrayDatabase\backups’,
‘log_path’: r’C:\Users\zbrzyy\Documents\Onsemi VN\XrayDatabase\logs’,
‘sync_interval’: 300,  # 5 minutes
‘backup_retention_days’: 30,
‘max_sync_attempts’: 3,
‘sync_timeout’: 300,  # 5 minutes
}

# Ensure directories exist

for path in [CONFIG[‘local_db_path’], CONFIG[‘backup_path’], CONFIG[‘log_path’]]:
Path(path).parent.mkdir(parents=True, exist_ok=True)

# Setup logging

logging.basicConfig(
level=logging.INFO,
format=’%(asctime)s - %(name)s - %(levelname)s - %(message)s’,
handlers=[
logging.FileHandler(os.path.join(CONFIG[‘log_path’], ‘sync_client.log’)),
logging.StreamHandler()
]
)
logger = logging.getLogger(**name**)

class LocalDatabaseManager:
“”“Manages local SQLite database operations”””

```
def __init__(self, db_path):
    self.db_path = db_path
    self.lock = threading.Lock()
    self._init_database()

def _init_database(self):
    """Initialize local database schema"""
    with self.get_connection() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = 20000")
        
        # Create same schema as edge processor
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
            processed_at TIMESTAMP,
            source_file TEXT,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(lot_id, tray_id, unit_idx)
        )
        """)
        
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
            processed_at TIMESTAMP,
            source_file TEXT,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(board_barcode, module_index, joint_type, pin)
        )
        """)
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS sync_history (
            sync_id TEXT PRIMARY KEY,
            sync_timestamp TIMESTAMP,
            source_file TEXT,
            records_synced INTEGER,
            sync_duration REAL,
            status TEXT,
            error_message TEXT
        )
        """)
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS sync_metadata (
            last_sync TIMESTAMP,
            total_records INTEGER,
            last_source_timestamp TIMESTAMP,
            sync_version INTEGER DEFAULT 1
        )
        """)
        
        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_lot_info_lot_id ON lot_info(lot_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_lot_info_synced ON lot_info(synced_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_void_results_board ON void_results(board_barcode)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_void_results_synced ON void_results(synced_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sync_history_timestamp ON sync_history(sync_timestamp)")
        
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

def get_last_sync_timestamp(self):
    """Get timestamp of last successful sync"""
    with self.get_connection() as conn:
        result = conn.execute(
            "SELECT last_sync FROM sync_metadata ORDER BY last_sync DESC LIMIT 1"
        ).fetchone()
        return result[0] if result else None

def update_sync_metadata(self, source_timestamp, records_synced):
    """Update sync metadata"""
    with self.get_connection() as conn:
        conn.execute("""
        INSERT OR REPLACE INTO sync_metadata 
        (last_sync, total_records, last_source_timestamp)
        VALUES (?, ?, ?)
        """, (datetime.now(), records_synced, source_timestamp))
        conn.commit()

def sync_from_source_db(self, source_db_path, sync_id):
    """Sync data from source database"""
    start_time = time.time()
    records_synced = 0
    
    try:
        with self.get_connection() as local_conn:
            # Attach source database
            local_conn.execute(f"ATTACH DATABASE '{source_db_path}' AS source")
            
            # Sync lot_info
            local_conn.execute("""
            INSERT OR REPLACE INTO lot_info 
            SELECT *, CURRENT_TIMESTAMP as synced_at 
            FROM source.lot_info
            WHERE processed_at > COALESCE(
                (SELECT last_source_timestamp FROM sync_metadata ORDER BY last_sync DESC LIMIT 1),
                '1970-01-01'
            )
            """)
            lot_records = local_conn.execute("SELECT changes()").fetchone()[0]
            
            # Sync void_results
            local_conn.execute("""
            INSERT OR REPLACE INTO void_results 
            SELECT *, CURRENT_TIMESTAMP as synced_at 
            FROM source.void_results
            WHERE processed_at > COALESCE(
                (SELECT last_source_timestamp FROM sync_metadata ORDER BY last_sync DESC LIMIT 1),
                '1970-01-01'
            )
            """)
            void_records = local_conn.execute("SELECT changes()").fetchone()[0]
            
            records_synced = lot_records + void_records
            
            # Get source timestamp
            source_timestamp = local_conn.execute(
                "SELECT MAX(processed_at) FROM source.lot_info"
            ).fetchone()[0]
            
            # Detach source database
            local_conn.execute("DETACH DATABASE source")
            
            # Update metadata
            self.update_sync_metadata(source_timestamp, records_synced)
            
            # Log sync history
            sync_duration = time.time() - start_time
            local_conn.execute("""
            INSERT INTO sync_history 
            (sync_id, sync_timestamp, source_file, records_synced, sync_duration, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (sync_id, datetime.now(), source_db_path, records_synced, sync_duration, 'success'))
            
            local_conn.commit()
            
            logger.info(f"Sync completed: {records_synced} records in {sync_duration:.2f}s")
            return records_synced
            
    except Exception as e:
        # Log error
        with self.get_connection() as conn:
            conn.execute("""
            INSERT INTO sync_history 
            (sync_id, sync_timestamp, source_file, records_synced, sync_duration, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (sync_id, datetime.now(), source_db_path, 0, time.time() - start_time, 'error', str(e)))
            conn.commit()
        raise

def get_stats(self):
    """Get database statistics"""
    with self.get_connection() as conn:
        stats = {}
        stats['lot_info_count'] = conn.execute("SELECT COUNT(*) FROM lot_info").fetchone()[0]
        stats['void_results_count'] = conn.execute("SELECT COUNT(*) FROM void_results").fetchone()[0]
        stats['last_sync'] = conn.execute("SELECT MAX(last_sync) FROM sync_metadata").fetchone()[0]
        stats['db_size'] = os.path.getsize(self.db_path)
        
        # Recent sync history
        recent_syncs = conn.execute("""
        SELECT sync_timestamp, records_synced, status 
        FROM sync_history 
        ORDER BY sync_timestamp DESC 
        LIMIT 5
        """).fetchall()
        stats['recent_syncs'] = [dict(row) for row in recent_syncs]
        
        return stats

def cleanup_old_data(self, retention_days=30):
    """Clean up old data"""
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    
    with self.get_connection() as conn:
        # Clean up old sync history
        conn.execute(
            "DELETE FROM sync_history WHERE sync_timestamp < ?",
            (cutoff_date,)
        )
        
        # Vacuum database
        conn.execute("VACUUM")
        conn.commit()
        
        logger.info(f"Cleaned up data older than {retention_days} days")
```

class SyncClient:
“”“Main synchronization client”””

```
def __init__(self):
    self.db_manager = LocalDatabaseManager(CONFIG['local_db_path'])
    self.sync_running = False
    self.sync_lock = threading.Lock()

def find_latest_sync_package(self):
    """Find the latest sync package from X-ray machine"""
    try:
        if not os.path.exists(CONFIG['sync_source_path']):
            logger.warning(f"Sync source path not accessible: {CONFIG['sync_source_path']}")
            return None, None
        
        # Find latest sync package
        sync_files = []
```