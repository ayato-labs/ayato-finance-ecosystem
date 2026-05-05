import pytest
from pathlib import Path


def test_full_sync_user_flow(mocker):
    """
    E2E Test: Runs the main CLI with mocked API calls to simulate a full user sync flow.
    """
    mocker.patch("jquantsapi.ClientV2")

    test_db = Path("data/e2e_jquants.duckdb")
    if test_db.exists():
        test_db.unlink()

    # Mock settings to use test DB
    mocker.patch("src.core.config.settings.DB_PATH", test_db)

    # Mock engine behavior
    mocker.patch("src.engine.JPEngine.sync_tickers", return_value=1)

    from main import main
    import sys

    # Simulate: python main.py --sync-tickers
    sys.argv = ["main.py", "--sync-tickers"]
    main()

    # Verify (though engine logic is mocked, this ensures main() runs without crashing)
    assert test_db.exists()

    if test_db.exists():
        test_db.unlink()


def test_hard_api_failure_handling(mocker):
    """
    Comprehensive Test: Ensure the system doesn't crash on total API blackout.
    """
    mocker.patch("jquantsapi.ClientV2", side_effect=Exception("API Down"))

    from main import main
    import sys

    sys.argv = ["main.py", "--sync-tickers"]

    # We expect SystemExit(1) now that we have a global try-except in main()
    with pytest.raises(SystemExit) as excinfo:
        main()
    assert excinfo.value.code == 1
