import os
import time
import sqlite3
import xml.etree.ElementTree as ET
import pandas as pd
import concurrent.futures
import logging
from datetime import datetime, timedelta
from pathlib import Path
import fnmatch
from tqdm import tqdm
import threading
import queue
from functools import lru_cache

# Configuration
CONFIG = {
    # Source paths
    'source_1': [r'\\10.240.39.111\mips\Lot-Export', r'\\10.240.39.195\mips\Lot-Export'],
    'source_2': [r'\\10.240.39.111\mips\Void Result', r'\\10.240.39.195\mips\Void Result'],
    
    # Database paths
    'lot_info_db': r'C:\Users\zbrzyy\Documents\Onsemi VN\XrayDatabase\Lot_Info_database.db',
    'void_results_db': r'C:\Users\zbrzyy\Documents\Onsemi VN\XrayDatabase\Void_results_database.db',
    'tracker_db': r'C:\Users\zbrzyy\Documents\Onsemi VN\XrayDatabase\file_tracker.db',
    
    # Processing parameters
    'max_workers': 8,
    'batch_size': 500,
    'hours_lookback': 48,  # Only process files modified in last 24 hours for first run
    'priority_hours': 24,   # Process files from last 2 hours first
    
    # CSV settings
    'csv_pattern': 'XRAY_SIC_*.csv',
    'standard_header': [
        'BoardBarcode', 'ModuleIndex', 'JointType', 'Pin', 'TotalVoidRatio',
        'LargestVoidRatio', 'SpreadX', 'SpreadY', 'GVMean', 'DefectCode',
        'SystemDefect', 'PinStatus', 'Lot', 'ModuleStatus', 'DeviceStatus'
    ]
}


# Initialize logging
os.makedirs('Logs', exist_ok=True)
logging.basicConfig(
 level=logging.INFO,
 format='%(asctime)s - %(levelname)s - %(message)s',
 handlers=[
 logging.FileHandler(os.path.join('Logs', f'unified_pipeline_{time.strftime("%Y%m%d")}.log')),
 logging.StreamHandler()
    ]
)
logger = logging.getLogger()


