import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import requests
from bs4 import BeautifulSoup
import urllib3
import threading
import time
import re
import csv
import os
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# -------------------- App Setup --------------------
app = tk.Tk()
app.title("Author Filter Forum Scraper")
app.geometry("1120x780")

# State
scanned_posts = set()
scanned_lock = threading.Lock()
session = requests.Session()
refresh_after_id = None  # for app.after cancel
last_inputs = {"url": None, "author": None}
stop_event = threading.Event()  # to stop background work gracefully
scrape_in_progress = False
scrape_lock = threading.Lock()

# Requests session with retries
retry = Retry(
    total=3, connect=3, read=3, backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "HEAD", "OPTIONS"]
)
adapter = HTTPAdapter(max_retries=retry)
session.mount("http://", adapter)
session.mount("https://", adapter)
session.headers.update({"User-Agent": "Mozilla/5.0 (ScraperApp; +https://example.local)"})


# -------------------- UI --------------------
tk.Label(app, text="Forum URL:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
url_entry = ttk.Entry(app, width=90)
url_entry.grid(row=0, column=1, columnspan=7, padx=5, pady=5, sticky="we")

tk.Label(app, text="Author:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
author_entry = ttk.Entry(app, width=24)
author_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")

tk.Label(app, text="From Page:").grid(row=1, column=2, padx=5, pady=5, sticky="w")
from_page_entry = ttk.Entry(app, width=7)
from_page_entry.grid(row=1, column=3, padx=5, pady=5, sticky="w")

tk.Label(app, text="To Page (blank = latest):").grid(row=1, column=4, padx=5, pady=5, sticky="w")
to_page_entry = ttk.Entry(app, width=7)
to_page_entry.grid(row=1, column=5, padx=5, pady=5, sticky="w")

tk.Label(app, text="Refresh Interval (sec):").grid(row=1, column=6, padx=5, pady=5, sticky="e")
interval_entry = ttk.Entry(app, width=10)
interval_entry.insert(0, "60")
interval_entry.grid(row=1, column=7, padx=5, pady=5, sticky="w")

# Export controls
export_var = tk.BooleanVar(value=False)
export_check = ttk.Checkbutton(app, text="Export to CSV", variable=export_var)
export_check.grid(row=2, column=0, padx=5, pady=5, sticky="w")

csv_path_entry = ttk.Entry(app, width=70)
csv_path_entry.grid(row=2, column=1, columnspan=5, padx=5, pady=5, sticky="we")

def browse_csv():
    path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )
    if path:
        csv_path_entry.delete(0, "end")
        csv_path_entry.insert(0, path)

browse_btn = ttk.Button(app, text="Browse…", command=browse_csv)
browse_btn.grid(row=2, column=6, padx=5, pady=5, sticky="w")

# Buttons
def start_scan_clicked():
    output_text.delete("1.0", "end")
    start_scrape_background()

start_button = ttk.Button(app, text="Start Scan (Once)", command=start_scan_clicked)
start_button.grid(row=2, column=7, padx=5, pady=5, sticky="e")

auto_start_button = ttk.Button(app, text="Start Auto-Refresh")
auto_start_button.grid(row=3, column=6, padx=5, pady=5, sticky="e")
auto_stop_button = ttk.Button(app, text="Stop Auto-Refresh")
auto_stop_button.grid(row=3, column=7, padx=5, pady=5, sticky="w")

# Output
output_text = scrolledtext.ScrolledText(app, wrap="word", font=("Consolas", 10))
output_text.grid(row=4, column=0, columnspan=8, padx=10, pady=10, sticky="nsew")

# Progress
progress_var = tk.IntVar(value=0)
progress_bar = ttk.Progressbar(app, orient="horizontal", mode="determinate", variable=progress_var, length=400)
progress_bar.grid(row=5, column=0, columnspan=3, padx=10, pady=6, sticky="w")

progress_label_var = tk.StringVar(value="Progress: 0/0")
progress_label = ttk.Label(app, textvariable=progress_label_var)
progress_label.grid(row=5, column=3, columnspan=2, padx=5, pady=6, sticky="w")

status_var = tk.StringVar(value="Ready.")
status_label = ttk.Label(app, textvariable=status_var)
status_label.grid(row=5, column=5, columnspan=3, padx=8, pady=6, sticky="e")

# Resizing
app.rowconfigure(4, weight=1)
for c in range(8):
    app.columnconfigure(c, weight=1)


# -------------------- Helpers --------------------
PAGE_SUFFIX_RE = re.compile(r"/page-\d+/?$")

def normalize_base_url(url: str) -> str:
    url = url.strip()
    url = url.rstrip("/")
    url = PAGE_SUFFIX_RE.sub("", url)
    return url

def parse_int(entry_widget, default, minimum=None):
    try:
        val = int(entry_widget.get().strip())
        if minimum is not None and val < minimum:
            return minimum
        return val
    except Exception:
        return default

def get_latest_page(base_url: str) -> int:
    try:
        resp = session.get(base_url, timeout=(5, 20), verify=False)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        # Try common nav patterns first
        nav = soup.find("div", class_="PageNav")
        if nav and nav.get("data-last"):
            return int(nav["data-last"])
        # Fallback: largest numeric link on the page
        nums = []
        for a in soup.select("a"):
            txt = (a.get_text() or "").strip()
            if txt.isdigit():
                nums.append(int(txt))
        if nums:
            return max(nums)
    except Exception:
        pass
    return 1

def append_output(text: str):
    output_text.insert("end", text)
    output_text.see("end")

def set_status(msg: str):
    status_var.set(msg)
    app.update_idletasks()

def reset_progress(total_pages: int):
    progress_bar["maximum"] = max(total_pages, 1)
    progress_var.set(0)
    progress_label_var.set(f"Progress: 0/{total_pages}")

def update_progress(done_pages: int, total_pages: int):
    progress_var.set(done_pages)
    progress_label_var.set(f"Progress: {done_pages}/{total_pages}")

def ensure_csv_header(csv_path: str):
    header = ["run_time", "base_url", "page", "page_url", "post_id", "author", "content"]
    need_header = not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0
    if need_header:
        with open(csv_path, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(header)


# -------------------- Scraping --------------------
def scrape_once(base_url: str, author_filter: str, from_page: int, to_page: int,
                export_to_csv: bool, csv_path: str) -> str:
    """
    Runs in a background thread. Returns a string to be appended to the UI.
    Also appends to CSV if enabled.
    """
    results = []
    author_filter_norm = author_filter.strip().lower()
    total_pages = max(0, to_page - from_page + 1)
    run_time_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    csv_writer = None
    csv_file = None
    if export_to_csv and csv_path:
        ensure_csv_header(csv_path)
        csv_file = open(csv_path, "a", newline="", encoding="utf-8-sig")
        csv_writer = csv.writer(csv_file)

    pages_done = 0

    try:
        for page in range(from_page, to_page + 1):
            if stop_event.is_set():
                break

            page_url = f"{base_url}/page-{page}"
            results.append(f"\n{'-'*90}\nPage {page}: {page_url}\n")

            try:
                resp = session.get(page_url, timeout=(5, 20), verify=False)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.content, "html.parser")

                # Post containers (include a few fallbacks):
                # - li.message (XenForo 1 pattern)
                # - article.message (XenForo 2 pattern)
                # - li[id^=post-] (another common pattern)
                messages = soup.select("li.message, article.message, li[id^=post-]")

                for message in messages:
                    post_id = message.get("id") or ""
                    if not post_id:
                        continue
                    with scanned_lock:
                        if post_id in scanned_posts:
                            continue

                    # Prefer data-author; fallback to user name link if needed
                    author = (message.get("data-author") or "").strip()
                    if not author:
                        a_user = message.select_one(".author a, a.username")
                        if a_user and a_user.get_text():
                            author = a_user.get_text(strip=True)

                    # Case-insensitive author match
                    if author_filter_norm and author.lower() != author_filter_norm:
                        continue

                    # Content block fallbacks for f319-like forums
                    content_block = (
                        message.select_one("blockquote.messageText.ugc.baseHtml")
                        or message.select_one("blockquote.messageText")
                        or message.select_one("div.messageContent .messageText")
                        or message.select_one("div.bbWrapper")  # XenForo 2 content
                    )
                    if not content_block:
                        continue

                    content = content_block.get_text(separator="\n", strip=True)
                    results.append(f"\nAuthor: {author}\n{content}\n")

                    with scanned_lock:
                        scanned_posts.add(post_id)

                    if csv_writer:
                        csv_writer.writerow([run_time_iso, base_url, page, page_url, post_id, author, content])

            except requests.HTTPError as e:
                results.append(f"HTTP error on page {page}: {e}\n")
            except requests.RequestException as e:
                results.append(f"Network error on page {page}: {e}\n")
            except Exception as e:
                results.append(f"Unexpected error on page {page}: {e}\n")

            pages_done += 1
            app.after(0, lambda d=pages_done, t=total_pages: update_progress(d, t))
            time.sleep(0.25)  # Be polite to the server
    finally:
        if csv_file:
            csv_file.close()

    return "".join(results)

def start_scrape_background():
    global scrape_in_progress  # <-- IMPORTANT (fix UnboundLocalError)
    with scrape_lock:
        if scrape_in_progress:
            messagebox.showinfo("Info", "A scrape is already running. Please wait for it to finish.")
            return
        scrape_in_progress = True

    try:
        base_url_raw = url_entry.get().strip()
        if not base_url_raw:
            messagebox.showerror("Input error", "Please enter a Forum URL.")
            with scrape_lock:
                scrape_in_progress = False
            return
        base_url = normalize_base_url(base_url_raw)

        author = author_entry.get().strip()
        from_page = parse_int(from_page_entry, default=1, minimum=1)

        to_page_str = to_page_entry.get().strip()
        if to_page_str == "":
            to_page = get_latest_page(base_url)
        else:
            to_page = max(parse_int(to_page_entry, default=from_page, minimum=from_page), from_page)

        # Reset scanned_posts if URL or author changed
        if last_inputs["url"] != base_url or last_inputs["author"] != author:
            with scanned_lock:
                scanned_posts.clear()
            last_inputs["url"] = base_url
            last_inputs["author"] = author

        # Export settings
        export_to_csv = export_var.get()
        csv_path = csv_path_entry.get().strip()
        if export_to_csv and not csv_path:
            path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if not path:
                export_to_csv = False
            else:
                csv_path = path
                csv_path_entry.delete(0, "end")
                csv_path_entry.insert(0, path)

        total_pages = max(0, to_page - from_page + 1)
        reset_progress(total_pages)
        set_status("Scraping...")
        stop_event.clear()
        start_time = time.time()

        def worker():
            global scrape_in_progress  # <-- IMPORTANT (fix SyntaxError + correct scope)
            try:
                result_text = scrape_once(base_url, author, from_page, to_page, export_to_csv, csv_path)
                app.after(0, lambda: append_output(result_text))
            finally:
                elapsed = time.time() - start_time
                ts = datetime.now().strftime("%H:%M:%S")
                app.after(0, lambda: set_status(f"Done at {ts}. Took {elapsed:.1f}s"))
                with scrape_lock:
                    scrape_in_progress = False

        threading.Thread(target=worker, daemon=True).start()

    except Exception as e:
        with scrape_lock:
            scrape_in_progress = False
        messagebox.showerror("Error", f"Failed to start scraping: {e}")


# -------------------- Auto Refresh --------------------
def schedule_auto_refresh():
    global refresh_after_id
    interval = parse_int(interval_entry, default=60, minimum=5)
    refresh_after_id = app.after(interval * 1000, auto_refresh_tick)

def auto_refresh_tick():
    with scrape_lock:
        busy = scrape_in_progress
    if not busy:
        start_scrape_background()
    schedule_auto_refresh()

def start_auto():
    global refresh_after_id
    if refresh_after_id is not None:
        set_status("Auto-refresh already running.")
        return
    set_status("Auto-refresh started.")
    schedule_auto_refresh()

def stop_auto():
    global refresh_after_id
    stop_event.set()
    if refresh_after_id is not None:
        app.after_cancel(refresh_after_id)
        refresh_after_id = None
    set_status("Auto-refresh stopped.")

auto_start_button.configure(command=start_auto)
auto_stop_button.configure(command=stop_auto)

# -------------------- Mainloop --------------------
app.mainloop()
