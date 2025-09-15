import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import csv
from io import StringIO
import os
import json
import glob
from pathlib import Path

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
    Nhận vào: đường dẫn người dùng nhập (có thể là file hoặc folder),
    hoặc chuỗi rỗng.
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

    # Nếu người dùng có nhập gì đó
    p = Path(os.path.expandvars(value))
    if p.is_file():
        return str(p)

    if p.is_dir():
        cands = list_db_files_in_dir(p)
        if len(cands) == 0:
            raise FileNotFoundError(f"Không tìm thấy file database (*.sqlite, *.db, *.sqlite3) trong thư mục:\n{p}")
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

    # Nếu không phải file cũng không phải folder → có thể người dùng nhập sai
    # Thử xem nó là relative path tính từ thư mục app
    p2 = (APP_DIR / value)
    if p2.is_file():
        return str(p2)
    if p2.is_dir():
        cands = list_db_files_in_dir(p2)
        if len(cands) == 0:
            raise FileNotFoundError(f"Không tìm thấy file database trong thư mục:\n{p2}")
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
    - Delimiter: ',', ';', hoặc '\t'
    - Lấy 3 cột đầu: (Lot no, LF ID, LF Pos). Query dùng (LF ID, LF Pos).
    - Bỏ qua dòng đầu nếu cột 3 không phải số (coi là header).
    - Khử trùng lặp các cặp (LF_ID, LF_POS).
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("Vui lòng nhập dữ liệu (3 cột: Lot no, LF ID, LF Pos).")

    normalized = raw_text.replace("\t", ",").replace(";", ",")
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
        raise ValueError("Không có dòng dữ liệu hợp lệ để truy vấn.\n" + ("\n".join(errors) if errors else ""))

    pairs = list(dict.fromkeys(pairs))  # khử trùng lặp, giữ thứ tự
    return pairs, errors

# =========================
# LOGIC TRUY VẤN
# =========================
query_results = []

def query_database():
    raw_text = text_input.get("1.0", tk.END)
    user_input_path = entry_db_path.get()

    progress_label.config(text="Processing...")
    progress_bar.start()
    root.update_idletasks()

    try:
        pairs, parse_warnings = parse_input_text(raw_text)
    except Exception as e:
        progress_bar.stop()
        progress_label.config(text="")
        messagebox.showerror("Input Error", str(e))
        return

    try:
        resolved_db = resolve_db_path(user_input_path)
    except Exception as e:
        progress_bar.stop()
        progress_label.config(text="")
        messagebox.showerror("Database Path", str(e))
        return

    try:
        conn = sqlite3.connect(resolved_db)
        cursor = conn.cursor()
    except Exception as e:
        progress_bar.stop()
        progress_label.config(text="")
        messagebox.showerror("Database Error", f"Không thể kết nối database:\n{e}\n\nĐường dẫn: {resolved_db}")
        return

    # Lưu lại DB path sau cùng (chỉ khi kết nối thành công)
    settings = load_settings()
    settings["last_db_path"] = resolved_db
    save_settings(settings)
    entry_db_path.delete(0, tk.END)
    entry_db_path.insert(0, resolved_db)

    global query_results
    query_results = []

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
    for row in tree.get_children():
        tree.delete(row)
    for result in query_results:
        tree.insert("", tk.END, values=result)

    progress_bar.stop()
    status = f"Done!. Input: {len(pairs)} Data. *-----* Kết quả: {len(query_results)} Data"
    if parse_warnings:
        status += f"  | Cảnh báo: {len(parse_warnings)} dòng bị bỏ qua."
    progress_label.config(text=status)

import re

def copy_to_clipboard():
    if not query_results:
        messagebox.showinfo("No Data", "Không có dữ liệu để copy.")
        return
    header = "internal2did_id,Lot,leadframe_id,LF_POS"
    text = "\n".join([header] + [",".join(map(str, row)) for row in query_results])
    root.clipboard_clear()
    root.clipboard_append(text)
    root.update()
    messagebox.showinfo("Copied", "Đã copy kết quả vào clipboard.")


