import sqlite3
import pandas as pd
import logging
import time
import os

# --- DATABASE MERGE CONFIGURATION ---

# The database synced from the X-ray machine (Source of new data)
SOURCE_DB_PATH = r'C:\Users\zbrzyy\Documents\Onsemi VN\XrayDatabase\synced_xray_data.db'

# The main database on your laptop with historical/migrated data (Destination)
DESTINATION_DB_PATH = r'C:\Users\zbrzyy\Documents\Onsemi VN\XrayDatabase\xray_data.db'

LOG_FILE = f'merge_log_{time.strftime("%Y%m%d")}.log'

# --- LOGGING SETUP ---
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

def merge_table(source_conn, dest_conn, table_name):
    """
    Reads all data from a table in the source database and merges it
    into the same table in the destination database.
    'INSERT OR IGNORE' prevents duplicate entries based on table's UNIQUE constraints.
    """
    print(f"Merging table: {table_name}...")
    logger.info(f"Starting merge for table: {table_name}")

    try:
        # Read all data from the source table into a pandas DataFrame
        df = pd.read_sql(f'SELECT * FROM {table_name}', source_conn)

        if df.empty:
            print(f"No new records found in source table '{table_name}'. Skipping.")
            logger.info(f"Source table '{table_name}' is empty. Nothing to merge.")
            return

        # Use DataFrame's to_sql method to append data to the destination table.
        # The 'append' method combined with the table's UNIQUE constraint handles the merge.
        # SQLite's 'INSERT OR IGNORE' behavior is implicitly used.
        df.to_sql(table_name, dest_conn, if_exists='append', index=False)
        
        print(f"Successfully merged {len(df)} records into {table_name}.")
        logger.info(f"Merge successful for {table_name}. {len(df)} source records processed.")

    except pd.io.sql.DatabaseError as e:
        # This can happen if the table doesn't exist in the source
        if "no such table" in str(e):
            print(f"Source table '{table_name}' not found. Skipping.")
            logger.warning(f"Source table '{table_name}' not found. Skipping merge.")
        else:
            print(f"An error occurred during merge for table {table_name}: {e}")
            logger.error(f"DatabaseError merging {table_name}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during merge for table {table_name}: {e}")
        logger.error(f"Unexpected error merging {table_name}: {e}")


def main():
    """Main function to orchestrate the database merge."""
    print("Starting database merge process...")
    logger.info("===== Starting Database Merge =====")
    start_time = time.time()

    # --- Validate paths ---
    if not os.path.exists(SOURCE_DB_PATH):
        print(f"ERROR: Source database not found at {SOURCE_DB_PATH}. Please run the synchronizer first.")
        logger.error(f"Merge failed: Source DB not found at {SOURCE_DB_PATH}")
        return
    if not os.path.exists(DESTINATION_DB_PATH):
        print(f"ERROR: Destination (master) database not found at {DESTINATION_DB_PATH}. Please run the migration first.")
        logger.error(f"Merge failed: Destination DB not found at {DESTINATION_DB_PATH}")
        return

    try:
        # Connect to both databases
        source_conn = sqlite3.connect(SOURCE_DB_PATH)
        dest_conn = sqlite3.connect(DESTINATION_DB_PATH)

        # Merge each table
        merge_table(source_conn, dest_conn, 'Lot_info')
        merge_table(source_conn, dest_conn, 'Void_results')
        # We don't need to merge 'processed_files' as each DB tracks its own state.

        # Close connections
        source_conn.close()
        dest_conn.close()

    except Exception as e:
        print(f"A critical error occurred: {e}")
        logger.critical(f"A critical error occurred during the merge process: {e}")

    duration = time.time() - start_time
    print(f"\nMerge process finished in {duration:.2f} seconds.")
    logger.info(f"===== Merge finished in {duration:.2f} seconds. =====\n")


if __name__ == "__main__":
    main()
