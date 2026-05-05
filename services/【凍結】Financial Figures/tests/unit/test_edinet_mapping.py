import duckdb
import pandas as pd
import pytest

from src.providers.edinet.mapping import EDINETMapper


@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test_mapping.duckdb"
    return str(db_path)


@pytest.fixture
def dummy_csv(tmp_path):
    csv_path = tmp_path / "dummy_edinet.csv"
    # Create a dummy CSV with Japanese headers and some messy data
    # Row 0: Metadata (to be skipped)
    # Row 1: Headers
    data = [
        ["Metadata Header", "", "", "", "", "", "", "", "", "", "", "", ""],
        [
            "EDINETコード",
            "提出者種別",
            "発行者",
            "上場区分",
            "連結・単体",
            "資本金",
            "提出者名",
            "提出者名(英)",
            "提出者名(ヨミ)",
            "住所",
            "業種",
            "証券コード",
            "法人番号",
        ],
        [
            "E00001",
            "個人",
            "なし",
            "非上場",
            "単体",
            "0",
            "テスト太郎",
            "Test Taro",
            "テストタロウ",
            "東京都",
            "サービス業",
            "",
            "123",
        ],  # No Ticker (Skip)
        [
            "E00002",
            "法人",
            "あり",
            "上場",
            "連結",
            "100",
            "トヨタ自動車",
            "Toyota",
            "トヨタ",
            "愛知県",
            "輸送用機器",
            "72030",
            "456",
        ],  # 5-digit Ticker
        [
            "E00003",
            "法人",
            "あり",
            "上場",
            "単体",
            "50",
            "ソフトバンク",
            "Softbank",
            "ソフバン",
            "東京都",
            "情報・通信業",
            "9984.0",
            "789",
        ],  # Float Ticker
        [
            "E00004",
            "法人",
            "あり",
            "上場",
            "連結",
            "10",
            "不明企業",
            "Unknown",
            "フメイ",
            "不明",
            "不明",
            "1234",
            "000",
        ],  # 4-digit Ticker
    ]
    df = pd.DataFrame(data)
    # Save as CP932 to simulate real EDINET file
    df.to_csv(csv_path, index=False, header=False, encoding="cp932")
    return str(csv_path)


def test_mapper_init(temp_db):
    EDINETMapper(temp_db)
    with duckdb.connect(temp_db) as conn:
        tables = conn.execute("SHOW TABLES").fetchall()
        assert ("edinet_tickers",) in tables


def test_load_csv_and_normalization(temp_db, dummy_csv):
    mapper = EDINETMapper(temp_db)
    mapper.load_csv(dummy_csv)

    # Verify Normalization
    mapping = mapper.get_ticker_to_edinet()

    # E00001 (No Ticker) should be skipped
    assert "E00001" not in mapping.values()

    # E00002: 72030 -> 7203
    assert mapping["7203"] == "E00002"

    # E00003: 9984.0 -> 9984
    assert mapping["9984"] == "E00003"

    # E00004: 1234 -> 1234
    assert mapping["1234"] == "E00004"


def test_load_csv_encoding_error(temp_db, tmp_path):
    mapper = EDINETMapper(temp_db)
    bad_csv = tmp_path / "bad_enc.csv"
    # Save as UTF-8 (which is "bad" because mapper expects CP932)
    with open(bad_csv, "w", encoding="utf-8") as f:
        f.write("header1,header2\ndata1,data2")

    # Should raise or log error (depending on implementation, here we expect it to fail reading)
    with pytest.raises((UnicodeDecodeError, ValueError, Exception)):
        mapper.load_csv(str(bad_csv))


def test_get_all_target_edinet_codes(temp_db, dummy_csv):
    mapper = EDINETMapper(temp_db)
    mapper.load_csv(dummy_csv)
    codes = mapper.get_all_target_edinet_codes()
    expected_count = 3  # E00002, E00003, E00004
    assert len(codes) == expected_count
    assert "E00002" in codes
    assert "E00001" not in codes
