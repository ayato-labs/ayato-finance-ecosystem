import os
import time
from pathlib import Path

from google import genai
from loguru import logger

def translate_mda(ticker: str):
    base_path = Path("C:/Users/saiha/My_Service/programing/finance/Financial Narratives/data")
    raw_path = base_path / f"raw/{ticker}_mda.txt"
    output_path = base_path / f"translated_analysis/{ticker}_mda_jp.md"

    if not raw_path.exists():
        logger.error(f"Raw file not found for {ticker}")
        return

    with open(raw_path, encoding="utf-8") as f:
        text = f.read()

    # API設定
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.error("GOOGLE_API_KEY not found in environment variables.")
        return

    client = genai.Client(api_key=api_key)

    logger.info(f"Translating MD&A for {ticker} ({len(text)} characters)...")

    # 長いテキストを分割 (Geminiのコンテキスト制限に配慮)
    chunk_size = 10000
    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

    translated_chunks = []
    for i, chunk in enumerate(chunks):
        logger.info(f"Translating chunk {i+1}/{len(chunks)}...")
        prompt = (
            "You are a professional financial translator. "
            "Translate the following section of a SEC 10-K filing (MD&A) into Japanese. "
            "Keep the translation as literal and faithful to the original as possible. "
            "Do not summarize. Do not skip any sentences. "
            "Original Text:\n" + chunk
        )

        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )
            translated_chunks.append(response.text)
            time.sleep(2) # レート制限対策
        except Exception as e:
            logger.error(f"Translation failed for chunk {i+1}: {e}")
            translated_chunks.append(f"\n[Translation Error: {e}]\n")

    # ファイル書き出し
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# {ticker} MD&A - 日本語直訳全文\n\n")
        f.write("".join(translated_chunks))

    logger.success(f"Saved translated MD&A for {ticker} to {output_path}")

if __name__ == "__main__":
    # まずは分析の優先度が高い2社を実行
    for t in ["AAPL", "NVDA"]:
        translate_mda(t)
