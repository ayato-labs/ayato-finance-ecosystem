import pytest

from src.storage import FinancialNarrativeStorage


def test_storage_init_and_save(temp_db_path, mock_filing_metadata):
    storage = FinancialNarrativeStorage(temp_db_path)
    sections = {"mda": "test content"}

    storage.save_filing(mock_filing_metadata, sections)

    # 存在確認のテスト
    assert storage.filing_exists(mock_filing_metadata["accessionNumber"]) is True
    assert storage.filing_exists("NON-EXISTENT") is False

    # サマリーの確認
    summary = storage.get_summary()
    assert len(summary) == 1
    assert summary[0][0] == "TEST"


def test_storage_upsert(temp_db_path, mock_filing_metadata):
    storage = FinancialNarrativeStorage(temp_db_path)

    # 1回目
    storage.save_filing(mock_filing_metadata, {"mda": "version 1"})
    # 2回目 (上書き)
    storage.save_filing(mock_filing_metadata, {"mda": "version 2"})

    # 重複せずに1レコードのみ存在することを確認
    summary = storage.get_summary()
    assert len(summary) == 1


def test_storage_invalid_metadata(temp_db_path):
    """メタデータが欠けている場合の挙動確認"""
    storage = FinancialNarrativeStorage(temp_db_path)
    # accessionNumber が無いメタデータ
    bad_metadata = {"ticker": "INVALID"}
    with pytest.raises(ValueError) as excinfo:
        storage.save_filing(bad_metadata, {"mda": "test"})
    assert "Missing required metadata fields" in str(excinfo.value)


def test_storage_very_large_content(temp_db_path, mock_filing_metadata):
    """極端に大きいデータの保存"""
    storage = FinancialNarrativeStorage(temp_db_path)
    large_content = "A" * (10 * 1024 * 1024)  # 10MB
    sections = {"mda": large_content}
    storage.save_filing(mock_filing_metadata, sections)

    filings = storage.get_filings_by_ticker("TEST")
    assert len(filings) == 1
    import json

    retrieved_sections = json.loads(filings[0][3])
    assert len(retrieved_sections["mda"]) == 10 * 1024 * 1024
