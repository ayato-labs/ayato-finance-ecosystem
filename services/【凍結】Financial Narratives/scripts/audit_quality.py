import asyncio
import json

from src.db.master_db import JobQueue
from src.storage import FinancialNarrativeStorage
from src.structurer import FinancialNarrativeStructurer


async def audit_ticker(ticker_query: str):
    queue = JobQueue()
    storage = FinancialNarrativeStorage(market="jp")
    structurer = FinancialNarrativeStructurer()

    # 1. ターゲットジョブの特定
    conn = queue._get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM jobs WHERE ticker LIKE ? AND market = 'jp' ORDER BY filing_date DESC LIMIT 1",
        (f"%{ticker_query}%",),
    )
    job = cursor.fetchone()

    if not job:
        print(f"\n[!] Ticker {ticker_query} not found in Job Queue.")
        return

    acc_no = job["accession_number"]
    ticker = job["ticker"]
    print(f"\n=== Auditing: {ticker} (Acc: {acc_no}) ===")

    # 2. Data Lake から全セクションを取得
    sections = storage.get_sections(acc_no)
    if not sections:
        print(f"[!] No sections found in Data Lake for {acc_no}")
        return

    print(f"[*] Data Lake contains {len(sections)} sections.")
    all_tags = list(sections.keys())
    print(f"[*] Available Tags: {all_tags[:10]}... (Total {len(all_tags)})")

    # 3. マッピングプロセスの検証
    print("\n--- Phase 1: Tag Mapping ---")
    mapping = await structurer._identify_tags(all_tags)
    print(f"[*] Identified Mapping: {json.dumps(mapping, indent=2, ensure_ascii=False)}")

    # 選ばれなかったタグのリスト
    mapped_tags = set()
    for tags in mapping.values():
        if isinstance(tags, list):
            mapped_tags.update(tags)

    missing_critical = [
        tag for tag in all_tags if "研究開発" in tag or "設備投資" in tag or "ガバナンス" in tag
    ]
    unmapped_critical = [tag for tag in missing_critical if tag not in mapped_tags]

    if unmapped_critical:
        print(f"[WARNING] Potential critical tags MISSED by LLM: {unmapped_critical}")
    else:
        print("[OK] Critical keywords (R&D, Capex) seem to be mapped.")

    # 4. 最終抽出の検証
    print("\n--- Phase 2: Fact Extraction ---")
    facts = await structurer.extract_facts(sections)

    if not facts:
        print("[FAILURE] LLM returned EMPTY facts.")
    else:
        print(f"[SUCCESS] Extracted {len(facts)} categories.")
        # 抜粋を表示
        for cat, content in facts.items():
            if cat == "thinking":
                continue
            val = content.get("facts", "")[:100]
            print(f"  - {cat}: {val}...")


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "7203"
    asyncio.run(audit_ticker(target))
