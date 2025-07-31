
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import filedialog, Toplevel, messagebox, Listbox
import requests
from bs4 import BeautifulSoup
import urllib3
import json
import os
import sys


# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# Set working directory to the script's folder
script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
os.chdir(script_dir)


# Config paths
CONFIG_DIR = "config"
BOOKMARK_FILE = os.path.join(CONFIG_DIR, "bookmarks.json")
SESSION_FILE = os.path.join(CONFIG_DIR, "last_session.json")
os.makedirs(CONFIG_DIR, exist_ok=True)

# Page tracking
current_page = 1
latest_page = 1
last_known_post_ids = set()

def load_last_session():
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                url_entry.insert(0, data.get("url", ""))
                page_entry.insert(0, str(data.get("page", 1)))
            except Exception:
                pass

def save_last_session(url, page):
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump({"url": url, "page": page}, f)

def get_latest_page(base_url):
    try:
        response = requests.get(base_url, headers={"User-Agent": "Mozilla/5.0"}, verify=False)
        soup = BeautifulSoup(response.content, "html.parser")
        nav = soup.find("div", class_="PageNav")
        if nav and nav.get("data-last"):
            return int(nav["data-last"])
    except Exception:
        pass
    return 1

def get_post_ids_from_page(url):
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, verify=False)
        soup = BeautifulSoup(response.content, "html.parser")
        post_ids = set()
        for message in soup.find_all("li", class_="message"):
            post_id = message.get("id")
            if post_id:
                post_ids.add(post_id)
        return post_ids
    except Exception:
        return set()

def scrape_page(page):
    global current_page, latest_page, last_known_post_ids
    base_url = url_entry.get().strip().rstrip("/")
    if not base_url or "f319.com" not in base_url:
        messagebox.showerror("Invalid URL", "Please enter a valid F319 thread URL.")
        return

    latest_page = get_latest_page(base_url)
    current_page = max(1, min(page, latest_page))
    page_entry.delete(0, "end")
    page_entry.insert(0, str(current_page))
    page_label.config(text=f"Current Page: {current_page} / Latest Page: {latest_page}")
    noti_label.config(text="")
    post_noti_label.config(text="")
    save_last_session(base_url, current_page)

    page_url = f"{base_url}/page-{current_page}"
    output_text.delete("1.0", "end")
    all_results = []

    try:
        response = requests.get(page_url, headers={"User-Agent": "Mozilla/5.0"}, verify=False)
        soup = BeautifulSoup(response.content, "html.parser")

        for message in soup.find_all("li", class_="message"):
            author = message.get("data-author", "").strip()
            time_tag = message.find("a", class_="datePermalink")
            post_time = time_tag.get_text(strip=True) if time_tag else ""

            quote_author = ""
            quote_content = ""
            quote_block = message.find("div", class_="bbCodeBlock bbCodeQuote")
            if quote_block:
                quote_author = quote_block.get("data-author", "").strip()
                quote_container = quote_block.find("blockquote", class_="quoteContainer")
                if quote_container:
                    quote_div = quote_container.find("div", class_="quote")
                    if quote_div:
                        quote_content = quote_div.get_text(separator="\n", strip=True)

            content_block = message.find("blockquote", class_="messageText ugc baseHtml")
            main_content = ""
            if content_block:
                aside = content_block.find("aside")
                if aside:
                    aside.extract()
                main_content = content_block.get_text(separator="\n", strip=True)

            formatted = f"👤 Author: {author}\n🕒 Time: {post_time}"
            if quote_author:
                formatted += f"\n💬 Quote from {quote_author}:\n{quote_content}"
            formatted += f"\n\n📝---> Message<---:\n{main_content}\n{'-'*80}\n"
            all_results.append(formatted)

    except Exception as e:
        all_results.append(f"Error loading page {current_page}: {e}\n")

    output_text.insert("end", "\n".join(all_results))
    last_known_post_ids = get_post_ids_from_page(page_url)

def refresh(event=None):
    scrape_page(current_page)

def go_previous():
    scrape_page(current_page - 1)

def go_next():
    scrape_page(current_page + 1)

