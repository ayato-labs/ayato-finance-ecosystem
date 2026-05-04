import asyncio
import random

import pytest

from src.storage import FinancialNarrativeStorage


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "robustness_test.duckdb"
    return str(db_file)


@pytest.mark.asyncio
async def test_high_concurrency_writes(temp_db):
    """
    100個の非同期タスクが同時にDBに書き込みを行う「地獄のテスト」。
    市場別ロック（またはDuckDBの内部ロック）が正しく機能していればクラッシュしないはず。
    """
    storage = FinancialNarrativeStorage(db_path=temp_db)

    async def worker(worker_id):
        for i in range(10):
            acc_no = f"ACC-{worker_id}-{i}"
            ticker = f"T{worker_id}"
            metadata = {
                "accessionNumber": acc_no,
                "ticker": ticker,
                "form": "10-K",
                "filingDate": "2026-05-01"
            }
            sections = {"content": "X" * random.randint(100, 1000)}

            # storage.save_filing は同期メソッドなので to_thread で実行
            await asyncio.to_thread(storage.save_filing, metadata, sections)
            await asyncio.sleep(random.uniform(0.01, 0.05))

    # 50並列で worker を走らせる
    tasks = [worker(i) for i in range(50)]
    await asyncio.gather(*tasks)

    # 最終的なカウントを確認
    stats = storage.get_stats()
    assert stats["total_filings"] == 50 * 10
    print(f"\nSuccessfully handled {stats['total_filings']} concurrent writes.")


@pytest.mark.asyncio
async def test_deadlock_prevention_sim(temp_db):
    """
    保存と取得が入り乱れる状況でのデッドロック確認。
    """
    storage = FinancialNarrativeStorage(db_path=temp_db)

    async def writer():
        for i in range(50):
            storage.save_filing(
                {
                    "accessionNumber": f"W-{i}",
                    "ticker": "BUSY",
                    "form": "10-Q",
                    "filingDate": "2026-05-01"
                },
                {"data": "info"}
            )
            await asyncio.sleep(0.01)

    async def reader():
        for _ in range(50):
            _ = storage.get_filings_by_ticker("BUSY")
            await asyncio.sleep(0.01)

    await asyncio.gather(writer(), reader(), writer(), reader())
