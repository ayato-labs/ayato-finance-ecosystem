import io
import zipfile
from src.core.config import settings
from src.core.csv_parser import get_csv_from_edinet

def debug_raw_zip():
    doc_id = "S100L8TB"
    content = get_csv_from_edinet(doc_id, settings.EDINET_API_KEY)
    if not content:
        return
    
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        for info in z.infolist():
            print(f"File: {info.filename}, Size: {info.file_size}")
            if info.filename.endswith(".csv") and info.file_size > 0:
                with z.open(info.filename) as f:
                    raw = f.read(500)
                    print(f"Raw Head (Hex): {raw.hex()[:100]}")
                    try:
                        print(f"Raw Head (cp932): {raw.decode('cp932', errors='replace')[:200]}")
                    except Exception as e:
                        print(f"Failed to decode as cp932: {e}")

if __name__ == "__main__":
    debug_raw_zip()
