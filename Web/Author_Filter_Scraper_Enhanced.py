
import tkinter as tk
from tkinter import ttk, scrolledtext
import requests
from bs4 import BeautifulSoup
import urllib3
import threading
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = tk.Tk()
app.title("Author Filter Forum Scraper")
app.geometry("1024x768")

# Input fields
tk.Label(app, text="Forum URL:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
url_entry = ttk.Entry(app, width=80)
url_entry.grid(row=0, column=1, columnspan=4, padx=5, pady=5, sticky="w")

tk.Label(app, text="Author:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
author_entry = ttk.Entry(app, width=30)
author_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")

tk.Label(app, text="From Page:").grid(row=1, column=2, padx=5, pady=5, sticky="w")
from_page_entry = ttk.Entry(app, width=5)
from_page_entry.grid(row=1, column=3, padx=5, pady=5, sticky="w")

tk.Label(app, text="To Page (leave blank for latest):").grid(row=1, column=4, padx=5, pady=5, sticky="w")
to_page_entry = ttk.Entry(app, width=5)
to_page_entry.grid(row=1, column=5, padx=5, pady=5, sticky="w")

tk.Label(app, text="Refresh Interval (sec):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
interval_entry = ttk.Entry(app, width=10)
interval_entry.insert(0, "60")
interval_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")

progress_label = ttk.Label(app, text="Status: Idle")
progress_label.grid(row=2, column=2, columnspan=3, padx=5, pady=5, sticky="w")

output_text = scrolledtext.ScrolledText(app, wrap="word", font=("Consolas", 10))
output_text.grid(row=3, column=0, columnspan=6, padx=10, pady=10, sticky="nsew")

app.rowconfigure(3, weight=1)
app.columnconfigure(1, weight=1)

scanned_posts = set()

def get_latest_page(base_url):
    try:
        response = requests.get(base_url, headers={"User-Agent": "Mozilla/5.0"}, verify=False)
        soup = BeautifulSoup(response.content, "html.parser")
        nav = soup.find("div", class_="PageNav")
        if nav and nav.get("data-last"):
            return int(nav["data-last"])
    except:
        pass
    return 1

def scrape_author_posts():
    base_url = url_entry.get().strip().rstrip("/")
    author_filter = author_entry.get().strip()
    try:
        from_page = int(from_page_entry.get().strip())
    except:
        from_page = 1
    try:
        to_page = int(to_page_entry.get().strip())
    except:
        to_page = get_latest_page(base_url)

    results = []

    for page in range(from_page, to_page + 1):
        progress_label.config(text=f"Scanning page {page}/{to_page}")
        page_url = f"{base_url}/page-{page}"
        page_results = [f"Page {page}"]
        try:
            response = requests.get(page_url, headers={"User-Agent": "Mozilla/5.0"}, verify=False)
            soup = BeautifulSoup(response.content, "html.parser")
            for message in soup.find_all("li", class_="message"):
                post_id = message.get("id")
                if post_id in scanned_posts:
                    continue
                author = message.get("data-author", "").strip()
                if author_filter and author != author_filter:
                    continue
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
                            quote_content = quote_div.get_text(separator="", strip=True)
                content_block = message.find("blockquote", class_="messageText ugc baseHtml")
                main_content = ""
                if content_block:
                    aside = content_block.find("aside")
                    if aside:
                        aside.extract()
                    main_content = content_block.get_text(separator="", strip=True)
                formatted = f"👤 Author: {author}🕒 Time: {post_time}"
                if quote_author:
                    formatted += f"\n💬 Quote from {quote_author}:\n{quote_content}"                
                    formatted += f"\n📝---> Message<---:\n{main_content}\n{'-'*80}\n"
                page_results.append(formatted)
                scanned_posts.add(post_id)
        except Exception as e:
            page_results.append(f"Error on page {page}: {e}")
        results.append("".join(page_results))
    output_text.insert("end", "".join(results))
    progress_label.config(text="Status: Completed")

def threaded_scan():
    threading.Thread(target=scrape_author_posts, daemon=True).start()

ttk.Button(app, text="Start Scan", command=threaded_scan).grid(row=2, column=5, padx=5, pady=5)

app.mainloop()
