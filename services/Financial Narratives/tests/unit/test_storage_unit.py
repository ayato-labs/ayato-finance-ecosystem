import json
from pathlib import Path

import pytest

from src.storage import FinancialNarrativeStorage


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test.duckdb"
    return str(db_file)


def test_storage_init(temp_db):
    FinancialNarrativeStorage(db_path=temp_db)
    assert Path(temp_db).exists()


def test_save_and_get_filing(temp_db):
    storage = FinancialNarrativeStorage(db_path=temp_db)
    metadata = {
        "accessionNumber": "123-456",
        "ticker": "TEST",
        "cik": "000",
        "form": "10-K",
        "filingDate": "2026-05-01",
    }
    sections = {"business": "Testing business section content."}

    storage.save_filing(metadata, sections)

    # Retrieve
    filings = storage.get_filings_by_ticker("TEST")
    assert len(filings) == 1
    assert filings[0][0] == "TEST"
    assert filings[0][1] == "10-K"


def test_save_and_get_structuring(temp_db):
    storage = FinancialNarrativeStorage(db_path=temp_db)
    acc_no = "123-456"
    ticker = "TEST"
    facts = {"capex": "Large investment", "rd": "AI focused", "governance": None}

    storage.save_structuring(acc_no, ticker, facts)

    # Retrieve
    retrieved = storage.get_structuring_by_ticker("TEST")
    assert retrieved["capex"] == "Large investment"
    assert retrieved["rd"] == "AI focused"


def test_filing_exists(temp_db):
    storage = FinancialNarrativeStorage(db_path=temp_db)
    acc_no = "999-888"
    assert not storage.filing_exists(acc_no)

    metadata = {
        "accessionNumber": acc_no,
        "ticker": "SPEC",
        "cik": "000",
        "form": "10-Q",
        "filingDate": "2026-05-01",
    }
    storage.save_filing(metadata, {})
    assert storage.filing_exists(acc_no)


def test_save_filing_upsert_behavior(temp_db):
    """
    【厳しいテスト】
    同じ accessionNumber の書類を2回保存した際、
    データが重複せず、最新の内容に更新（UPSERT）されることを確認する。
    """
    storage = FinancialNarrativeStorage(db_path=temp_db)
    acc_no = "UPSERT-001"
    ticker = "TEST"

    # 1回目の保存
    metadata_v1 = {
        "accessionNumber": acc_no,
        "ticker": ticker,
        "form": "10-K",
        "filingDate": "2026-01-01",
    }
    sections_v1 = {"business": "Old Business Text"}
    storage.save_filing(metadata_v1, sections_v1)

    # 2回目の保存 (同じ accessionNumber で内容を更新)
    metadata_v2 = {
        "accessionNumber": acc_no,
        "ticker": ticker,
        "form": "10-K/A",
        "filingDate": "2026-01-02",
    }
    sections_v2 = {"business": "New Business Text", "risk": "New Risk Text"}
    storage.save_filing(metadata_v2, sections_v2)

    # 検証
    filings = storage.get_filings_by_ticker(ticker)

    # 1. 重複行が作られていないこと (1件のまま)
    assert len(filings) == 1, "UPSERTが機能しておらず、重複レコードが生成されています。"

    # 2. 内容がv2で上書きされていること
    assert filings[0][1] == "10-K/A"  # Form
    assert json.loads(filings[0][3]) == sections_v2  # Sections


def test_save_filing_invalid_metadata(temp_db):
    storage = FinancialNarrativeStorage(db_path=temp_db)
    # 必須キーが欠けているメタデータ
    invalid_metadata = {"ticker": "INVALID"}
    with pytest.raises(ValueError, match="Missing required metadata fields"):
        storage.save_filing(invalid_metadata, {})


def test_save_large_payload(temp_db):
    """極端に大きいデータを保存してもクラッシュしないか"""
    storage = FinancialNarrativeStorage(db_path=temp_db)
    metadata = {
        "accessionNumber": "HUGE-001",
        "ticker": "SPEC",
        "cik": "0",
        "form": "10-K",
        "filingDate": "2026-05-01",
    }
    sections = {"huge_content": "A" * (1024 * 1024)}  # 1MB

    storage.save_filing(metadata, sections)

    filings = storage.get_filings_by_ticker("SPEC")
    retrieved_sections = json.loads(filings[0][3])
    assert len(retrieved_sections["huge_content"]) == 1024 * 1024
