import os
import fnmatch
import sqlite3
import xml.etree.ElementTree as ET
from tqdm import tqdm  # For progress tracking

# Configuration
lotx_folder = r'C:\Users\zbrzyy\Documents\Onsemi VN\XrayDatabase\Lot_Info'
db_path = r'C:\Users\zbrzyy\Documents\Onsemi VN\XrayDatabase\Lot_Info_database.db'
batch_size = 100  # Process files in batches for better performance

def setup_database(conn):
    """Initialize database structure with tracking system"""
    conn.execute("PRAGMA journal_mode = WAL")  # Better concurrency
    conn.execute("PRAGMA synchronous = NORMAL")  # Good balance between safety and speed
    
    # Main data table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS Lot_info (
        LotId TEXT, Recipe TEXT, AllowSizeNull TEXT, CountUniqueBarcodesOnly TEXT, 
        Size INTEGER, CarrierIndex INTEGER, TrayId TEXT, TrayState INTEGER, 
        TrayCode TEXT, UnitId TEXT, UnitState INTEGER, UnitCode TEXT, UnitIdx INTEGER,
        UNIQUE(LotId, TrayId, UnitIdx)
    )""")
    
    # File tracking table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS processed_files (
        filename TEXT PRIMARY KEY,
        last_modified REAL,
        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

def process_xml_file(file_path, conn):
    """Process single XML file and return data batch"""
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    # Extract common lot information
    lot_attrs = {
        'lot_id': root.attrib.get('Id'),
        'recipe': root.attrib.get('Recipe'),
        'allow_size_null': root.attrib.get('AllowSizeNull'),
        'count_unique_barcodes_only': root.attrib.get('CountUniqueBarcodesOnly'),
        'size': int(root.attrib.get('Size', 0)),
        'carrier_index': int(root.attrib.get('CarrierIndex', 0))
    }
    
    batch = []
    # Extract tray and unit information
    trays = root.find('Trays')
    if trays is None:
        trays = []
    
    for tray in trays:
        tray_attrs = {
            'tray_id': tray.attrib.get('Id'),
            'tray_state': int(tray.attrib.get('State', 0)),
            'tray_code': tray.attrib.get('Code')
        }
        
        units = tray.find('Units')
        if units is None:
            units = []
        for unit in units:
            unit_attrs = {
                'unit_id': unit.attrib.get('Id'),
                'unit_state': int(unit.attrib.get('State', 0)),
                'unit_code': unit.attrib.get('Code'),
                'unit_idx': int(unit.attrib.get('Idx', 0))
            }
            
            # Combine all attributes into a single record
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
                unit_attrs['unit_idx']
            )
            batch.append(record)
    
    return batch

def process_lotx_files():
    """Main processing function with restart capability"""
    with sqlite3.connect(db_path) as conn:
        setup_database(conn)
        
        # Get already processed files
        processed_files = set()
        try:
            processed_files = set(row[0] for row in 
                conn.execute("SELECT filename FROM processed_files").fetchall())
        except sqlite3.OperationalError:
            pass  # Table doesn't exist yet
            
        # Find all candidate files with their modification times
        all_files = []
        for filename in os.listdir(lotx_folder):
            if fnmatch.fnmatch(filename, '*.lotx'):
                file_path = os.path.join(lotx_folder, filename)
                mtime = os.path.getmtime(file_path)
                
                # Check if needs processing
                if filename not in processed_files:
                    all_files.append((filename, file_path, mtime))
                else:
                    # Check if file has been modified since last processing
                    stored_mtime = conn.execute(
                        "SELECT last_modified FROM processed_files WHERE filename=?",
                        (filename,)
                    ).fetchone()
                    if stored_mtime and stored_mtime[0] < mtime:
                        all_files.append((filename, file_path, mtime))

        with tqdm(total=len(all_files), desc="Processing files") as pbar:
            for i in range(0, len(all_files), batch_size):
                batch_files = all_files[i:i+batch_size]
                all_records = []
                file_metadata = []

                try:
                    for filename, file_path, mtime in batch_files:
                        records = process_xml_file(file_path, conn)
                        if records:
                            all_records.extend(records)
                            file_metadata.append((filename, mtime))

                    # Bulk insert using executemany
                    if all_records:
                        conn.executemany(
                            """INSERT OR REPLACE INTO Lot_info
                            (LotId, Recipe, AllowSizeNull, CountUniqueBarcodesOnly,
                             Size, CarrierIndex, TrayId, TrayState, TrayCode,
                             UnitId, UnitState, UnitCode, UnitIdx)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            all_records
                        )
                        
                        # Update processed files tracking
                        conn.executemany(
                            """INSERT OR REPLACE INTO processed_files
                            (filename, last_modified) VALUES (?, ?)""",
                            file_metadata
                        )

                    conn.commit()
                    pbar.update(len(batch_files))
                except Exception as e:
                    conn.rollback()
                    print(f"Error processing batch {i//batch_size}: {str(e)}")
                    # Consider adding retry logic here

if __name__ == "__main__":
    process_lotx_files()