def go_latest():
    scrape_page(get_latest_page(url_entry.get().strip().rstrip("/")))

def go_to_page():
    try:
        page = int(page_entry.get().strip())
        scrape_page(page)
    except ValueError:
        messagebox.showerror("Invalid Input", "Please enter a valid page number.")

def save_to_file():
    content = output_text.get("1.0", "end").strip()
    if not content:
        messagebox.showinfo("No Content", "There is no content to save.")
        return

    file_path = filedialog.asksaveasfilename(defaultextension=".txt",
                                             filetypes=[("Text Files", "*.txt")])
    if file_path:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        messagebox.showinfo("Saved", f"Content saved to {file_path}")

def check_for_updates():
    global latest_page, last_known_post_ids
    base_url = url_entry.get().strip().rstrip("/")
    if not base_url or "f319.com" not in base_url:
        app.after(60000, check_for_updates)
        return

    new_latest = get_latest_page(base_url)
    if new_latest > latest_page:
        noti_label.config(text="🟢 New page available!")
        page_label.config(text=f"Current Page: {current_page} / Latest Page: {new_latest}")
    else:
        noti_label.config(text="")

    current_url = f"{base_url}/page-{current_page}"
    current_post_ids = get_post_ids_from_page(current_url)
    if current_post_ids - last_known_post_ids:
        post_noti_label.config(text="🟢 New post available!")
    else:
        post_noti_label.config(text="")

    app.after(60000, check_for_updates)

def add_bookmark():
    url = url_entry.get().strip()
    if not url:
        messagebox.showerror("Missing URL", "Please enter a URL to bookmark.")
        return

    def save_bookmark():
        label = label_entry.get().strip()
        if not label:
            messagebox.showerror("Missing Label", "Please enter a label for the bookmark.")
            return
        bookmarks = []
        if os.path.exists(BOOKMARK_FILE):
            with open(BOOKMARK_FILE, "r", encoding="utf-8") as f:
                bookmarks = json.load(f)
        bookmarks.append({"label": label, "url": url})
        with open(BOOKMARK_FILE, "w", encoding="utf-8") as f:
            json.dump(bookmarks, f, indent=2)
        bookmark_win.destroy()
        messagebox.showinfo("Bookmarked", f"Bookmark '{label}' saved.")

    bookmark_win = Toplevel(app)
    bookmark_win.title("Add Bookmark")
    ttk.Label(bookmark_win, text="Label:").pack(padx=10, pady=5)
    label_entry = ttk.Entry(bookmark_win, width=40)
    label_entry.pack(padx=10, pady=5)
    ttk.Button(bookmark_win, text="Save", command=save_bookmark, bootstyle=SUCCESS).pack(pady=10)

def show_bookmarks():
    if not os.path.exists(BOOKMARK_FILE):
        messagebox.showinfo("No Bookmarks", "No bookmarks found.")
        return

    with open(BOOKMARK_FILE, "r", encoding="utf-8") as f:
        bookmarks = json.load(f)

    bookmark_win = Toplevel(app)
    bookmark_win.title("Bookmarks")
    bookmark_win.geometry("400x300")

    def load_selected():
        selected = listbox.curselection()
        if selected:
            index = selected[0]
            url_entry.delete(0, "end")
            url_entry.insert(0, bookmarks[index]["url"])
            page_entry.delete(0, "end")
            page_entry.insert(0, "1")
            bookmark_win.destroy()
            refresh()

    def delete_selected():
        selected = listbox.curselection()
        if selected:
            index = selected[0]
            confirm = messagebox.askyesno("Delete Bookmark", f"Delete bookmark '{bookmarks[index]['label']}'?")
            if confirm:
                del bookmarks[index]
                with open(BOOKMARK_FILE, "w", encoding="utf-8") as f:
                    json.dump(bookmarks, f, indent=2)
                listbox.delete(index)

    listbox = Listbox(bookmark_win)
    for bm in bookmarks:
        listbox.insert("end", bm["label"])
    listbox.pack(fill="both", expand=True, padx=10, pady=10)

    btn_frame = ttk.Frame(bookmark_win)
    btn_frame.pack(pady=5)
    ttk.Button(btn_frame, text="Open", command=load_selected, bootstyle=PRIMARY).pack(side="left", padx=5)
    ttk.Button(btn_frame, text="Delete", command=delete_selected, bootstyle=DANGER).pack(side="left", padx=5)

