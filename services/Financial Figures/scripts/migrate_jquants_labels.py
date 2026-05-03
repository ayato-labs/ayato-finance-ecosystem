import logging

import duckdb

from src.core.config import settings


def migrate_labels():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("Migration")

    jp_db = settings.DB_PATH_JP
    if not jp_db.exists():
        logger.error(f"Database not found: {jp_db}")
        return

    # Mapping dictionary: V1 (Short) -> V2 (Long/Standard)
    # Based on J-Quants V1 field names and V2 canonical targets
    MAPPING = {
        "Sales": "NetSales",
        "OP": "OperatingProfit",
        "OdP": "OrdinaryProfit",
        "NP": "Profit",
        "EPS": "EarningsPerShare",
        "TA": "TotalAssets",
        "Eq": "NetAssets",
        "EqAR": "EquityToAssetRatio",
        "BPS": "BookValuePerShare",
        # Forecasts (Using a prefix 'Forecast' for clarity in the unified schema)
        "FSales": "ForecastNetSales",
        "FOP": "ForecastOperatingProfit",
        "FOdP": "ForecastOrdinaryProfit",
        "FNP": "ForecastProfit",
        "FEPS": "ForecastEarningsPerShare",
        # 2Q Forecasts
        "FSales2Q": "ForecastNetSales2Q",
        "FOP2Q": "ForecastOperatingProfit2Q",
        "FOdP2Q": "ForecastOrdinaryProfit2Q",
        "FNP2Q": "ForecastProfit2Q",
        "FEPS2Q": "ForecastEarningsPerShare2Q",
    }

    logger.info(f"Starting migration for {jp_db.name}...")

    try:
        conn = duckdb.connect(str(jp_db))

        # 1. Backup check (Optional but recommended)
        count_before = conn.execute("SELECT count(*) FROM company_facts").fetchone()[0]
        logger.info(f"Total records before migration: {count_before:,}")

        # 2. Execute Updates
        updated_total = 0
        for v1, v2 in MAPPING.items():
            conn.execute("UPDATE company_facts SET label = ? WHERE label = ?", (v2, v1))
            logger.info(f"  [UPDATE] {v1:10} -> {v2:25}")

        logger.info(f"Migration completed. Total records updated: {updated_total:,}")
        conn.close()

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)


if __name__ == "__main__":
    migrate_labels()
