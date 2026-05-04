import asyncio
import time
from unittest.mock import patch

import pytest

from src.batch_fetch import batch_fetch


@pytest.mark.asyncio
async def test_parallel_execution_timing():
    """日米の取得が並列（同時）に開始・実行されていることを、擬似的な遅延を用いて検証"""

    # 擬似的な遅延を Fetcher に仕込む
    async def delayed_fetch(*args, **kwargs):
        await asyncio.sleep(1)  # 1秒待機
        return []

    with patch(
        "src.batch_fetch.sync_recent_jp_filings", side_effect=delayed_fetch
    ) as mock_jp, patch(
        "src.batch_fetch.sync_recent_us_filings", side_effect=delayed_fetch
    ) as mock_us:

        start_time = time.perf_counter()

        # 実行 (daysは任意、モックが呼ばれることを重視)
        await batch_fetch(days=1)

        end_time = time.perf_counter()
        duration = end_time - start_time

        # もし逐次（シリアル）実行なら、1s + 1s = 2s 以上かかるはず。
        # 並列実行なら、ほぼ 1s 程度で終わるはず。
        assert duration < 1.5, (
            f"Execution took too long ({duration:.2f}s), " "parallelization might be broken."
        )
        assert mock_jp.called
        assert mock_us.called


@pytest.mark.asyncio
async def test_parallel_error_isolation():
    """片方の市場でエラーが発生しても、もう片方の市場の処理が継続されることを検証"""

    async def fail_fetch(*args, **kwargs):
        raise RuntimeError("JP Market Crash")

    async def success_fetch(*args, **kwargs):
        await asyncio.sleep(0.1)
        return "Success"

    with patch("src.batch_fetch.sync_recent_jp_filings", side_effect=fail_fetch), patch(
        "src.batch_fetch.sync_recent_us_filings", side_effect=success_fetch
    ) as mock_us:

        # batch_fetch自体は例外をキャッチして正常終了するはず（ログにはエラーが出る）
        await batch_fetch(days=1)

        # US側が呼ばれていることを確認
        assert mock_us.called
