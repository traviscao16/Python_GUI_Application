
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import csv
from io import StringIO
import os
import json
from pathlib import Path
import re

# =========================
# CẤU HÌNH & LƯU TRẠNG THÁI
# =========================
DEFAULT_DB_PATH = r"C:\Users\zbrzyy\Desktop\Logcheck\ceramic crack\Lot_Traceback\lotfrom21-31.sqlite"
APP_DIR = Path(__file__).resolve().parent
SETTINGS_FILE = APP_DIR / "settings.json"


def load_settings():
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_settings(data: dict):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        messagebox.showwarning("Warning", f"Không thể lưu settings: {e}")


def list_db_files_in_dir(dir_path: Path):
    # Ưu tiên *.sqlite rồi đến *.db, *.sqlite3
    patterns = ["*.sqlite", "*.db", "*.sqlite3"]
    files = []
    for pat in patterns:
        files.extend(sorted(Path(dir_path).glob(pat)))
    # Sắp xếp theo thời gian sửa đổi mới nhất (desc)
    files = sorted(files, key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return files


def resolve_db_path(value: str):
    """
    Nhận vào: đường dẫn người dùng nhập (có thể là file hoặc folder), hoặc chuỗi rỗng.
    Trả về: đường dẫn file DB hợp lệ (str).
    Quy tắc:
    - Nếu là file hợp lệ: dùng luôn.
    - Nếu là folder: tìm file DB trong folder; nếu nhiều → mở dialog cho chọn.
    - Nếu rỗng: thử settings → app folder → DEFAULT_DB_PATH.
    """
    value = (value or "").strip()
    settings = load_settings()

    def choose_from_many(initial_dir: Path):
        # Nếu nhiều file, cho user chọn 1 file
        return filedialog.askopenfilename(
            title="Chọn file database",
            initialdir=str(initial_dir),
            filetypes=[("SQLite DB", "*.sqlite *.db *.sqlite3"), ("All files", "*.*")]
        )

    # Nếu người dùng để trống, chọn theo ưu tiên
    if not value:
        # 1) Đường dẫn đã lưu
        last = settings.get("last_db_path", "").strip()
        if last:
            p = Path(os.path.expandvars(last))
            if p.is_file():
                return str(p)
            if p.is_dir():
                cands = list_db_files_in_dir(p)
                if len(cands) == 1:
                    return str(cands[0])
                elif len(cands) > 1:
                    chosen = choose_from_many(p)
                    if chosen:
                        return chosen

        # 2) Thư mục app
        local_cands = list_db_files_in_dir(APP_DIR)
        if len(local_cands) == 1:
            return str(local_cands[0])
        elif len(local_cands) > 1:
            chosen = choose_from_many(APP_DIR)
            if chosen:
                return chosen

        # 3) Fallback default
        return DEFAULT_DB_PATH

    # Nếu người dùng có nhập path/file
    p = Path(os.path.expandvars(value))
    if p.is_file():
        return str(p)
    if p.is_dir():
        cands = list_db_files_in_dir(p)
        if len(cands) == 0:
            raise FileNotFoundError(f"Không tìm thấy file database (*.sqlite, *.db, *.sqlite3) trong thư mục:{p}")
        elif len(cands) == 1:
            return str(cands[0])
        else:
            chosen = filedialog.askopenfilename(
                title="Chọn file database",
                initialdir=str(p),
                filetypes=[("SQLite DB", "*.sqlite *.db *.sqlite3"), ("All files", "*.*")]
            )
            if not chosen:
                raise FileNotFoundError("Bạn chưa chọn file database.")
            return chosen

    # Thử relative path tính từ thư mục app
    p2 = (APP_DIR / value)
    if p2.is_file():
        return str(p2)
    if p2.is_dir():
        cands = list_db_files_in_dir(p2)
        if len(cands) == 0:
            raise FileNotFoundError(f"Không tìm thấy file database trong thư mục:{p2}")
        elif len(cands) == 1:
            return str(cands[0])
        else:
            chosen = filedialog.askopenfilename(
                title="Chọn file database",
                initialdir=str(p2),
                filetypes=[("SQLite DB", "*.sqlite *.db *.sqlite3"), ("All files", "*.*")]
            )
            if not chosen:
                raise FileNotFoundError("Bạn chưa chọn file database.")
            return chosen

    # Cuối cùng: trả về nguyên văn (có thể là UNC hoặc path chưa tồn tại → sẽ báo lỗi lúc connect)
    return str(p)


# =========================
# PARSE INPUT LINH HOẠT
# =========================
def parse_input_text(raw_text: str):
    """
    - Chấp nhận: có header hoặc không; header tên/format không cần đúng.
    - Delimiter: ',', ';', hoặc '	'
    - Lấy 3 cột đầu: (Lot no, LF ID, LF Pos). Query dùng (LF ID, LF Pos).
    - Bỏ qua dòng đầu nếu cột 3 không phải số (coi là header).
    - Khử trùng lặp các cặp (LF_ID, LF_POS).
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("Vui lòng nhập dữ liệu (3 cột: Lot no, LF ID, LF Pos).")

    normalized = raw_text.replace("	", ",").replace(";", ",")
    reader = csv.reader(StringIO(normalized))
    rows = [[c.strip() for c in row] for row in reader if any(c.strip() for c in row)]
    if not rows:
        raise ValueError("Không tìm thấy dòng dữ liệu hợp lệ.")

    def looks_like_data(row):
        if len(row) < 3:
            return False
        try:
            int(row[2])
            return True
        except:
            return False

    start_idx = 0
    if rows and not looks_like_data(rows[0]):
        start_idx = 1

    pairs = []
    errors = []
    for i, row in enumerate(rows[start_idx:], start=start_idx + 1):
        if len(row) < 3:
            errors.append(f"Dòng {i}: không đủ 3 cột.")
            continue
        lot_no, lf_id, lf_pos_str = row[0], row[1], row[2]
        try:
            lf_pos = int(lf_pos_str)
        except Exception:
            errors.append(f"Dòng {i}: cột 3 (LF Pos) phải là số nguyên. Giá trị: '{lf_pos_str}'")
            continue
        lf_id = (lf_id or "").strip()
        if not lf_id:
            errors.append(f"Dòng {i}: LF ID trống.")
            continue
        pairs.append((lf_id, lf_pos))

    if not pairs:
        raise ValueError("Không có dòng dữ liệu hợp lệ để truy vấn." + ("".join(errors) if errors else ""))

    # khử trùng lặp, giữ thứ tự
    pairs = list(dict.fromkeys(pairs))
    return pairs, errors


# =========================
# LOGIC TRUY VẤN
# =========================
query_results = []
current_columns = ["internal2did_id", "Lot", "leadframe_id", "LF_POS"]  # mặc định cho Tab 1


def set_tree_columns(cols):
    """Cấu hình lại cột Treeview theo danh sách cột 'cols'."""
    global current_columns, tree
    current_columns = list(cols)
    # Xóa toàn bộ dòng cũ
    for row in tree.get_children():
        tree.delete(row)
    # Đặt lại danh sách cột
    tree["columns"] = cols
    # Cập nhật heading/width
    for col in cols:
        tree.heading(col, text=col)
        w = 120 if len(col) <= 18 else 160
        tree.column(col, width=w, stretch=True)


def get_table_columns(conn, table_name="lot_traceback"):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table_name})")
    info = cur.fetchall()
    # PRAGMA table_info: (cid, name, type, notnull, dflt_value, pk)
    return [row[1] for row in info]


def _connect_resolved_db():
    user_input_path = entry_db_path.get()
    resolved_db = resolve_db_path(user_input_path)
    conn = sqlite3.connect(resolved_db)
    # Lưu lại DB path sau cùng (chỉ khi kết nối thành công)
    settings = load_settings()
    settings["last_db_path"] = resolved_db
    save_settings(settings)
    entry_db_path.delete(0, tk.END)
    entry_db_path.insert(0, resolved_db)
    return conn


def query_database():  # Tab 1
    raw_text = text_input_tab1.get("1.0", tk.END)
    progress_label.config(text="Processing...")
    root.update_idletasks()

    try:
        pairs, parse_warnings = parse_input_text(raw_text)
    except Exception as e:
        progress_label.config(text="")
        messagebox.showerror("Input Error", str(e))
        return

    try:
        conn = _connect_resolved_db()
        cursor = conn.cursor()
    except Exception as e:
        progress_label.config(text="")
        messagebox.showerror("Database Error", f"Không thể kết nối database:{e}")
        return

    global query_results
    query_results = []

    # Đảm bảo cột chuẩn 4 cột cho truy vấn kiểu LF_ID/LF_POS
    default_cols = ["internal2did_id", "Lot", "leadframe_id", "LF_POS"]
    set_tree_columns(default_cols)

    query = """
        SELECT internal2did_id, Lot, leadframe_id, LF_POS
        FROM lot_traceback
        WHERE leadframe_id = ? AND LF_POS = ?
    """

    try:
        for lf_id, lf_pos in pairs:
            cursor.execute(query, (lf_id, lf_pos))
            query_results.extend(cursor.fetchall())
    except Exception as e:
        messagebox.showerror("Query Error", str(e))
    finally:
        conn.close()

    # Cập nhật bảng kết quả
    for result in query_results:
        tree.insert("", tk.END, values=result)

    status = f"Done! Input: {len(pairs)} dòng — Kết quả: {len(query_results)} dòng"
    if parse_warnings:
        status += f"  Cảnh báo: {len(parse_warnings)} dòng bị bỏ qua."
    progress_label.config(text=status)


def reverse_query_database():  # Tab 2 (LIKE, NOCASE)
    ids_raw = text_input_tab2.get("1.0", tk.END).strip()
    if not ids_raw:
        messagebox.showerror("Input Error", "Vui lòng nhập ít nhất 1 internal2did_id.")
        return

    # Chấp nhận phân tách bởi dấu phẩy, chấm phẩy, khoảng trắng, xuống dòng
    tokens = [x.strip() for x in re.split(r"[,;\s]+", ids_raw) if x.strip()]
    # Khử trùng lặp, giữ thứ tự
    ids = list(dict.fromkeys(tokens))
    if not ids:
        messagebox.showerror("Input Error", "Không tìm thấy internal2did_id hợp lệ.")
        return

    progress_label.config(text="Processing (Reverse Query)...")
    root.update_idletasks()

    try:
        conn = _connect_resolved_db()
    except Exception as e:
        progress_label.config(text="")
        messagebox.showerror("Database Error", f"Không thể kết nối database:{e}")
        return

    # Lấy danh sách cột động
    try:
        cols = get_table_columns(conn, "lot_traceback")
        if not cols:
            cols = ["internal2did_id", "Lot", "leadframe_id", "LF_POS"]
    except Exception:
        cols = ["internal2did_id", "Lot", "leadframe_id", "LF_POS"]

    # Cập nhật Treeview theo full columns
    set_tree_columns(cols)

    # Dựng truy vấn SELECT trả về toàn bộ cột + LIKE theo batches
    quoted_cols = ",".join([f"[{c}]" for c in cols])  # bao cột tránh ký tự đặc biệt
    batch_size = 500  # an toàn < 999 (giới hạn tham số mặc định của SQLite)
    global query_results
    query_results = []

    try:
        cur = conn.cursor()
        for i in range(0, len(ids), batch_size):
            batch = ids[i:i + batch_size]
            # WHERE internal2did_id LIKE ? OR internal2did_id LIKE ? ...
            or_parts = ["internal2did_id LIKE ? COLLATE NOCASE" for _ in batch]
            sql = f"SELECT {quoted_cols} FROM lot_traceback WHERE " + " OR ".join(or_parts)
            params = [f"%{x}%" for x in batch]
            cur.execute(sql, params)
            query_results.extend(cur.fetchall())
    except Exception as e:
        messagebox.showerror("Query Error", str(e))
    finally:
        conn.close()

    # Cập nhật bảng kết quả
    for row in tree.get_children():
        tree.delete(row)
    for result in query_results:
        tree.insert("", tk.END, values=result)

    progress_label.config(
        text=f"Reverse Query xong. ID nhập: {len(ids)} — Kết quả: {len(query_results)} dòng."
    )


def query_by_lot_database():  # Tab 3 (LIKE, NOCASE)
    lots_raw = text_input_tab3.get("1.0", tk.END).strip()
    if not lots_raw:
        messagebox.showerror("Input Error", "Vui lòng nhập ít nhất 1 Lot.")
        return

    # Tách theo ',', ';', khoảng trắng, newline
    tokens = [x.strip() for x in re.split(r"[,;\s]+", lots_raw) if x.strip()]
    lots = list(dict.fromkeys(tokens))
    if not lots:
        messagebox.showerror("Input Error", "Không tìm thấy Lot hợp lệ.")
        return

    progress_label.config(text="Processing (Query theo Lot)...")
    root.update_idletasks()

    try:
        conn = _connect_resolved_db()
    except Exception as e:
        progress_label.config(text="")
        messagebox.showerror("Database Error", f"Không thể kết nối database:{e}")
        return

    # Lấy danh sách cột động
    try:
        cols = get_table_columns(conn, "lot_traceback")
        if not cols:
            cols = ["internal2did_id", "Lot", "leadframe_id", "LF_POS"]
    except Exception:
        cols = ["internal2did_id", "Lot", "leadframe_id", "LF_POS"]

    # Hiển thị full cột
    set_tree_columns(cols)
    quoted_cols = ",".join([f"[{c}]" for c in cols])

    batch_size = 500
    global query_results
    query_results = []

    try:
        cur = conn.cursor()
        for i in range(0, len(lots), batch_size):
            batch = lots[i:i + batch_size]
            or_parts = ["[Lot] LIKE ? COLLATE NOCASE" for _ in batch]
            sql = f"SELECT {quoted_cols} FROM lot_traceback WHERE " + " OR ".join(or_parts)
            params = [f"%{x}%" for x in batch]
            cur.execute(sql, params)
            query_results.extend(cur.fetchall())
    except Exception as e:
        messagebox.showerror("Query Error", str(e))
    finally:
        conn.close()

    # Đổ dữ liệu ra bảng
    for row in tree.get_children():
        tree.delete(row)
    for result in query_results:
        tree.insert("", tk.END, values=result)

    progress_label.config(
        text=f"Query theo Lot xong. Số Lot nhập: {len(lots)} — Kết quả: {len(query_results)} dòng."
    )


def copy_to_clipboard():
    if not query_results:
        messagebox.showinfo("No Data", "Không có dữ liệu để copy.")
        return
    header = ",".join(current_columns)
    lines = [header]
    for row in query_results:
        lines.append(",".join("" if v is None else str(v) for v in row))
    text = "\n".join(lines)
    root.clipboard_clear()
    root.clipboard_append(text)
    root.update()
    messagebox.showinfo("Copied", "Đã copy kết quả vào clipboard.")


def export_to_csv():
    if not query_results:
        messagebox.showinfo("No Data", "Không có dữ liệu để xuất.")
        return
    df = pd.DataFrame(query_results, columns=current_columns)
    file_path = filedialog.asksaveasfilename(defaultextension=".csv",
                                             filetypes=[("CSV files", "*.csv")])
    if file_path:
        try:
            df.to_csv(file_path, index=False)
            messagebox.showinfo("Exported", f"Đã xuất kết quả ra {file_path}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))


def clear_all():
    # Xóa input ở cả ba tab
    try:
        text_input_tab1.delete("1.0", tk.END)
    except Exception:
        pass
    try:
        text_input_tab2.delete("1.0", tk.END)
    except Exception:
        pass
    try:
        text_input_tab3.delete("1.0", tk.END)  # Tab 3
    except Exception:
        pass

    # Xóa bảng
    for row in tree.get_children():
        tree.delete(row)

    global query_results
    query_results = []
    progress_label.config(text="")

    # Đặt lại cột mặc định cho bảng
    set_tree_columns(["internal2did_id", "Lot", "leadframe_id", "LF_POS"])


def load_from_csv_tab1():
    file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
    if file_path:
        try:
            df = pd.read_csv(file_path)
            if df.shape[1] >= 3:
                lines = ["Lot no,LF ID,LF Pos"]
                for _, row in df.iterrows():
                    lines.append(f"{row.iloc[0]},{row.iloc[1]},{row.iloc[2]}")
                text_input_tab1.delete("1.0", tk.END)
                text_input_tab1.insert(tk.END, "".join(lines))
            else:
                messagebox.showerror("CSV Error", "CSV phải có ít nhất 3 cột.")
        except Exception as e:
            messagebox.showerror("CSV Error", str(e))


def browse_db_file():
    chosen = filedialog.askopenfilename(
        title="Chọn file database",
        initialdir=str(APP_DIR),
        filetypes=[("SQLite DB", "*.sqlite *.db *.sqlite3"), ("All files", "*.*")]
    )
    if chosen:
        entry_db_path.delete(0, tk.END)
        entry_db_path.insert(0, chosen)


def browse_db_folder():
    chosen = filedialog.askdirectory(
        title="Chọn thư mục chứa database",
        initialdir=str(APP_DIR),
    )
    if chosen:
        entry_db_path.delete(0, tk.END)
        entry_db_path.insert(0, chosen)


# =========================
# GUI
# =========================
root = tk.Tk()
root.title("2DID Lot Traceback Query")
root.state('zoomed')  # Fullscreen


# Xác định giá trị DB path ban đầu (theo ưu tiên)

def initial_db_path():
    try:
        resolved = resolve_db_path("")  # rỗng → settings → app folder → default
        return resolved
    except Exception:
        return DEFAULT_DB_PATH


# Hàng 0: Database path
tk.Label(root, text="Database Path (file hoặc thư mục):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
entry_db_path = tk.Entry(root, width=100)
entry_db_path.insert(0, initial_db_path())
entry_db_path.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
btn_browse_file = tk.Button(root, text="Browse File…", command=browse_db_file)
btn_browse_file.grid(row=0, column=2, padx=5, pady=5)
btn_browse_folder = tk.Button(root, text="Browse Folder…", command=browse_db_folder)
btn_browse_folder.grid(row=0, column=3, padx=5, pady=5)

# Hàng 1-3: Notebook với 3 tab
notebook = ttk.Notebook(root)
tab1 = ttk.Frame(notebook)
tab2 = ttk.Frame(notebook)
tab3 = ttk.Frame(notebook)  # NEW

notebook.add(tab1, text="Tìm theo LF ID & LF POS")
notebook.add(tab2, text="Tìm theo internal2did_id")
notebook.add(tab3, text="Tìm theo Lot")  # NEW
notebook.grid(row=1, column=0, columnspan=4, sticky="nsew", padx=5, pady=(0, 5))

# --- Tab 1 ---
tk.Label(tab1, text="Nhập 3 cột (có thể có/không có header): Lot no, LF ID, LF Pos").grid(
    row=0, column=0, columnspan=3, padx=5, pady=5, sticky="w"
)
text_frame1 = tk.Frame(tab1)
text_frame1.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)
text_scroll_y1 = tk.Scrollbar(text_frame1, orient=tk.VERTICAL)
text_scroll_x1 = tk.Scrollbar(text_frame1, orient=tk.HORIZONTAL)
text_input_tab1 = tk.Text(text_frame1, height=12, wrap="none",
                          yscrollcommand=text_scroll_y1.set, xscrollcommand=text_scroll_x1.set)
text_scroll_y1.config(command=text_input_tab1.yview)
text_scroll_x1.config(command=text_input_tab1.xview)
text_scroll_y1.pack(side=tk.RIGHT, fill=tk.Y)
text_scroll_x1.pack(side=tk.BOTTOM, fill=tk.X)
text_input_tab1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
btn_frame1 = tk.Frame(tab1)
btn_frame1.grid(row=2, column=0, columnspan=3, pady=5, sticky="w")
tk.Button(btn_frame1, text="Query", command=query_database).pack(side=tk.LEFT, padx=5)

tk.Button(btn_frame1, text="Load from CSV", command=load_from_csv_tab1).pack(side=tk.LEFT, padx=5)

tab1.grid_rowconfigure(1, weight=1)
tab1.grid_columnconfigure(0, weight=1)

# --- Tab 2 ---
tk.Label(tab2, text="Nhập danh sách internal2did_id (mỗi ID 1 dòng hoặc ngăn cách bởi ',', ';' hay khoảng trắng):").grid(
    row=0, column=0, columnspan=3, padx=5, pady=5, sticky="w"
)
text_frame2 = tk.Frame(tab2)
text_frame2.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)
text_scroll_y2 = tk.Scrollbar(text_frame2, orient=tk.VERTICAL)
text_scroll_x2 = tk.Scrollbar(text_frame2, orient=tk.HORIZONTAL)
text_input_tab2 = tk.Text(text_frame2, height=12, wrap="none",
                          yscrollcommand=text_scroll_y2.set, xscrollcommand=text_scroll_x2.set)
text_scroll_y2.config(command=text_input_tab2.yview)
text_scroll_x2.config(command=text_input_tab2.xview)
text_scroll_y2.pack(side=tk.RIGHT, fill=tk.Y)
text_scroll_x2.pack(side=tk.BOTTOM, fill=tk.X)
text_input_tab2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
btn_frame2 = tk.Frame(tab2)
btn_frame2.grid(row=2, column=0, columnspan=3, pady=5, sticky="w")
tk.Button(btn_frame2, text="Reverse Query", command=reverse_query_database).pack(side=tk.LEFT, padx=5)

tab2.grid_rowconfigure(1, weight=1)
tab2.grid_columnconfigure(0, weight=1)

# --- Tab 3 (NEW) ---
tk.Label(tab3, text="Nhập danh sách Lot (mỗi Lot 1 dòng hoặc ngăn cách bởi ',', ';' hay khoảng trắng):").grid(
    row=0, column=0, columnspan=3, padx=5, pady=5, sticky="w"
)
text_frame3 = tk.Frame(tab3)
text_frame3.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)
text_scroll_y3 = tk.Scrollbar(text_frame3, orient=tk.VERTICAL)
text_scroll_x3 = tk.Scrollbar(text_frame3, orient=tk.HORIZONTAL)
text_input_tab3 = tk.Text(text_frame3, height=12, wrap="none",
                          yscrollcommand=text_scroll_y3.set, xscrollcommand=text_scroll_x3.set)
text_scroll_y3.config(command=text_input_tab3.yview)
text_scroll_x3.config(command=text_input_tab3.xview)
text_scroll_y3.pack(side=tk.RIGHT, fill=tk.Y)
text_scroll_x3.pack(side=tk.BOTTOM, fill=tk.X)
text_input_tab3.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
btn_frame3 = tk.Frame(tab3)
btn_frame3.grid(row=2, column=0, columnspan=3, pady=5, sticky="w")
tk.Button(btn_frame3, text="Query Lot", command=query_by_lot_database).pack(side=tk.LEFT, padx=5)

# Hàng 4: Chỉ Status (đã bỏ progress bar)
progress_label = tk.Label(root, text="", anchor="w")
progress_label.grid(row=2, column=0, columnspan=4, sticky="w", padx=5)

# Hàng 5: Result table with scrollbars
tree_frame = tk.Frame(root)
tree_frame.grid(row=3, column=0, columnspan=4, sticky="nsew", padx=5, pady=5)
tree_scroll_y = tk.Scrollbar(tree_frame, orient=tk.VERTICAL)
tree_scroll_x = tk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
columns = tuple(current_columns)
tree = ttk.Treeview(
    tree_frame, columns=columns, show="headings",
    yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set
)
for col in columns:
    tree.heading(col, text=col)
    tree.column(col, width=150)
tree_scroll_y.config(command=tree.yview)
tree_scroll_x.config(command=tree.xview)
tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Hàng 6: Hàng nút chung (Copy/Export/Clear)
button_frame_common = tk.Frame(root)
button_frame_common.grid(row=4, column=0, columnspan=4, pady=(0, 10), sticky="w")
tk.Button(button_frame_common, text="Copy to Clipboard", command=copy_to_clipboard).pack(side=tk.LEFT, padx=5)
tk.Button(button_frame_common, text="Export to CSV", command=export_to_csv).pack(side=tk.LEFT, padx=5)
tk.Button(button_frame_common, text="Clear All", command=clear_all).pack(side=tk.LEFT, padx=5)

# Layout expansion
root.grid_rowconfigure(1, weight=1)  # notebook
root.grid_rowconfigure(3, weight=1)  # tree
root.grid_columnconfigure(1, weight=1)
root.grid_columnconfigure(2, weight=0)
root.grid_columnconfigure(3, weight=0)

root.mainloop()