class DatabaseManager:
    """Centralized database operations"""
    
    def __init__(self):
        self.init_databases()
    
    def init_databases(self):
        """Initialize all required databases"""
        # File tracker database
        with sqlite3.connect(CONFIG['tracker_db']) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS file_tracker (
                file_path TEXT PRIMARY KEY,
                file_type TEXT NOT NULL,
                last_modified REAL NOT NULL,
                processed_at REAL NOT NULL,
                file_size INTEGER,
                status TEXT DEFAULT 'processed'
            )''')
            conn.commit()
        
        # Lot info database
        with sqlite3.connect(CONFIG['lot_info_db']) as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute('''CREATE TABLE IF NOT EXISTS Lot_info (
                LotId TEXT, Recipe TEXT, AllowSizeNull TEXT, CountUniqueBarcodesOnly TEXT,
                Size INTEGER, CarrierIndex INTEGER, TrayId TEXT, TrayState INTEGER,
                TrayCode TEXT, UnitId TEXT, UnitState INTEGER, UnitCode TEXT, UnitIdx INTEGER,
                UNIQUE(LotId, TrayId, UnitIdx)
            )''')
            conn.commit()
        
        # Void results database
        with sqlite3.connect(CONFIG['void_results_db']) as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            header_cols = ', '.join(f'{col} TEXT' for col in CONFIG['standard_header'])
            conn.execute(f'''CREATE TABLE IF NOT EXISTS Void_results (
                {header_cols},
                source_filename TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(BoardBarcode, ModuleIndex, JointType, Pin)
            )''')
            conn.commit()
    
    def is_file_processed(self, file_path, file_type, current_mtime):
        """Check if file needs processing"""
        with sqlite3.connect(CONFIG['tracker_db']) as conn:
            cursor = conn.execute(
                'SELECT last_modified FROM file_tracker WHERE file_path = ? AND file_type = ?',
                (file_path, file_type)
            )
            result = cursor.fetchone()
            return result and result[0] >= current_mtime
    
    def mark_file_processed(self, file_path, file_type, mtime, file_size):
        """Mark file as processed"""
        with sqlite3.connect(CONFIG['tracker_db']) as conn:
            conn.execute('''INSERT OR REPLACE INTO file_tracker
                (file_path, file_type, last_modified, processed_at, file_size)
                VALUES (?, ?, ?, ?, ?)''',
                (file_path, file_type, mtime, time.time(), file_size))
            conn.commit()

class SmartFileScanner:
    """Intelligent file scanning with priority processing"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
    
    def scan_files(self, source_dirs, file_pattern, file_type):
        """Scan files with smart prioritization"""
        now = time.time()
        priority_cutoff = now - (CONFIG['priority_hours'] * 3600)
        lookback_cutoff = now - (CONFIG['hours_lookback'] * 3600)
        
        priority_files = []
        regular_files = []
        
        for source_dir in source_dirs:
            if not os.path.exists(source_dir):
                logger.warning(f"Source directory not found: {source_dir}")
                continue
                
            logger.info(f"Scanning {source_dir} for {file_pattern}")
            
            try:
                for filename in os.listdir(source_dir):
                    if not fnmatch.fnmatch(filename, file_pattern):
                        continue
                    
                    file_path = os.path.join(source_dir, filename)
                    try:
                        stat = os.stat(file_path)
                        mtime = stat.st_mtime
                        
                        # Skip very old files on first run
                        if mtime < lookback_cutoff:
                            continue
                        
                        # Skip if already processed
                        if self.db_manager.is_file_processed(file_path, file_type, mtime):
                            continue
                        
                        file_info = {
                            'path': file_path,
                            'mtime': mtime,
                            'size': stat.st_size,
                            'type': file_type
                        }
                        
                        # Prioritize recent files
                        if mtime > priority_cutoff:
                            priority_files.append(file_info)
                        else:
                            regular_files.append(file_info)
                            
                    except OSError:
                        logger.warning(f"Cannot access file: {file_path}")
                        continue
                        
            except OSError:
                logger.error(f"Cannot access directory: {source_dir}")
                continue
        
        # Sort by modification time (newest first)
        priority_files.sort(key=lambda x: x['mtime'], reverse=True)
        regular_files.sort(key=lambda x: x['mtime'], reverse=True)
        
        return priority_files + regular_files

class StreamProcessor:
    """Process files directly from network without copying"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
    
    def process_lotx_file(self, file_info):
        """Process single LOTX file"""
        try:
            tree = ET.parse(file_info['path'])
            root = tree.getroot()
            
            # Extract lot information
            lot_attrs = {
                'lot_id': root.attrib.get('Id'),
                'recipe': root.attrib.get('Recipe'),
                'allow_size_null': root.attrib.get('AllowSizeNull'),
                'count_unique_barcodes_only': root.attrib.get('CountUniqueBarcodesOnly'),
                'size': int(root.attrib.get('Size', 0)),
                'carrier_index': int(root.attrib.get('CarrierIndex', 0))
            }
            
            records = []
            trays = root.find('Trays')
            if trays is not None:
                for tray in trays:
                    tray_attrs = {
                        'tray_id': tray.attrib.get('Id'),
                        'tray_state': int(tray.attrib.get('State', 0)),
                        'tray_code': tray.attrib.get('Code')
                    }
                    
                    units = tray.find('Units')
                    if units is not None:
                        for unit in units:
                            unit_attrs = {
                                'unit_id': unit.attrib.get('Id'),
                                'unit_state': int(unit.attrib.get('State', 0)),
                                'unit_code': unit.attrib.get('Code'),
                                'unit_idx': int(unit.attrib.get('Idx', 0))
                            }
                            
                            record = (
                                lot_attrs['lot_id'], lot_attrs['recipe'],
                                lot_attrs['allow_size_null'], lot_attrs['count_unique_barcodes_only'],
                                lot_attrs['size'], lot_attrs['carrier_index'],
                                tray_attrs['tray_id'], tray_attrs['tray_state'], tray_attrs['tray_code'],
                                unit_attrs['unit_id'], unit_attrs['unit_state'], unit_attrs['unit_code'], unit_attrs['unit_idx']
                            )
                            records.append(record)
            
            return records
            
        except Exception as e:
            logger.error(f"Error processing {file_info['path']}: {str(e)}")
            return []
    
    def process_csv_file(self, file_info):
        """Process single CSV file"""
        try:
            df = pd.read_csv(file_info['path'], low_memory=False)
            
            if df.empty:
                return []
            
            # Check for required columns
            if not set(df.columns).intersection(set(CONFIG['standard_header'])):
                logger.warning(f"No standard columns found in {file_info['path']}")
                return []
            
            # Add missing columns and reorder
            missing_cols = set(CONFIG['standard_header']) - set(df.columns)
            for col in missing_cols:
                df[col] = None
            
            df = df[CONFIG['standard_header']]
            df = df.where(pd.notnull(df), None)
            
            # Add filename to each record
            filename = os.path.basename(file_info['path'])
            records = []
            for row in df.values:
                record = tuple(row) + (filename,)
                records.append(record)
            
            return records
            
        except Exception as e:
            logger.error(f"Error processing {file_info['path']}: {str(e)}")
            return []

class UnifiedPipeline:
    """Main pipeline orchestrator"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.file_scanner = SmartFileScanner(self.db_manager)
        self.stream_processor = StreamProcessor(self.db_manager)
        self.stats = {
            'lotx_processed': 0,
            'csv_processed': 0,
            'lotx_records': 0,
            'csv_records': 0,
            'errors': 0
        }
    
    def process_lotx_batch(self, files):
        """Process batch of LOTX files"""
        all_records = []
        processed_files = []
        
        for file_info in files:
            records = self.stream_processor.process_lotx_file(file_info)
            if records:
                all_records.extend(records)
                processed_files.append(file_info)
                self.stats['lotx_records'] += len(records)
            else:
                self.stats['errors'] += 1
        
        # Bulk insert
        if all_records:
            with sqlite3.connect(CONFIG['lot_info_db']) as conn:
                conn.executemany('''INSERT OR REPLACE INTO Lot_info
                    (LotId, Recipe, AllowSizeNull, CountUniqueBarcodesOnly,
                     Size, CarrierIndex, TrayId, TrayState, TrayCode,
                     UnitId, UnitState, UnitCode, UnitIdx)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''', all_records)
                conn.commit()
        
        # Mark files as processed
        for file_info in processed_files:
            self.db_manager.mark_file_processed(
                file_info['path'], file_info['type'], file_info['mtime'], file_info['size']
            )
            self.stats['lotx_processed'] += 1
    
    def process_csv_batch(self, files):
        """Process batch of CSV files"""
        all_records = []
        processed_files = []
        
        for file_info in files:
            records = self.stream_processor.process_csv_file(file_info)
            if records:
                all_records.extend(records)
                processed_files.append(file_info)
                self.stats['csv_records'] += len(records)
            else:
                self.stats['errors'] += 1
        
        # Bulk insert
        if all_records:
            columns = CONFIG['standard_header'] + ['source_filename']
            placeholders = ','.join(['?'] * len(columns))
            with sqlite3.connect(CONFIG['void_results_db']) as conn:
                conn.executemany(
                    f"INSERT OR IGNORE INTO Void_results ({','.join(columns)}) VALUES ({placeholders})",
                    all_records
                )
                conn.commit()
        
        # Mark files as processed
        for file_info in processed_files:
            self.db_manager.mark_file_processed(
                file_info['path'], file_info['type'], file_info['mtime'], file_info['size']
            )
            self.stats['csv_processed'] += 1
    
    def run_pipeline(self):
        """Execute the complete pipeline"""
        start_time = time.time()
        logger.info("Starting unified pipeline...")
        
        # Phase 1: Process LOTX files
        logger.info("Phase 1: Processing LOTX files...")
        lotx_files = self.file_scanner.scan_files(CONFIG['source_1'], '*.lotx', 'lotx')
        
        if lotx_files:
            with tqdm(total=len(lotx_files), desc="Processing LOTX files") as pbar:
                for i in range(0, len(lotx_files), CONFIG['batch_size']):
                    batch = lotx_files[i:i+CONFIG['batch_size']]
                    try:
                        self.process_lotx_batch(batch)
                        pbar.update(len(batch))
                    except Exception as e:
                        logger.error(f"Error processing LOTX batch: {str(e)}")
                        self.stats['errors'] += len(batch)
                        pbar.update(len(batch))
        
        # Phase 2: Process CSV files
        logger.info("Phase 2: Processing CSV files...")
        csv_files = self.file_scanner.scan_files(CONFIG['source_2'], CONFIG['csv_pattern'], 'csv')
        
        if csv_files:
            with tqdm(total=len(csv_files), desc="Processing CSV files") as pbar:
                for i in range(0, len(csv_files), CONFIG['batch_size']):
                    batch = csv_files[i:i+CONFIG['batch_size']]
                    try:
                        self.process_csv_batch(batch)
                        pbar.update(len(batch))
                    except Exception as e:
                        logger.error(f"Error processing CSV batch: {str(e)}")
                        self.stats['errors'] += len(batch)
                        pbar.update(len(batch))
        
        # Report results
        duration = time.time() - start_time
        logger.info(f"Pipeline completed in {duration:.2f} seconds")
        logger.info(f"Statistics: {self.stats}")
        
        print(f"\n=== Pipeline Summary ===")
        print(f"Duration: {duration:.2f} seconds")
        print(f"LOTX files processed: {self.stats['lotx_processed']}")
        print(f"CSV files processed: {self.stats['csv_processed']}")
        print(f"LOTX records: {self.stats['lotx_records']}")
        print(f"CSV records: {self.stats['csv_records']}")
        print(f"Errors: {self.stats['errors']}")

def main():
    """Main execution function"""
    try:
        pipeline = UnifiedPipeline()
        pipeline.run_pipeline()
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}")
        raise

if __name__ == "__main__":
    main()
