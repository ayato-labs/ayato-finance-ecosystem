import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from src.batch_fetch import sync_recent_us_filings


@pytest.mark.asyncio
async def test_true_asynchronous_overlap_proof():
    """
    【アーキテクト視点のテスト】
    構造化タスク(重い処理)が、次のインジェクション(I/O処理)をブロックしていないことを、
    タイムスタンプの実行順序によって数学的に証明するテスト。
    """
    mock_fetcher = MagicMock()
    mock_parser = MagicMock()
    mock_storage = MagicMock()

    # 3つのティッカーを処理させる
    mock_fetcher.get_all_tickers.return_value = ["T1", "T2", "T3"]

    event_log = []

    # process_us_ticker (I/O部分) のモック: 0.1秒かかる
    async def mock_process_us(
        ticker, fetcher, parser, storage, run_structuring, days, structuring_tasks
    ):
        event_log.append(f"{ticker}_FETCH_START")
        await asyncio.sleep(0.1)
        event_log.append(f"{ticker}_FETCH_END")

        if structuring_tasks is not None:
            # 構造化タスク (LLM推論) のモック: I/Oより圧倒的に遅い 0.5秒かかる
            async def mock_heavy_structuring():
                event_log.append(f"{ticker}_STRUCT_START")
                await asyncio.sleep(0.5)
                event_log.append(f"{ticker}_STRUCT_END")

            structuring_tasks.append(asyncio.create_task(mock_heavy_structuring()))

    with patch("src.batch_fetch.process_us_ticker", side_effect=mock_process_us):
        start_time = time.perf_counter()
        await sync_recent_us_filings(
            mock_fetcher, mock_parser, mock_storage, days=1, run_structuring=True
        )
        end_time = time.perf_counter()

    # 1. 実行時間の証明:
    # もし直列(await)なら: (0.1 + 0.5) * 3 = 1.8秒以上かかる
    # 並列・非同期なら: I/O(0.1*3) は約0.3秒で終わり、裏で走るStruct(0.5)は並列処理されるので、
    # 全体で約0.8〜1.0秒で終わるはず
    duration = end_time - start_time
    assert duration < 1.5, (
        f"実行時間が長すぎます({duration:.2f}s)。非同期オーバーラップが機能していません。"
    )

    # 2. 実行順序の証明 (非ブロッキングの証拠):
    # T1のSTRUCT_END (完了) よりも前に、T2やT3のFETCH_START (開始) が
    # ログに記録されていなければならない
    t1_struct_end_idx = event_log.index("T1_STRUCT_END")
    t2_fetch_start_idx = event_log.index("T2_FETCH_START")

    assert t2_fetch_start_idx < t1_struct_end_idx, (
        "T1の構造化が終わるまでT2のフェッチがブロックされています！"
    )


@pytest.mark.asyncio
async def test_poison_pill_task_isolation():
    """
    【SRE視点のテスト】
    複数の構造化タスクのうちの1つが致命的な例外（パニック）を起こしても、
    return_exceptions=True によって他の正常なタスクが巻き添えで死なず、
    最後まで完走することを証明する。
    """
    mock_fetcher = MagicMock()
    mock_fetcher.get_all_tickers.return_value = ["GOOD1", "POISON", "GOOD2"]

    successful_structs = []

    async def mock_process_us(
        ticker, fetcher, parser, storage, run_structuring, days, structuring_tasks
    ):
        if structuring_tasks is not None:

            async def structured_task():
                if ticker == "POISON":
                    raise MemoryError("Out of Memory during LLM parsing!")
                successful_structs.append(ticker)
                return True

            structuring_tasks.append(asyncio.create_task(structured_task()))

    with patch("src.batch_fetch.process_us_ticker", side_effect=mock_process_us):
        # これがクラッシュせずに通ることが絶対条件
        await sync_recent_us_filings(mock_fetcher, None, None, days=1, run_structuring=True)

    # POISON は死んだが、GOOD1 と GOOD2 は正常に処理完了していること
    assert "GOOD1" in successful_structs
    assert "GOOD2" in successful_structs
    assert "POISON" not in successful_structs
