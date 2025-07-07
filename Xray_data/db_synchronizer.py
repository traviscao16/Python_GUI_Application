import os
import shutil
import time
import logging

# --- DATABASE SYNCHRONIZER CONFIGURATION ---

# Path to the database on the X-ray machine (as seen from your laptop's network)
# IMPORTANT: You must ensure the folder containing the DB on the X-ray machine is a shared folder.
# Example: \\XRAY-MACHINE-IP\shared_folder\local_xray_data.db
SOURCE_DB_PATH = r'\\XRAY-MACHINE-IP\path\to\shared\folder\local_xray_data.db'

# Path where you want to save the database on your local laptop
DESTINATION_DB_PATH = r'C:\Users\zbrzyy\Documents\Onsemi VN\XrayDatabase\synced_xray_data.db'

LOG_FILE = f'sync_log_{time.strftime("%Y%m%d")}.log'

# --- LOGGING SETUP ---
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

def sync_database():
    """Copies the database from the source to the destination."""
    print(f"Attempting to sync database from: {SOURCE_DB_PATH}")
    logger.info(f"Starting sync from {SOURCE_DB_PATH} to {DESTINATION_DB_PATH}")

    # --- 1. Check if source database exists ---
    if not os.path.exists(SOURCE_DB_PATH):
        error_msg = f"Source database not found at {SOURCE_DB_PATH}. Please check the network path and ensure the folder is shared."
        print(f"ERROR: {error_msg}")
        logger.error(error_msg)
        return

    # --- 2. Check if destination directory exists ---
    dest_dir = os.path.dirname(DESTINATION_DB_PATH)
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
        print(f"Created destination directory: {dest_dir}")
        logger.info(f"Created destination directory: {dest_dir}")

    # --- 3. Perform the copy ---
    try:
        shutil.copy2(SOURCE_DB_PATH, DESTINATION_DB_PATH)
        success_msg = f"Successfully synced database to: {DESTINATION_DB_PATH}"
        print(success_msg)
        logger.info(success_msg)
    except Exception as e:
        error_msg = f"Failed to copy database: {e}"
        print(f"ERROR: {error_msg}")
        logger.error(error_msg)

def main():
    """Main function to run the synchronizer."""
    start_time = time.time()
    sync_database()
    duration = time.time() - start_time
    print(f"Synchronization process finished in {duration:.2f} seconds.")
    logger.info(f"Sync process finished in {duration:.2f} seconds.\n")

if __name__ == "__main__":
    main()
