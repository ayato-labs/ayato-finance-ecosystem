import pytest
import os
from src.translate_for_analysis import translate_mda

def test_translator_no_api_key(mocker):
    """APIキーがない場合に適切にログを出力して終了するかを確認"""
    # 環境変数からキーを一時的に削除
    mocker.patch.dict(os.environ, {"GOOGLE_API_KEY": ""})
    
    # 実際に関数を呼び出す (MagicMockでクライアントを置換しない)
    # ログ出力のみを確認するため、エラーが発生せずに終了することを確認
    translate_mda("AAPL")

def test_translator_file_not_found():
    """入力ファイルがない場合に適切に終了するかを確認"""
    translate_mda("NON_EXISTENT_TICKER")
