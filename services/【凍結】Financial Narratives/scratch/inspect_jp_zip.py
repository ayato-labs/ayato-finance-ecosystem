import os
import io
import zipfile
from src.edinet_fetcher import EdinetFetcher
from dotenv import load_dotenv

def inspect_zip():
    load_dotenv()
    fetcher = EdinetFetcher()
    doc_id = "S100Y1KO"
    zip_bytes = fetcher.download_document(doc_id, doc_type=1)
    
    if zip_bytes:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            print("Files in ZIP:")
            for name in z.namelist()[:20]:
                print(f"  {name}")
            
            html_files = [f for f in z.namelist() if f.startswith("PublicDoc/") and f.endswith((".htm", ".html"))]
            if html_files:
                print(f"\nContent of {html_files[0]}:")
                with z.open(html_files[0]) as f:
                    content = f.read().decode("utf-8", errors="ignore")
                    print(content[:2000])
                    # Look for ix: tags
                    import re
                    ix_tags = re.findall(r'<ix:[^>]+name="([^"]+)"', content)
                    print(f"\nFound {len(ix_tags)} ix tags.")
                    print(f"First 10 tags: {ix_tags[:10]}")
            else:
                print("\nNo HTML files found in PublicDoc/")

if __name__ == "__main__":
    inspect_zip()
