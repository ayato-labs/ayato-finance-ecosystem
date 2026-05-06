import io
import zipfile
import re
from dotenv import load_dotenv
from src.edinet_fetcher import EdinetFetcher

load_dotenv()

def inspect_raw_html():
    fetcher = EdinetFetcher()
    doc_id = "S100Y1UW" # 9799
    
    print(f"Inspecting raw HTML for {doc_id}...")
    zip_bytes = fetcher.download_document(doc_id)
    if not zip_bytes:
        print("Failed to download.")
        return
        
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        html_files = [f for f in z.namelist() if "PublicDoc/" in f and f.endswith((".htm", ".html"))]
        if not html_files:
            print("No HTML files found in PublicDoc/.")
            print("Zip content preview:", z.namelist()[:10])
            return
            
        with z.open(html_files[0]) as f:
            content = f.read().decode("utf-8", errors="ignore")
            print(f"HTML Length: {len(content)}")
            
            # Find any ix:nonNumeric tags manually
            sample = re.findall(r'<ix:nonNumeric[^>]*>', content[:100000])
            print(f"Found {len(sample)} sample tags in first 100k chars.")
            for s in sample[:5]:
                print(f" - Tag: {s}")

if __name__ == "__main__":
    inspect_raw_html()
