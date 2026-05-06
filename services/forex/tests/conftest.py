import pytest


@pytest.fixture
def temp_forex_dir(tmp_path):
    d = tmp_path / "forex_data"
    d.mkdir()
    yield str(d)
