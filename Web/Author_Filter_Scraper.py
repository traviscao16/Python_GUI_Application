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
import json
from pathlib import Path
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

def add_url_to_history(*args):
    url = url_combo.get().strip()
    if url:
        values = list(url_combo["values"])
        # Only add if URL isn't already in the list
        if url not in values:
            values.append(url)
            url_combo["values"] = values
            save_history()

url_combo = ttk.Combobox(app, width=90)
url_combo.grid(row=0, column=1, columnspan=7, padx=5, pady=5, sticky="we")

# Bind events to save URL
url_combo.bind("<Return>", add_url_to_history)  # When user presses Enter
url_combo.bind("<<ComboboxSelected>>", add_url_to_history)  # When user selects from dropdown

# Author frame with list and controls
author_frame = ttk.Frame(app)
author_frame.grid(row=1, column=1, padx=5, pady=5, sticky="w")

# Author list with checkboxes
author_tree = ttk.Treeview(author_frame, columns=("author",), show="tree", height=6)
author_tree.column("#0", width=30)  # Checkbox column
author_tree.column("author", width=200)
author_tree.grid(row=0, column=0, columnspan=2)

# Scrollbar for author list
author_scroll = ttk.Scrollbar(author_frame, orient="vertical", command=author_tree.yview)
author_scroll.grid(row=0, column=2, sticky="ns")
author_tree.configure(yscrollcommand=author_scroll.set)

# Author input and add button
author_entry = ttk.Entry(author_frame, width=24)
author_entry.grid(row=1, column=0, pady=2)

def add_author():
    author = author_entry.get().strip()
    if author:
        author_tree.insert("", "end", text="", values=(author,))
        author_entry.delete(0, "end")
        save_history()

def toggle_check(event):
    item = author_tree.identify_row(event.y)
    if item:
        if author_tree.item(item, "text") == "✓":
            author_tree.item(item, text="")
        else:
            author_tree.item(item, text="✓")

add_button = ttk.Button(author_frame, text="Add", command=add_author)
add_button.grid(row=1, column=1, pady=2)

# Bind checkbox toggle
author_tree.bind("<Button-1>", toggle_check)

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

# Remember posts option
remember_posts_var = tk.BooleanVar(value=True)
remember_posts_check = ttk.Checkbutton(
    app, 
    text="Skip previously seen posts", 
    variable=remember_posts_var
)
remember_posts_check.grid(row=3, column=4, padx=5, pady=5, sticky="w")

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

def get_history_file():
    app_dir = Path.home() / ".forum_scraper"
    app_dir.mkdir(exist_ok=True)
    return app_dir / "history.json"

def load_history():
    try:
        history_file = get_history_file()
        if history_file.exists():
            with open(history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("urls", []), data.get("authors", [])
    except Exception as e:
        print(f"Error loading history: {e}")
    return [], []

def save_history():
    try:
        urls = list(url_combo["values"])
        authors = []
        for item in author_tree.get_children():
            author = author_tree.item(item, "values")[0]
            authors.append(author)
        
        history_file = get_history_file()
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump({
                "urls": urls,
                "authors": authors
            }, f, indent=2)
    except Exception as e:
        print(f"Error saving history: {e}")

# -------------------- Scraping --------------------
def scrape_once(base_url: str, author_filter: str, from_page: int, to_page: int) -> str:
    """
    Runs in a background thread. Returns a string to be appended to the UI.
    """
    results = []
    author_filter_norm = author_filter.strip().lower()
    total_pages = max(0, to_page - from_page + 1)
    run_time_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    pages_done = 0

    try:
        # Get selected authors
        selected_authors = set()
        for item in author_tree.get_children():
            if author_tree.item(item, "text") == "✓":  # If checked
                selected_authors.add(author_tree.item(item, "values")[0].lower())

        for page in range(from_page, to_page + 1):
            if stop_event.is_set():
                break

            page_url = f"{base_url}/page-{page}"
            results.append(f"\n{'-'*90}\nPage {page}\n")

            try:
                resp = session.get(page_url, timeout=(5, 20), verify=False)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.content, "html.parser")

                # Post containers (include a few fallbacks):
                # - li.message (XenForo 1 pattern)
                # - article.message (XenForo 2 pattern)
                # - li[id^=post-] (another common pattern)
                #messages = soup.select("li.message, article.message, li[id^=post-]")
                messages = soup.select("li[id^=post-][data-author]")

                for message in messages:
                    post_id = message.get("id") or ""
                    if not post_id:
                        continue
                    with scanned_lock:
                        if remember_posts_var.get() and post_id in scanned_posts:
                            continue

                    # Extract date
                    date_elem = message.select_one(".datePermalink")
                    post_date = date_elem.get_text(strip=True) if date_elem else "Unknown date"

                    # Prefer data-author; fallback to user name link if needed
                    author = message.get("data-author").strip()
                    if not author:
                        a_user = message.select_one(".author a, a.username")
                        if a_user and a_user.get_text():
                            author = a_user.get_text(strip=True)

                    # Case-insensitive author match
                    if selected_authors and author.lower() not in selected_authors:
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
                    results.append(f"\nAuthor: {author}\nDate: {post_date}\n{content}\n")

                    with scanned_lock:
                        scanned_posts.add(post_id)

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
        pass  # No CSV file to close

    return "".join(results)

