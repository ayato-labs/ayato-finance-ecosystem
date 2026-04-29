import logging
import sys
from unittest.mock import MagicMock

from src.mappers.ai_mapper import AIMapper

# ログ設定: コンソール出力をキャプチャできるように設定
logging.basicConfig(level=logging.ERROR, stream=sys.stdout)
logger = logging.getLogger("src.mappers.ai_mapper")


def verify_log_sanitization():
    print("=== Step 1: Simulating AI Loop/Hallucination ===")
    mapper = AIMapper()

    # AIが数千文字のゴミデータを返したと仮定
    garbage_text = "level-" * 1000

    # generate_contentの結果をラップするモック
    mock_response = MagicMock()
    mock_response.text = garbage_text

    mapper.client.models.generate_content = MagicMock(return_value=mock_response)

    print(f"Feeding {len(garbage_text)} characters of garbage to the mapper...")

    try:
        # この呼び出しでエラーログが発生するはず
        mapper.map_tag("US", "TEST_TAG", "TEST_DESC", "verify-session-3")
    except Exception as e:
        print(f"\ncaught expected exception: {e}")


if __name__ == "__main__":
    verify_log_sanitization()
