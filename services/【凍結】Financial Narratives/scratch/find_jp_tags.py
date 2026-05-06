import io
import zipfile
from bs4 import BeautifulSoup
from src.edinet_fetcher import EdinetFetcher
from dotenv import load_dotenv

def find_all_tags():
    load_dotenv()
    fetcher = EdinetFetcher()
    doc_id = "S100Y1KO" # 3399
    zip_bytes = fetcher.download_document(doc_id, doc_type=1)
    
    if zip_bytes:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            html_files = [f for f in z.namelist() if "PublicDoc/" in f and f.endswith((".htm", ".html"))]
            all_tags = set()
            for html_file in html_files:
                with z.open(html_file) as f:
                    content = f.read().decode("utf-8", errors="ignore")
                    soup = BeautifulSoup(content, "html.parser")
                    # Find all ix:nonNumeric tags
                    tags = soup.find_all(lambda t: t.name.endswith("nonnumeric"))
                    for t in tags:
                        name = t.get("name")
                        if name:
                            all_tags.add(name)
            
            print("Found tags:")
            for tag in sorted(list(all_tags)):
                if "jpcrp_cor" in tag:
                    print(f"  {tag}")

if __name__ == "__main__":
    find_all_tags()
