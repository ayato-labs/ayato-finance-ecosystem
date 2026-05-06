import io
import time
import zipfile
import re
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from dotenv import load_dotenv
from src.edinet_fetcher import EdinetFetcher

load_dotenv()

def profile_parser():
    fetcher = EdinetFetcher()
    # 日本酸素ホールディングス (4091) の有報。実戦級の巨大ファイル。
    doc_id = "S100TN9T" 
    
    print(f"# Profiling EDINET Parsing for {doc_id}\n")
    zip_bytes = fetcher.download_document(doc_id)
    if not zip_bytes:
        print("Failed to download.")
        return
        
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        html_files = [f for f in z.namelist() if "PublicDoc/" in f and f.endswith((".htm", ".html"))]
        print(f"Total HTML files: {len(html_files)}")
        
        all_content = ""
        for html_file in html_files:
            with z.open(html_file) as f:
                all_content += f.read().decode("utf-8", errors="ignore")
        
        print(f"Total Combined HTML Length: {len(all_content)} chars")
        
        # 1. Regex find matches (Targeting all tags)
        pattern = re.compile(r'<ix:nonNumeric[^>]*name="([^"]+)"[^>]*>(.*?)</ix:nonNumeric>', re.DOTALL)
        start = time.perf_counter()
        matches = pattern.findall(all_content)
        regex_find_time = time.perf_counter() - start
        print(f"\n1. Regex findall (matches={len(matches)}): {regex_find_time:.4f}s")

        if not matches:
            return

        # 小規模なサンプリング（全体の1/10または最大20個）で計測
        sample_size = min(len(matches), 20)
        samples = matches[:sample_size]
        print(f"Profiling performance on {sample_size} tags...")

        # 2. Markdownify profiling
        start = time.perf_counter()
        for _, content in samples:
            try:
                _ = md(content, heading_style="ATX")
            except:
                pass
        md_time = time.perf_counter() - start
        avg_md = md_time / sample_size
        print(f"2. Markdownify (Average per tag): {avg_md:.4f}s | Estimated Total: {avg_md * len(matches):.2f}s")

        # 3. BeautifulSoup profiling
        start = time.perf_counter()
        for _, content in samples:
            try:
                soup = BeautifulSoup(content, "html.parser")
                _ = soup.get_text(separator="\n")
            except:
                pass
        bs_time = time.perf_counter() - start
        avg_bs = bs_time / sample_size
        print(f"3. BeautifulSoup.get_text (Average): {avg_bs:.4f}s | Estimated Total: {avg_bs * len(matches):.2f}s")

        # 4. Regex Strip profiling
        start = time.perf_counter()
        for _, content in samples:
            _ = re.sub(r'<[^>]+>', '', content)
        re_strip_time = time.perf_counter() - start
        avg_re = re_strip_time / sample_size
        print(f"4. Regex tag strip (Average): {avg_re:.4f}s | Estimated Total: {avg_re * len(matches):.2f}s")

if __name__ == "__main__":
    profile_parser()
