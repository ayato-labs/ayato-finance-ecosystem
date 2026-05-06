import os
import json
import duckdb
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load env for API keys
load_dotenv()

# Configuration
JP_DB_PATH = "data/narratives_jp.duckdb"
US_DB_PATH = "data/narratives_us.duckdb"
MODEL_NAME = "gemma-4-31b-it"

EXPERIMENT_PROMPT = """
あなたは、金融ドキュメントの高度な抽出エンジンです。
提供された『定性情報のセクション』から、以下の2つの軸で構造化データを抽出してください。

1. 投資と成長 (Investment & Growth):
   - 設備投資 (Capex): 投資意図、対象設備、金額の見通し、実施時期。
   - 研究開発 (R&D): 重点項目、技術的優位性の源泉、将来の成長エンジン。

2. ガバナンスと規律 (Governance & Discipline):
   - 資本配分の方針: キャッシュの使い道（還元、投資、財務健全性）。
   - ガバナンス体制: 役員報酬の設計（インセンティブ）、取締役会の構成に関する重要な事実。

【制約】
- 推測や要約はせず、テキストに明記されている『事実』のみを抽出してください。
- 該当する情報が全くない場合は null を返してください。
- 出力は必ず以下のJSON形式で行ってください。

JSON Schema:
{
  "investment_growth": {
    "capex": {
      "intent": string,
      "target": string,
      "amount": string,
      "timing": string,
      "evidence": string
    },
    "rd": {
      "priority_items": string[],
      "advantage": string,
      "evidence": string
    }
  },
  "governance_discipline": {
    "capital_allocation": {
      "policy": string,
      "priority": string,
      "evidence": string
    },
    "governance_structure": {
      "incentives": string,
      "board_notes": string,
      "evidence": string
    }
  }
}
"""

def run_experiment():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY not found in env")
        return

    client = genai.Client(api_key=api_key)
    
    samples = []
    
    # 1. Fetch JP Sample (3399) from JP DB
    if os.path.exists(JP_DB_PATH):
        print(f"Connecting to {JP_DB_PATH}...")
        with duckdb.connect(JP_DB_PATH, read_only=True) as conn:
            jp_data = conn.execute("SELECT ticker, form, sections FROM filings WHERE ticker = '3399' LIMIT 1").fetchone()
            if jp_data: samples.append(jp_data)
    
    # 2. Fetch US Sample (AAPL) from US DB
    if os.path.exists(US_DB_PATH):
        print(f"Connecting to {US_DB_PATH}...")
        with duckdb.connect(US_DB_PATH, read_only=True) as conn:
            us_data = conn.execute("SELECT ticker, form, sections FROM filings WHERE ticker = 'AAPL' LIMIT 1").fetchone()
            if us_data: samples.append(us_data)
    
    results = []

    for ticker, form, sections_json in samples:
        print(f"Processing experiment for {ticker} ({form})...")
        sections = json.loads(sections_json)
        
        content = ""
        for key, text in sections.items():
            content += f"### Section: {key}\n{text}\n\n"
        
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=f"以下のドキュメントから情報を抽出してください:\n\n{content}",
                config=types.GenerateContentConfig(
                    system_instruction=EXPERIMENT_PROMPT,
                    response_mime_type="application/json",
                ),
            )
            
            structured = response.text
            results.append({
                "ticker": ticker,
                "form": form,
                "data": json.loads(structured)
            })
            print(f"Successfully structured {ticker}")
            
        except Exception as e:
            print(f"Failed to process {ticker}: {e}")
            results.append({
                "ticker": ticker,
                "form": form,
                "error": str(e)
            })

    output_path = "artifacts/experiments/structuring_verification_20260504.md"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# Fact Extraction Experiment Results ({MODEL_NAME})\n\n")
        f.write("抽出ロジックの検証結果：設備投資・研究開発・ガバナンスの構造化テスト。\n\n")
        
        for res in results:
            f.write(f"## Target: {res['ticker']} ({res['form']})\n")
            if "error" in res:
                f.write(f"**Error**: {res['error']}\n\n")
            else:
                f.write("### 抽出結果 (JSON)\n")
                f.write(f"```json\n{json.dumps(res['data'], indent=2, ensure_ascii=False)}\n```\n\n")
                
                f.write("### 考察\n")
                has_growth = res['data'].get('investment_growth')
                f.write(f"- 成長投資セクション: {'抽出成功' if has_growth else '情報不足'}\n")
                f.write(f"- ガバナンスセクション: {'抽出成功' if res['data'].get('governance_discipline') else '情報不足'}\n\n")
            f.write("---\n")

    print(f"Experiment report generated at {output_path}")

if __name__ == "__main__":
    run_experiment()
