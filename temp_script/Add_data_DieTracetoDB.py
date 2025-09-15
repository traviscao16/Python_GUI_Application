# -*- coding: utf-8 -*-
"""
Append CSV vào SQLite hiện có, dọn trùng hiện hữu và ngăn trùng về sau.
Không dùng tham số dòng lệnh; chỉnh ở mục THAM SỐ bên dưới.

Yêu cầu: pandas
  pip install pandas
"""

import os
import sys
import time
import sqlite3
import logging
from pathlib import Path

import pandas as pd

# =============== THAM SỐ ===============
file_path   = r"C:\Users\zbrzyy\Desktop\Logcheck\ceramic crack\Lot_Traceback\Die Trace_ww31-34.csv"
sqlite_path = r"C:\Users\zbrzyy\Desktop\Logcheck\ceramic crack\Lot_Traceback\lotfrom21-31.sqlite"
TABLE_NAME  = "lot_traceback"

# Có thể điều chỉnh thêm:
ENCODING        = "utf-16"     # 'utf-16' cho file UTF-16; nếu file UTF-8 thì đổi 'utf-8'
ENGINE          = "python"     # 'python' ổn định cho UTF-16
CHUNK_SIZE      = 200_000      # số dòng mỗi chunk
COMMIT_INTERVAL = 5            # commit mỗi N chunk để nhanh hơn
DEDUP_FIRST     = True         # dọn dữ liệu trùng sẵn có trước khi import
VACUUM_AFTER_DEDUP = True      # VACUUM sau dọn trùng để thu gọn DB
LF_POS_FORMULA_OFFSET = 10     # LF_POS = 10 - leadframe_x (chỉnh nếu cần)

# =============== LOGGING ===============
def setup_logging():
    log_dir = Path(__file__).resolve().parent
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
    return logging.getLogger("die_trace")

log = setup_logging()

