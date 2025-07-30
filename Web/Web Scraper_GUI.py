import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import filedialog
import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

current_page = 1
latest_page = 1

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

def scrape_page(page):
    global current_page, latest_page
    base_url = url_entry.get().strip().rstrip("/")
    if not base_url or "f319.com" not in base_url:
        ttk.messagebox.showerror("Invalid URL", "Please enter a valid F319 thread URL.")
        return

    latest_page = get_latest_page(base_url)
    current_page = max(1, min(page, latest_page))
    page_label.config(text=f"Current Page: {current_page}")

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
            formatted += f"\n📝 Message:\n{main_content}\n{'-'*80}\n"
            all_results.append(formatted)

    except Exception as e:
        all_results.append(f"Error loading page {current_page}: {e}\n")

    output_text.insert("end", "\n".join(all_results))

def refresh(event=None):
    try:
        page = int(page_entry.get().strip())
        scrape_page(page)
    except ValueError:
        ttk.messagebox.showerror("Invalid Input", "Please enter a valid page number.")

def go_previous():
    scrape_page(current_page - 1)

def go_next():
    scrape_page(current_page + 1)

def go_latest():
    scrape_page(get_latest_page(url_entry.get().strip().rstrip("/")))

def save_to_file():
    content = output_text.get("1.0", "end").strip()
    if not content:
        ttk.messagebox.showinfo("No Content", "There is no content to save.")
        return

    file_path = filedialog.asksaveasfilename(defaultextension=".txt",
                                             filetypes=[("Text Files", "*.txt")])
    if file_path:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        ttk.messagebox.showinfo("Saved", f"Content saved to {file_path}")

# GUI Setup
app = ttk.Window(themename="darkly")
app.title("Forum Scraper")
app.geometry("1024x768")
app.rowconfigure(3, weight=1)
app.columnconfigure(1, weight=1)

# URL input
ttk.Label(app, text="Input URL:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
url_entry = ttk.Entry(app, width=80)
url_entry.grid(row=0, column=1, columnspan=3, sticky="ew", padx=5, pady=5)

# Page input and controls
ttk.Label(app, text="Go to Page:").grid(row=1, column=0, sticky="w", padx=5)
page_entry = ttk.Entry(app, width=10)
page_entry.grid(row=1, column=1, sticky="w", padx=5)
ttk.Button(app, text="Refresh", command=refresh, bootstyle=PRIMARY).grid(row=1, column=3, sticky="w", padx=5)
page_label = ttk.Label(app, text="Current Page: -")
page_label.grid(row=1, column=2, sticky="w", padx=10)

# Navigation buttons
nav_frame = ttk.Frame(app)
nav_frame.grid(row=2, column=0, columnspan=4, sticky="ew", padx=5)
ttk.Button(nav_frame, text="Previous Page", command=go_previous, bootstyle=SECONDARY).pack(side="left", padx=5)
ttk.Button(nav_frame, text="Next Page", command=go_next, bootstyle=SECONDARY).pack(side="left", padx=5)
ttk.Button(nav_frame, text="Latest Page", command=go_latest, bootstyle=SECONDARY).pack(side="left", padx=5)
ttk.Button(nav_frame, text="Save to File", command=save_to_file, bootstyle=SUCCESS).pack(side="right", padx=5)

# Output area
output_text = ttk.ScrolledText(app, wrap="word", font=("Consolas", 10))
output_text.grid(row=3, column=0, columnspan=4, sticky="nsew", padx=10, pady=10)

# Bind F5 to refresh
app.bind("<F5>", refresh)

app.mainloop()
