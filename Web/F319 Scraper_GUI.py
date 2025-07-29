import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox
import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def parse_page_range(page_input, latest_page):
    try:
        if page_input.lower() == "latest":
            return [latest_page]
        elif "-" in page_input:
            start, end = map(int, page_input.split("-"))
            return list(range(start, end + 1))
        else:
            return [int(page_input)]
    except ValueError:
        return []

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

def scrape_forum(event=None):
    base_url = url_entry.get().strip().rstrip("/")
    page_input = pages_entry.get().strip()
    latest_page = get_latest_page(base_url)
    pages = parse_page_range(page_input, latest_page)

    if not base_url or "f319.com" not in base_url or not pages:
        messagebox.showerror("Invalid Input", "Please enter a valid URL and page number or range (e.g., 243, 240-244, or 'latest').")
        return

    output_text.delete(1.0, tk.END)
    all_results = []

    for page in pages:
        page_url = f"{base_url}/page-{page}"
        try:
            response = requests.get(page_url, headers={"User-Agent": "Mozilla/5.0"}, verify=False)
            soup = BeautifulSoup(response.content, "html.parser")

            for message in soup.find_all("li", class_="message"):
                content_block = message.find("blockquote", class_="messageText ugc baseHtml")
                time_tag = message.find("a", class_="datePermalink")
                if content_block and time_tag:
                    text = content_block.get_text(separator="\n", strip=True)
                    time = time_tag.get_text(strip=True)
                    all_results.append(f"[{time}]\n{text}\n")

        except Exception as e:
            all_results.append(f"Error loading page {page}: {e}\n")

    output_text.insert(tk.END, "\n".join(all_results))

def save_to_file():
    content = output_text.get(1.0, tk.END).strip()
    if not content:
        messagebox.showinfo("No Content", "There is no content to save.")
        return

    file_path = filedialog.asksaveasfilename(defaultextension=".txt",
                                             filetypes=[("Text Files", "*.txt")])
    if file_path:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        messagebox.showinfo("Saved", f"Content saved to {file_path}")

# GUI Setup
root = tk.Tk()
root.title("F319 Forum Scraper")
root.geometry("1024x768")
root.rowconfigure(2, weight=1)
root.columnconfigure(1, weight=1)

# URL input
tk.Label(root, text="F319 Thread URL:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
url_entry = tk.Entry(root)
url_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

# Page range input
tk.Label(root, text="Page(s) (e.g. 243, 240-244, latest):").grid(row=1, column=0, sticky="w", padx=5)
pages_entry = tk.Entry(root)
pages_entry.grid(row=1, column=1, sticky="ew", padx=5)

# Buttons
button_frame = tk.Frame(root)
button_frame.grid(row=1, column=2, sticky="e", padx=5)
refresh_button = tk.Button(button_frame, text="Refresh", command=scrape_forum)
refresh_button.pack(side="left", padx=2)
save_button = tk.Button(button_frame, text="Save to File", command=save_to_file)
save_button.pack(side="left", padx=2)

# Output area
output_text = scrolledtext.ScrolledText(root, wrap=tk.WORD)
output_text.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=10, pady=10)

# Bind F5 to refresh
root.bind("<F5>", scrape_forum)

root.mainloop()