# =============== UTILS ===============
def human(n: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(n) < 1024.0:
            return f"{n:,.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"

def exec_pragma(con: sqlite3.Connection):
    cur = con.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.execute("PRAGMA temp_store=MEMORY;")
    cur.execute("PRAGMA cache_size=-200000;")  # ~200 MB page cache
    con.commit()

def ensure_table(con: sqlite3.Connection, table: str):
    cur = con.cursor()
    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS {table} (
        Lot TEXT,
        internal2did_id TEXT,
        leadframe_id TEXT,
        leadframe_x INTEGER,
        dbc_id TEXT,
        singulation_id TEXT,
        LF_POS INTEGER
    );
    """)
    # Index phục vụ truy vấn
    cur.execute(f"CREATE INDEX IF NOT EXISTS ix_{table}_lot ON {table}(Lot);")
    cur.execute(f"CREATE INDEX IF NOT EXISTS ix_{table}_i2d ON {table}(internal2did_id);")
    cur.execute(f"CREATE INDEX IF NOT EXISTS ix_{table}_lf ON {table}(leadframe_id);")
    con.commit()

def create_unique_index(con: sqlite3.Connection, table: str, index_name: str):
    cur = con.cursor()
    cur.execute(f"""
    CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON {table} (
        IFNULL(Lot,''),
        IFNULL(internal2did_id,''),
        IFNULL(leadframe_id,''),
        IFNULL(leadframe_x,-1),
        IFNULL(dbc_id,''),
        IFNULL(singulation_id,''),
        IFNULL(LF_POS,-1)
    );
    """)
    con.commit()

def dedup_existing_rows(con: sqlite3.Connection, table: str) -> int:
    """
    Xoá dữ liệu trùng trong bảng hiện có, giữ lại bản ghi có rowid nhỏ nhất
    theo khóa chuẩn hoá (IFNULL ...). Trả về số dòng đã xoá.
    """
    cur = con.cursor()
    prev_changes = con.total_changes
    log.info(f"Dọn dữ liệu trùng hiện có trong '{table}' (có thể mất thời gian nếu bảng lớn)...")
    cur.execute("BEGIN;")
    try:
        cur.execute(f"""
            DELETE FROM {table}
            WHERE rowid NOT IN (
                SELECT MIN(rowid)
                FROM {table}
                GROUP BY
                  IFNULL(Lot,''),
                  IFNULL(internal2did_id,''),
                  IFNULL(leadframe_id,''),
                  IFNULL(leadframe_x,-1),
                  IFNULL(dbc_id,''),
                  IFNULL(singulation_id,''),
                  IFNULL(LF_POS,-1)
            );
        """)
        con.commit()
    except Exception:
        con.rollback()
        raise
    deleted = con.total_changes - prev_changes
    log.info(f"Dọn trùng xong: đã xoá {deleted:,} dòng.")
    return deleted

def analyze_optimize(con: sqlite3.Connection, table: str):
    cur = con.cursor()
    cur.execute(f"ANALYZE {table};")
    cur.execute("PRAGMA optimize;")
    con.commit()

def import_csv_append(
    file_path: str,
    sqlite_path: str,
    table: str,
    encoding: str = ENCODING,
    engine: str = ENGINE,
    chunk_size: int = CHUNK_SIZE,
    commit_interval: int = COMMIT_INTERVAL,
    lf_pos_offset: int = LF_POS_FORMULA_OFFSET
):
    """
    Append CSV vào SQLite hiện có, bỏ qua trùng nhờ UNIQUE INDEX + INSERT OR IGNORE.
    """
    usecols = ['Lot', 'internal2did_id', 'leadframe_id', 'leadframe_x', 'dbc_id', 'singulation_id']
    dtype_map = {c: 'string' for c in usecols}
    cols_out = ['Lot','internal2did_id','leadframe_id','leadframe_x','dbc_id','singulation_id','LF_POS']

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"CSV not found: {file_path}")

    con = sqlite3.connect(sqlite_path)
    exec_pragma(con)
    ensure_table(con, table)

    file_size = os.path.getsize(file_path)
    log.info("Bắt đầu APPEND → SQLite")
    log.info(f"Input:  {file_path} ({human(file_size)})")
    log.info(f"Output: {sqlite_path}")
    log.info(f"Table:  {table}")
    log.info(f"Encoding={encoding}, engine={engine}, sep=',', CHUNK_SIZE={chunk_size:,}")

    total_read = 0
    total_inserted = 0
    prev_changes = con.total_changes

    cur = con.cursor()
    cur.execute("BEGIN;")
    chunks_since_commit = 0

    try:
        reader = pd.read_csv(
            file_path,
            encoding=encoding,
            sep=',',
            engine=engine,
            usecols=usecols,
            dtype=dtype_map,
            chunksize=chunk_size,
            low_memory=True
        )
        for i, chunk in enumerate(reader, start=1):
            t0 = time.time()
            n_in = len(chunk)
            total_read += n_in

            # leadframe_x -> Int64, tính LF_POS = offset - leadframe_x
            lf_x = pd.to_numeric(chunk['leadframe_x'], errors='coerce').astype('Int64')
            chunk['leadframe_x'] = lf_x
            chunk['LF_POS'] = (lf_pos_offset - lf_x).astype('Int64')

            # Dedup trong chunk để giảm I/O
            before = len(chunk)
            chunk = chunk.drop_duplicates()
            after = len(chunk)

            # đảm bảo cột text là object để nhận None
            for c in ['Lot','internal2did_id','leadframe_id','dbc_id','singulation_id']:
                chunk[c] = chunk[c].astype('object')

            def pyval(col, v):
                if pd.isna(v):
                    return None
                if col in ('leadframe_x','LF_POS'):
                    return int(v)
                return str(v)

            rows = [
                tuple(pyval(col, v) for col, v in zip(cols_out, rec))
                for rec in chunk[cols_out].itertuples(index=False, name=None)
            ]

            cur.executemany(
                f"""INSERT OR IGNORE INTO {table}
                    (Lot, internal2did_id, leadframe_id, leadframe_x, dbc_id, singulation_id, LF_POS)
                    VALUES (?,?,?,?,?,?,?)""",
                rows
            )

            inserted = con.total_changes - prev_changes
            prev_changes = con.total_changes
            total_inserted += inserted

            dt = time.time() - t0
            rate = after / dt if dt > 0 else 0.0
            db_size = os.path.getsize(sqlite_path) if os.path.exists(sqlite_path) else 0
            log.info(
                f"Chunk {i:>5}: read={n_in:,} → after_dedup={after:,} | "
                f"inserted={inserted:,} | rate={rate:,.0f} rows/s | DB={human(db_size)} | {dt:,.2f}s"
            )

            chunks_since_commit += 1
            if chunks_since_commit >= commit_interval:
                con.commit()
                cur.execute("BEGIN;")
                chunks_since_commit = 0

        con.commit()
        analyze_optimize(con, table)

    except Exception:
        con.rollback()
        log.exception("ERROR during import")
        raise
    finally:
        con.close()

    log.info(f"Hoàn tất import. Total_read={total_read:,}, Total_inserted={total_inserted:,}")

# =============== MAIN ===============
def main():
    start_all = time.time()

    if not os.path.exists(sqlite_path):
        # Nếu DB chưa có, sẽ tạo mới (append vào DB trống)
        Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)

    # 1) Mở DB & chuẩn bị schema
    con = sqlite3.connect(sqlite_path)
    exec_pragma(con)
    ensure_table(con, TABLE_NAME)

    # 2) Dọn trùng hiện có (nếu bật)
    if DEDUP_FIRST:
        try:
            deleted = dedup_existing_rows(con, TABLE_NAME)
            if VACUUM_AFTER_DEDUP and deleted > 0:
                log.info("VACUUM để thu gọn file DB...")
                con.execute("VACUUM;")
                con.commit()
        except Exception:
            log.exception("Lỗi khi dọn dữ liệu trùng hiện có")
            con.close()
            sys.exit(2)

    # 3) Tạo UNIQUE INDEX để ngăn trùng về sau
    ux_name = f"ux_{TABLE_NAME}_dedup"
    try:
        log.info(f"Tạo UNIQUE INDEX '{ux_name}' (nếu chưa có) để chống trùng...")
        create_unique_index(con, TABLE_NAME, ux_name)
    except Exception:
        log.exception("Tạo UNIQUE INDEX thất bại (có thể DB còn trùng). "
                      "Hãy bật DEDUP_FIRST=True rồi chạy lại.")
        con.close()
        sys.exit(3)

    con.close()

    # 4) Append CSV và bỏ qua trùng
    try:
        import_csv_append(
            file_path=file_path,
            sqlite_path=sqlite_path,
            table=TABLE_NAME,
            encoding=ENCODING,
            engine=ENGINE,
            chunk_size=CHUNK_SIZE,
            commit_interval=COMMIT_INTERVAL,
            lf_pos_offset=LF_POS_FORMULA_OFFSET
        )
    except Exception:
        log.exception("Import thất bại")
        sys.exit(4)

    log.info(f"ALL DONE trong {time.time() - start_all:,.1f}s. SQLite ở: {sqlite_path}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.warning("Bị dừng bởi người dùng (Ctrl+C).")
        sys.exit(130)
