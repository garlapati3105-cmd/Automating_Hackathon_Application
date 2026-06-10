"""Debug MLH card inner HTML."""
import requests
from bs4 import BeautifulSoup

r = requests.get(
    "https://mlh.io/seasons/2025/events",
    headers={"User-Agent": "HackathonHunter/1.0"},
    timeout=15,
)
soup = BeautifulSoup(r.text, "lxml")

for anchor in soup.find_all("a", href=True):
    card = anchor.find(class_="rounded-card")
    if card:
        print("FIRST CARD FULL HTML:")
        print(card.prettify()[:2000])
        print("\nCard text (all):", card.get_text(separator="|", strip=True)[:400])
        break
