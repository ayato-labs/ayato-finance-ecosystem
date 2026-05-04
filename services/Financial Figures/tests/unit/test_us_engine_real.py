from src.engines.us_engine import USEngine


def test_us_engine_fetch_company_facts_real():
    """SEC APIを実際に叩いてApple(AAPL)のデータを取得できるか検証"""
    engine = USEngine()
    # USEngine.fetch_company_facts takes ticker, then resolves to CIK
    data = engine.fetch_company_facts("AAPL")

    assert data is not None
    assert "cik" in data
    # Some parts of API return CIK as int in the JSON body, or normalized string.
    assert str(data["cik"]).lstrip("0") == "320193"
    assert "facts" in data
    assert "us-gaap" in data["facts"]


def test_us_engine_sync_tickers_real():
    """SECのticker.jsonを実際に取得してDBに保存できるか検証"""
    engine = USEngine()
    # 最初の数件だけ取得するような仕組みはないが、実行してカウントが返るか確認
    count = engine.sync_tickers(session_id="test_unit")
    assert count > 0


def test_us_engine_invalid_cik():
    """存在しないCIKでの挙動"""
    engine = USEngine()
    # 9999999999 is likely invalid
    data = engine.fetch_company_facts("9999999999")
    assert data is None
