import requests
from bs4 import BeautifulSoup
import re

url = "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm"
headers = {"User-Agent": "SampleAgent sample@example.com"}

response = requests.get(url, headers=headers)
html = response.text

soup = BeautifulSoup(html, 'lxml')
# "Item 7" を含むノードを探す
pattern = re.compile(r"Item\s+7\.?", re.IGNORECASE)
matches = soup.find_all(text=pattern)

print(f"Total matches found: {len(matches)}")
for i, m in enumerate(matches[:15]):  # 最初の15個を確認
    parent = m.parent
    print(f"\n--- Match {i+1} ---")
    print(f"Text: '{m.strip()}'")
    print(f"Parent Tag: {parent.name}")
    print(f"Parent Class: {parent.get('class')}")
    print(f"Parent attrs: {parent.attrs}")
    # さらに上の階層も少し見る
    grandparent = parent.parent
    print(f"Grandparent Tag: {grandparent.name}")