# GUI Setup
app = ttk.Window(themename="darkly")
app.title("Forum Scraper")
app.geometry("1024x768")
app.rowconfigure(3, weight=1)
app.columnconfigure(1, weight=1)

# URL input

# Toggleable URL input section
toggle_frame = ttk.Frame(app)
toggle_frame.grid(row=0, column=0, columnspan=4, sticky="w")

def toggle_url_input():
    if url_input_frame.winfo_viewable():
        url_input_frame.grid_remove()
        toggle_btn.config(text="Show URL Input")
    else:
        url_input_frame.grid()
        toggle_btn.config(text="Hide URL Input")

toggle_btn = ttk.Button(toggle_frame, text="URL Input", command=toggle_url_input, bootstyle=SECONDARY)
toggle_btn.pack(anchor="w", padx=5, pady=10)

url_input_frame = ttk.Frame(app)
url_input_frame.grid(row=0, column=2,padx=5, columnspan=4, sticky="w")
url_input_frame.grid_remove()

ttk.Label(url_input_frame, text="Input URL:").grid(row=0, column=1, sticky="w", padx=5, pady=5)
url_entry = ttk.Entry(url_input_frame, width=80)
url_entry.grid(row=0, column=2, columnspan=4, sticky="w", padx=5, pady=5)

# Blank row to prevent overlap
#ttk.Label(app, text="").grid(row=2, column=0, columnspan=7, pady=5)

# Page input and controls
ttk.Label(app, text="Go to Page:").grid(row=1, column=0, sticky="w", padx=5,pady=5)
page_entry = ttk.Entry(app, width=10)
page_entry.grid(row=1, column=1, sticky="w", padx=5)
ttk.Button(app, text="Go", command=go_to_page, bootstyle=PRIMARY).grid(row=1, column=2, sticky="w", padx=5)
ttk.Button(app, text="Refresh", command=refresh, bootstyle=SECONDARY).grid(row=1, column=3, sticky="w", padx=5)
page_label = ttk.Label(app, text="Current Page: -")
page_label.grid(row=1, column=4, sticky="w", padx=10)
noti_label = ttk.Label(app, text="", bootstyle=INFO)
noti_label.grid(row=1, column=5, sticky="w", padx=5)
post_noti_label = ttk.Label(app, text="", bootstyle=INFO)
post_noti_label.grid(row=1, column=6, sticky="w", padx=5)

# Navigation buttons
nav_frame = ttk.Frame(app)
nav_frame.grid(row=2, column=0, columnspan=7, sticky="ew", padx=5,pady=5)
ttk.Button(nav_frame, text="Previous Page", command=go_previous, bootstyle=SECONDARY).pack(side="left", padx=5)
ttk.Button(nav_frame, text="Next Page", command=go_next, bootstyle=SECONDARY).pack(side="left", padx=5)
ttk.Button(nav_frame, text="Latest Page", command=go_latest, bootstyle=SECONDARY).pack(side="left", padx=5)
ttk.Button(nav_frame, text="Save to File", command=save_to_file, bootstyle=SUCCESS).pack(side="right", padx=5)
ttk.Button(nav_frame, text="Add Bookmark", command=add_bookmark, bootstyle=INFO).pack(side="right", padx=5)
ttk.Button(nav_frame, text="Show Bookmarks", command=show_bookmarks, bootstyle=INFO).pack(side="right", padx=5)

# Output area
output_text = ttk.ScrolledText(app, wrap="word", font=("Consolas", 10))
output_text.grid(row=3, column=0, columnspan=7, sticky="nsew", padx=10, pady=10)

# Bind F5 to refresh
app.bind("<F5>", refresh)

# Load last session and start update checker
load_last_session()
check_for_updates()

# Start the GUI
app.mainloop()