def start_scrape_background():
    global scrape_in_progress  # <-- IMPORTANT (fix UnboundLocalError)
    with scrape_lock:
        if scrape_in_progress:
            messagebox.showinfo("Info", "A scrape is already running. Please wait for it to finish.")
            return
        scrape_in_progress = True

    try:
        base_url_raw = url_combo.get().strip()
        if not base_url_raw:
            messagebox.showerror("Input error", "Please enter a Forum URL.")
            with scrape_lock:
                scrape_in_progress = False
            return
        base_url = normalize_base_url(base_url_raw)

        # Get selected authors instead of single author
        selected_authors = []
        for item in author_tree.get_children():
            if author_tree.item(item, "text") == "✓":
                selected_authors.append(author_tree.item(item, "values")[0])
        
        if not selected_authors:
            messagebox.showwarning("Warning", "No authors selected")
            with scrape_lock:
                scrape_in_progress = False
            return

        author = ",".join(selected_authors)  # Join for cache key
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
        export_to_csv = False  # Disabled export by default
        csv_path = ""  # No default path
        total_pages = max(0, to_page - from_page + 1)
        reset_progress(total_pages)
        set_status("Scraping...")
        stop_event.clear()
        start_time = time.time()

        def worker():
            global scrape_in_progress  # <-- IMPORTANT (fix SyntaxError + correct scope)
            try:
                result_text = scrape_once(base_url, author, from_page, to_page)
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

# -------------------- Save to CSV --------------------
def save_to_csv():
    # Get current content from output_text
    content = output_text.get("1.0", "end").strip()
    if not content:
        messagebox.showinfo("Info", "No content to save")
        return
        
    # Ask for save location
    file_path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )
    if not file_path:
        return
        
    try:
        with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            # Write header
            writer.writerow(["run_time", "author", "post_date", "content"])
            
            # Parse and write content
            current_author = ""
            current_date = ""
            current_content = []
            
            for line in content.split("\n"):
                if line.startswith("Author: "):
                    # Write previous entry if exists
                    if current_author and current_content:
                        writer.writerow([
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            current_author,
                            current_date,
                            "\n".join(current_content)
                        ])
                    # Start new entry
                    current_author = line.replace("Author: ", "").strip()
                    current_content = []
                elif line.startswith("Date: "):
                    current_date = line.replace("Date: ", "").strip()
                elif line and not line.startswith("-" * 90):
                    current_content.append(line)
            
            # Write final entry
            if current_author and current_content:
                writer.writerow([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    current_author,
                    current_date,
                    "\n".join(current_content)
                ])
                
        set_status(f"Saved to CSV: {file_path}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save CSV: {e}")

save_csv_btn = ttk.Button(app, text="Save to CSV", command=save_to_csv)
save_csv_btn.grid(row=2, column=5, padx=5, pady=5, sticky="e")

# Load saved history
saved_urls, saved_authors = load_history()
if saved_urls:
    url_combo["values"] = saved_urls
    url_combo.set(saved_urls[0])  # Set the most recently added URL
    
for author in saved_authors:
    author_tree.insert("", "end", text="", values=(author,))

# Remove selected authors
def remove_selected_authors():
    selected = author_tree.selection()
    for item in selected:
        author_tree.delete(item)
    save_history()

remove_button = ttk.Button(author_frame, text="Remove", command=remove_selected_authors)
remove_button.grid(row=1, column=2, pady=2)

# Start main loop
app.mainloop()
