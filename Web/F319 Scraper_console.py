import requests
from bs4 import BeautifulSoup
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = "https://f319.com/threads/toa-son-quanthuong-tra-luan-ban-vni-chinh-ra-sao-truoc-khi-don-ky-niem-dai-le-quoc-khanh.1922921/page-243"
headers = {
    "User-Agent": "Mozilla/5.0"
}

response = requests.get(url, headers=headers, verify=False)
soup = BeautifulSoup(response.content, "html.parser")

results = []

# Loop through each message block
for message in soup.find_all("li", class_="message"):
    content_block = message.find("blockquote", class_="messageText ugc baseHtml")
    time_tag = message.find("a", class_="datePermalink")
    
    if content_block and time_tag:
        text = content_block.get_text(separator="\n", strip=True)
        time = time_tag.get_text(strip=True)
        results.append({"time": time, "message": text})

# Print results
for i, item in enumerate(results, 1):
    print(f"--- Message {i} ---")
    print(f"Time: {item['time']}")
    print(f"Content:\n{item['message']}\n")
