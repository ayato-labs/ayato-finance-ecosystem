from edgar_core.config import settings
from edgar_provider.engine import USEngine


def test_settings_load():
    assert "FinancialAppAdmin" in settings.SEC_IDENTITY
    assert str(settings.FACTS_DB_PATH).endswith("facts.duckdb")


def test_engine_init():
    # This might fail in CI if no network, but let's test the class creation
    engine = USEngine()
    assert engine.facts_db == settings.FACTS_DB_PATH
    assert engine.narratives_db == settings.NARRATIVES_DB_PATH
    assert engine.compressor is not None


def test_extract_section_logic():
    engine = USEngine()
    test_md = """
# Header
## Item 1A. Risk Factors
This is a risk factor.
## Item 2. MD&A
This is MD&A.
    """
    section = engine._extract_section(test_md, [r"##\s+Item\s+1A\.?\s+Risk\s+Factors"])
    assert "Risk Factors" in section
    assert "MD&A" not in section
    assert "This is a risk factor." in section

    section_mda = engine._extract_section(test_md, [r"##\s+Item\s+2\.?\s+MD&A"])
    assert "MD&A" in section_mda
    assert "This is MD&A." in section_mda
