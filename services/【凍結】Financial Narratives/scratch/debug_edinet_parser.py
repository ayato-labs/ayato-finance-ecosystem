import io
import requests
from dotenv import load_dotenv
from src.edinet_fetcher import EdinetFetcher
from src.edinet_parser import EdinetParser

load_dotenv()

def test_parser_live():
    fetcher = EdinetFetcher()
    parser = EdinetParser()
    doc_id = "S100Y1UW" # 9799 (伊豆シャボテン)
    
    print(f"Testing live parse for {doc_id}...")
    zip_bytes = fetcher.download_document(doc_id)
    if not zip_bytes:
        print("Failed to download.")
        return
        
    sections = parser.parse_zip(zip_bytes)
    print(f"Found {len(sections)} sections.")
    for key, text in list(sections.items())[:5]:
        print(f" - {key}: {len(text)} chars")

if __name__ == "__main__":
    test_parser_live()
