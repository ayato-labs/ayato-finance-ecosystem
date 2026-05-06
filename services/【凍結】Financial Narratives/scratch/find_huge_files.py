import io
import zipfile
from dotenv import load_dotenv
from src.edinet_fetcher import EdinetFetcher

load_dotenv()

def find_huge_files():
    fetcher = EdinetFetcher()
    doc_id = "S100T72D" 
    
    print(f"Listing all files in {doc_id} to find the bottleneck...")
    zip_bytes = fetcher.download_document(doc_id)
    if not zip_bytes:
        print("Failed to download.")
        return
        
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        files = []
        for info in z.infolist():
            files.append((info.filename, info.file_size))
        
        # サイズ順にソート
        files.sort(key=lambda x: x[1], reverse=True)
        
        print("\nTop 20 Largest Files in ZIP:")
        for name, size in files[:20]:
            print(f" - {name}: {size / 1024 / 1024:.2f} MB")

if __name__ == "__main__":
    find_huge_files()
