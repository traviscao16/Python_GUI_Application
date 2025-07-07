import os
import time
import shutil
import concurrent.futures
import sqlite3
import logging
from functools import lru_cache

# Configuration
source_1 = [r'\\10.240.39.111\mips\Lot-Export', r'\\10.240.39.195\mips\Lot-Export']
source_2 = [r'\\10.240.39.111\mips\Void Result', r'\\10.240.39.195\mips\Void Result']
dest_1 = r'C:\Users\zbrzyy\Documents\Onsemi VN\XrayDatabase\Lot_Info'
dest_2 = r'C:\Users\zbrzyy\Documents\Onsemi VN\XrayDatabase\Void_results'
DB_PATH = r'C:\Users\zbrzyy\Documents\Onsemi VN\XrayDatabase\file_tracker.db'

# Initialize logging
logging.basicConfig(
    filename=f'copy_log_{time.strftime("%Y%m%d")}.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

def init_database():
    """Initialize the database with necessary tables"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
        CREATE TABLE IF NOT EXISTS file_meta (
            src_path TEXT PRIMARY KEY,
            dest_path TEXT NOT NULL,
            mtime REAL NOT NULL,
            size INTEGER NOT NULL,
            last_updated REAL NOT NULL
        )
        ''')
        conn.commit()

def get_file_state(src_path):
    """Retrieve file state from database"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('''
        SELECT mtime, size, dest_path 
        FROM file_meta 
        WHERE src_path = ?
        ''', (src_path,))
        return cursor.fetchone()

def update_file_state(src_path, dest_path, mtime, size):
    """Update file state in database"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
        INSERT OR REPLACE INTO file_meta 
            (src_path, dest_path, mtime, size, last_updated)
        VALUES (?, ?, ?, ?, ?)
        ''', (src_path, dest_path, mtime, size, time.time()))
        conn.commit()

def copy_file(src_file, dest_file, src_dir):
    """Copy file using database state tracking"""
    try:
        src_path = os.path.normpath(src_file)
        src_stat = os.stat(src_file)
        src_mtime = src_stat.st_mtime
        src_size = src_stat.st_size

        # Check database for existing state
        db_state = get_file_state(src_path)
        if db_state:
            db_mtime, db_size, db_dest = db_state
            if src_mtime == db_mtime and src_size == db_size:
                if os.path.exists(db_dest):
                    logger.debug(f'Skipped (no changes): {os.path.basename(src_file)}')
                    return
                else:
                    logger.info(f'Re-copying missing file: {os.path.basename(src_file)}')

        # Perform file copy
        shutil.copy2(src_file, dest_file)
        print(f"Copied: {os.path.basename(src_file)}")

        # Verify destination
        dest_stat = os.stat(dest_file)
        if dest_stat.st_size != src_size:
            raise IOError(f"Size mismatch after copy: {src_size} vs {dest_stat.st_size}")

        # Update database
        update_file_state(src_path, dest_file, src_mtime, src_size)
        logger.info(f'Copied: {os.path.basename(src_file)}')

    except Exception as e:
        logger.error(f"Failed {os.path.basename(src_file)}: {str(e)}")
        print(f"Failed to copy: {os.path.basename(src_file)}")


@lru_cache(maxsize=1)
def list_destination_files(dest_dir):
    """Cache destination file list to reduce I/O"""
    return {f for f in os.listdir(dest_dir) if os.path.isfile(os.path.join(dest_dir, f))}

def process_files(source_dirs, dest_dir, file_extension):
    """Process files with thread pooling and batched operations"""
    dest_files = list_destination_files(dest_dir)
    os.makedirs(dest_dir, exist_ok=True)
    
    

    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for src_dir in source_dirs:
            print(f"Processing directory: {src_dir}")
            if not os.path.exists(src_dir):
                logger.warning(f"Source missing: {src_dir}")
                continue

            futures = []
            for fname in os.listdir(src_dir):
                if not fname.endswith(file_extension):
                    continue
                    
                src_file = os.path.join(src_dir, fname)
                dest_file = os.path.join(dest_dir, fname)
                
                # Skip if destination exists and not in database
                if fname in dest_files and not get_file_state(src_file):
                    logger.debug(f'Skipped (existing): {fname}')
                    continue
                
                futures.append(executor.submit(
                    copy_file, src_file, dest_file, src_dir
                ))

            # Handle task exceptions
            for future in concurrent.futures.as_completed(futures):
                if future.exception():
                    logger.error(f"Thread error: {future.exception()}")

def main():
    init_database()
    logger.info("===== Starting file sync =====")
    print("Starting file synchronization...")

    
    start_time = time.time()
    process_files(source_1, dest_1, '.lotx')
    process_files(source_2, dest_2, '.csv')
    
    logger.info(f"Completed in {time.time()-start_time:.2f} seconds")
    print(f"Synchronization completed in {time.time()-start_time:.2f} seconds.")    
    logger.info("===== Synchronization finished =====\n")

if __name__ == "__main__":
    main()
    
