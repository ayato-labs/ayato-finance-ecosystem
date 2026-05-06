import asyncio
import sys
from pathlib import Path

# プロジェクトルートを追加
sys.path.append(str(Path.cwd()))

from src.structuring_worker import StructuringWorkerPool
from src.config import GOOGLE_AI_MODELS
from loguru import logger

async def test_one():
    # 1件だけ処理する特別モード
    pool = StructuringWorkerPool(num_workers=1)
    model_name = GOOGLE_AI_MODELS[0]
    
    print(f"Testing extraction with model: {model_name}")
    
    # _worker_loop の中身を模倣して1回だけ実行
    job = pool.queue.dequeue_job(market="us")
    if not job:
        print("No US jobs in PENDING status.")
        return
        
    acc_no = job['accession_number']
    ticker = job['ticker']
    market = job['market']
    print(f"Processing {ticker} ({acc_no})...")
    
    try:
        # 1. セクション取得
        sections = await pool._get_sections_from_lake(acc_no, market)
        print(f"Retrieved data from Data Lake. Type: {type(sections)}")
        
        if isinstance(sections, str):
            print(f"Data is a string of length {len(sections)}.")
            print(f"Hex of first 10 chars: {[ord(c) for c in sections[:10]]}")
            print(f"Repr of first 100 chars: {repr(sections[:100])}")
            
            # もしJSONならパース
            if sections.startswith('{'):
                import json
                sections = json.loads(sections)
        
        if not isinstance(sections, dict):
            print(f"ERROR: Expected dict but got {type(sections)}. Sections: {str(sections)[:200]}")
            return
            
        print(f"Keys Found: {list(sections.keys())}")
        
        if len(sections) <= 1:
            print("WARNING: Data Lake still only has 1 section. Re-fetch might have failed or not reached DB.")
            return

        # 2. 構造化
        from src.structurer import FilingStructurer
        structurer = FilingStructurer(api_key=pool.api_key, model_name=model_name)
        
        print("Starting LLM extraction (this may take a minute)...")
        facts = await structurer.structure_filing(sections, market=market)
        
        # 3. 結果表示
        print("\n--- Extraction Results ---")
        print(f"Thinking: {facts.get('thinking', 'N/A')[:500]}...")
        print(f"Facts Found: {len(facts.get('facts', []))}")
        for i, f in enumerate(facts.get('facts', [])[:5]):
            print(f"  {i+1}. {f}")
            
        # 4. 保存
        import json
        pool.queue.store_parsed_result(acc_no, json.dumps(facts, ensure_ascii=False))
        print(f"\nResult saved to SQLite for {ticker}.")

    except Exception as e:
        logger.exception(f"Extraction failed: {e}")
        pool.queue.fail_job(acc_no, str(e))

if __name__ == "__main__":
    asyncio.run(test_one())
