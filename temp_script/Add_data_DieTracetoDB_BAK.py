import os, sys, time, sqlite3, logging, traceback
import pandas as pd
from pathlib import Path

# =============== LOGGING ===============
log_dir = Path(__file__).with_suffix('').parent
log_file = log_dir / "die_trace_run.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8")
    ]
)
log = logging.getLogger("die_trace")

# =============== THAM SỐ ===============
file_path = r"C:\Users\zbrzyy\Desktop\Logcheck\ceramic crack\Lot_Traceback\lotfrom21-31.csv"
sqlite_path = r"C:\Users\zbrzyy\Desktop\Logcheck\ceramic crack\Lot_Traceback\lotfrom21-31.sqlite"
TABLE_NAME = "lot_traceback"

# Với UTF-16 + engine='python', chunk nhỏ một chút cho mượt (100k~300k)
CHUNK_SIZE = 200_000

usecols = ['Lot', 'internal2did_id', 'leadframe_id', 'leadframe_x', 'dbc_id', 'singulation_id']
dtype_map = {c: 'string' for c in usecols}

def human(n):
    for unit in ['B','KB','MB','GB','TB']:
        if abs(n) < 1024.0:
            return f"{n:,.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"

def main():
    start_all = time.time()

    if not os.path.exists(file_path):
        log.error(f"INPUT NOT FOUND: {file_path}")
        sys.exit(1)

    # Với UTF-16, pandas sẽ hoạt động ổn nhất với engine='python'
    encoding = 'utf-16'      # hoặc 'utf-16-le' nếu file LE
    engine = 'python'
    file_size = os.path.getsize(file_path)
    log.info(f"Start import → SQLite")
    log.info(f"Input:  {file_path} ({human(file_size)})")
    log.info(f"Output: {sqlite_path}")
    log.info(f"Table:  {TABLE_NAME}")
    log.info(f"Encoding={encoding}, engine={engine}, sep=',', CHUNK_SIZE={CHUNK_SIZE:,}")

    # Chuẩn bị DB (overwrite nếu tồn tại)
    if os.path.exists(sqlite_path):
        log.info("Remove existing SQLite file (overwrite).")
        os.remove(sqlite_path)

    con = sqlite3.connect(sqlite_path)
    cur = con.cursor()
    # Tối ưu import
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.execute("PRAGMA temp_store=MEMORY;")
    cur.execute("PRAGMA cache_size=-200000;")  # ~200 MB page cache
    con.commit()

    # Tạo bảng
    cur.execute(f"""
    CREATE TABLE {TABLE_NAME} (
        Lot TEXT,
        internal2did_id TEXT,
        leadframe_id TEXT,
        leadframe_x INTEGER,
        dbc_id TEXT,
        singulation_id TEXT,
        LF_POS INTEGER
    );
    """)
    con.commit()

    # UNIQUE INDEX để dedup toàn cục (coi NULL là trùng nhau nhờ IFNULL)
    cur.execute(f"""
    CREATE UNIQUE INDEX ux_{TABLE_NAME}_dedup ON {TABLE_NAME} (
        IFNULL(Lot,''),
        IFNULL(internal2did_id,''),
        IFNULL(leadframe_id,''),
        IFNULL(leadframe_x,-1),
        IFNULL(dbc_id,''),
        IFNULL(singulation_id,''),
        IFNULL(LF_POS,-1)
    );
    """)
    # Index truy vấn
    cur.execute(f"CREATE INDEX ix_{TABLE_NAME}_lot ON {TABLE_NAME}(Lot);")
    cur.execute(f"CREATE INDEX ix_{TABLE_NAME}_i2d ON {TABLE_NAME}(internal2did_id);")
    cur.execute(f"CREATE INDEX ix_{TABLE_NAME}_lf ON {TABLE_NAME}(leadframe_id);")
    con.commit()
    log.info("SQLite schema ready.")

    total_read = 0
    total_ins = 0
    prev_changes = con.total_changes

    try:
        reader = pd.read_csv(
            file_path,
            encoding=encoding,
            sep=',',             # CSV comma
            engine=engine,       # bắt buộc cho UTF-16
            usecols=usecols,
            dtype=dtype_map,
            chunksize=CHUNK_SIZE,
            low_memory=True
        )
        for i, chunk in enumerate(reader, start=1):
            t0 = time.time()
            n_in = len(chunk)
            total_read += n_in

            # leadframe_x -> Int64, tính LF_POS
            lf_x = pd.to_numeric(chunk['leadframe_x'], errors='coerce').astype('Int64')
            chunk['leadframe_x'] = lf_x
            chunk['LF_POS'] = (10 - lf_x).astype('Int64')

            # Dedup trong chunk để giảm I/O
            before = len(chunk)
            chunk = chunk.drop_duplicates()
            after = len(chunk)

            cols = ['Lot','internal2did_id','leadframe_id','leadframe_x','dbc_id','singulation_id','LF_POS']

            # Bảo đảm cột text là object để nhận None
            for c in ['Lot','internal2did_id','leadframe_id','dbc_id','singulation_id']:
                chunk[c] = chunk[c].astype('object')

            def pyval(col, v):
                if pd.isna(v):
                    return None
                if col in ('leadframe_x','LF_POS'):
                    return int(v)
                return str(v)

            rows = [
                tuple(pyval(col, v) for col, v in zip(cols, rec))
                for rec in chunk[cols].itertuples(index=False, name=None)
            ]

            cur.executemany(
                f"""INSERT OR IGNORE INTO {TABLE_NAME}
                    (Lot, internal2did_id, leadframe_id, leadframe_x, dbc_id, singulation_id, LF_POS)
                    VALUES (?,?,?,?,?,?,?)""",
                rows
            )
            con.commit()


            inserted = con.total_changes - prev_changes
            prev_changes = con.total_changes
            total_ins += inserted

            dt = time.time() - t0
            rate = after / dt if dt > 0 else 0.0
            db_size = os.path.getsize(sqlite_path) if os.path.exists(sqlite_path) else 0

            logging.info(
                f"Chunk {i:>5}: read={n_in:,} → after_dedup={after:,} | "
                f"inserted={inserted:,} | rate={rate:,.0f} rows/s | DB={human(db_size)} | {dt:,.2f}s"
            )

        # Tối ưu truy vấn
        cur.execute(f"ANALYZE {TABLE_NAME};")
        cur.execute("PRAGMA optimize;")
        con.commit()
        log.info("ANALYZE & PRAGMA optimize done.")
    except Exception:
        log.exception("ERROR during import")
        raise
    finally:
        con.close()

    log.info(
        f"Done. Total_read={total_read:,}, Total_inserted={total_ins:,}, "
        f"Wall_time={time.time()-start_all:,.1f}s"
    )
    log.info(f"SQLite DB at: {sqlite_path}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.warning("Interrupted by user (Ctrl+C).")
        sys.exit(130)