def export_to_csv():
    if not query_results:
        messagebox.showinfo("No Data", "Không có dữ liệu để xuất.")
        return
    df = pd.DataFrame(query_results, columns=["internal2did_id", "Lot", "leadframe_id", "LF_POS"])
    file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
    if file_path:
        try:
            df.to_csv(file_path, index=False)
            messagebox.showinfo("Exported", f"Đã xuất kết quả ra {file_path}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

def clear_all():
    text_input.delete("1.0", tk.END)
    for row in tree.get_children():
        tree.delete(row)
    global query_results
    query_results = []
    progress_label.config(text="")
    try:
        progress_bar.stop()
    except:
        pass

def load_from_csv():
    file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
    if file_path:
        try:
            df = pd.read_csv(file_path)
            if df.shape[1] >= 3:
                lines = ["Lot no,LF ID,LF Pos"]
                for _, row in df.iterrows():
                    lines.append(f"{row.iloc[0]},{row.iloc[1]},{row.iloc[2]}")
                text_input.delete("1.0", tk.END)
                text_input.insert(tk.END, "\n".join(lines))
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

# Database path input
tk.Label(root, text="Database Path (file hoặc thư mục):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
entry_db_path = tk.Entry(root, width=100)
entry_db_path.insert(0, initial_db_path())
entry_db_path.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
btn_browse_file = tk.Button(root, text="Browse File…", command=browse_db_file)
btn_browse_file.grid(row=0, column=2, padx=5, pady=5)
btn_browse_folder = tk.Button(root, text="Browse Folder…", command=browse_db_folder)
btn_browse_folder.grid(row=0, column=3, padx=5, pady=5)

# Data input label
tk.Label(root, text="Nhập 3 cột (có thể có/không có header): Lot no, LF ID, LF Pos").grid(row=1, column=0, columnspan=4, padx=5, pady=5, sticky="w")

# Data input with scrollbars
text_frame = tk.Frame(root)
text_frame.grid(row=2, column=0, columnspan=4, sticky="nsew", padx=5, pady=5)
text_scroll_y = tk.Scrollbar(text_frame, orient=tk.VERTICAL)
text_scroll_x = tk.Scrollbar(text_frame, orient=tk.HORIZONTAL)
text_input = tk.Text(text_frame, height=15, wrap="none", yscrollcommand=text_scroll_y.set, xscrollcommand=text_scroll_x.set)
text_scroll_y.config(command=text_input.yview)
text_scroll_x.config(command=text_input.xview)
text_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
text_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
text_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Button frame
button_frame = tk.Frame(root)
button_frame.grid(row=3, column=0, columnspan=4, pady=5)

btn_query = tk.Button(button_frame, text="Query", command=query_database)
btn_query.pack(side=tk.LEFT, padx=5)

btn_copy = tk.Button(button_frame, text="Copy to Clipboard", command=copy_to_clipboard)
btn_copy.pack(side=tk.LEFT, padx=5)

btn_export = tk.Button(button_frame, text="Export to CSV", command=export_to_csv)
btn_export.pack(side=tk.LEFT, padx=5)

btn_clear_all = tk.Button(button_frame, text="Clear All", command=clear_all)
btn_clear_all.pack(side=tk.LEFT, padx=5)

btn_load_csv = tk.Button(button_frame, text="Load from CSV", command=load_from_csv)
btn_load_csv.pack(side=tk.LEFT, padx=5)

# Progress bar and status
progress_label = tk.Label(root, text="", anchor="w")
progress_label.grid(row=4, column=0, sticky="w", padx=5)
progress_bar = ttk.Progressbar(root, mode="indeterminate")
progress_bar.grid(row=4, column=1, columnspan=3, sticky="ew", padx=5)

# Result table with scrollbars
tree_frame = tk.Frame(root)
tree_frame.grid(row=5, column=0, columnspan=4, sticky="nsew", padx=5, pady=5)
tree_scroll_y = tk.Scrollbar(tree_frame, orient=tk.VERTICAL)
tree_scroll_x = tk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
columns = ("internal2did_id", "Lot", "leadframe_id", "LF_POS")
tree = ttk.Treeview(tree_frame, columns=columns, show="headings", yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)
for col in columns:
    tree.heading(col, text=col)
    tree.column(col, width=150)
tree_scroll_y.config(command=tree.yview)
tree_scroll_x.config(command=tree.xview)
tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Layout expansion
root.grid_rowconfigure(2, weight=1)
root.grid_rowconfigure(5, weight=1)
root.grid_columnconfigure(1, weight=1)
root.grid_columnconfigure(2, weight=0)
root.grid_columnconfigure(3, weight=0)

root.mainloop()
