# Centralized Schema Registry (SSoT)
# Each database shard has its own set of tables with versions.

TABLE_SCHEMAS: dict[str, dict[str, dict[str, str]]] = {
    "traceability": {
        "sync_sessions": {
            "v1": """
                CREATE TABLE sync_sessions (
                    session_id VARCHAR PRIMARY KEY,
                    market VARCHAR,
                    status VARCHAR,
                    started_at TIMESTAMP,
                    ended_at TIMESTAMP,
                    records_processed INTEGER,
                    errors_count INTEGER,
                    error_log VARCHAR,
                    git_commit_hash VARCHAR
                )
            """
        },
        "mapping_audit": {
            "v1": """
                CREATE TABLE mapping_audit (
                    mapping_id VARCHAR PRIMARY KEY,
                    session_id VARCHAR,
                    source_tag VARCHAR,
                    mapped_label VARCHAR,
                    reasoning VARCHAR,
                    confidence_score DOUBLE,
                    mapped_at TIMESTAMP,
                    llm_model_version VARCHAR
                )
            """
        },
        "sync_progress": {
            "v1": """
                CREATE TABLE sync_progress (
                    market VARCHAR,
                    symbol VARCHAR,
                    last_synced_at TIMESTAMP,
                    records_in_last_sync INTEGER,
                    status VARCHAR,
                    PRIMARY KEY(market, symbol)
                )
            """
        },
    },
    "us": {
        "tickers": {
            "v1": """
                CREATE TABLE tickers (
                    ticker VARCHAR PRIMARY KEY,
                    cik VARCHAR,
                    name VARCHAR,
                    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_session_id VARCHAR
                )
            """
        },
        "company_facts": {
            "v1": """
                CREATE TABLE company_facts (
                    fact_id VARCHAR PRIMARY KEY,
                    cik VARCHAR,
                    taxonomy VARCHAR,
                    tag VARCHAR,
                    label VARCHAR,
                    unit VARCHAR,
                    value DOUBLE,
                    end_date DATE,
                    fiscal_year INTEGER,
                    fiscal_period VARCHAR,
                    form VARCHAR,
                    filed_date DATE,
                    accession_number VARCHAR,
                    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    session_id VARCHAR
                )
            """
        },
    },
    "jp": {
        "tickers": {
            "v1": """
                CREATE TABLE tickers (
                    code VARCHAR PRIMARY KEY,
                    name VARCHAR,
                    market_section VARCHAR,
                    sector VARCHAR,
                    last_session_id VARCHAR
                )
            """
        },
        "company_facts": {
            "v1": """
                CREATE TABLE company_facts (
                    DisclosedDate DATE,
                    DisclosedTime VARCHAR,
                    LocalCode VARCHAR,
                    DisclosureNumber VARCHAR,
                    Type VARCHAR,
                    FiscalYear VARCHAR,
                    FiscalPeriod VARCHAR,
                    NetSales VARCHAR,
                    OperatingProfit VARCHAR,
                    OrdinaryProfit VARCHAR,
                    Profit VARCHAR,
                    EarningsPerShare VARCHAR,
                    TotalAssets VARCHAR,
                    NetAssets VARCHAR,
                    Equity VARCHAR,
                    EquityToAssetRatio VARCHAR,
                    BookValuePerShare VARCHAR,
                    CashFlowsFromOperatingActivities VARCHAR,
                    CashFlowsFromInvestingActivities VARCHAR,
                    CashFlowsFromFinancingActivities VARCHAR,
                    CashAndCashEquivalents VARCHAR,
                    ResultForecastNetSales VARCHAR,
                    ResultForecastOperatingProfit VARCHAR,
                    ResultForecastOrdinaryProfit VARCHAR,
                    ResultForecastProfit VARCHAR,
                    ResultForecastEPS VARCHAR,
                    session_id VARCHAR,
                    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (LocalCode, DisclosedDate, DisclosureNumber)
                )
            """,
            "v2": """
                CREATE TABLE company_facts (
                    DisclosedDate DATE,
                    DisclosedTime VARCHAR,
                    LocalCode VARCHAR,
                    DisclosureNumber VARCHAR,
                    Type VARCHAR,
                    FiscalYear VARCHAR,
                    FiscalPeriod VARCHAR,
                    NetSales DOUBLE,
                    OperatingProfit DOUBLE,
                    OrdinaryProfit DOUBLE,
                    Profit DOUBLE,
                    EarningsPerShare DOUBLE,
                    TotalAssets DOUBLE,
                    NetAssets DOUBLE,
                    Equity DOUBLE,
                    EquityToAssetRatio DOUBLE,
                    BookValuePerShare DOUBLE,
                    CashFlowsFromOperatingActivities DOUBLE,
                    CashFlowsFromInvestingActivities DOUBLE,
                    CashFlowsFromFinancingActivities DOUBLE,
                    CashAndCashEquivalents DOUBLE,
                    ResultForecastNetSales DOUBLE,
                    ResultForecastOperatingProfit DOUBLE,
                    ResultForecastOrdinaryProfit DOUBLE,
                    ResultForecastProfit DOUBLE,
                    ResultForecastEPS DOUBLE,
                    session_id VARCHAR,
                    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (LocalCode, DisclosedDate, DisclosureNumber)
                )
            """,
        },
    },
    "edinet_raw": {
        "documents": {
            "v1": """
                CREATE TABLE documents (
                    doc_id VARCHAR PRIMARY KEY,
                    ticker VARCHAR,
                    filer_name VARCHAR,
                    doc_description VARCHAR,
                    submission_date DATE,
                    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
        },
        "raw_facts": {
            "v1": """
                CREATE TABLE raw_facts (
                    doc_id VARCHAR,
                    element_id VARCHAR,
                    element_name VARCHAR,
                    context_id VARCHAR,
                    amount_value DOUBLE,
                    unit_name VARCHAR,
                    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
                )
            """
        }
    },
    "edinet_norm": {
        "company_facts": {
            "v1": """
                CREATE TABLE company_facts (
                    DisclosedDate DATE,
                    LocalCode VARCHAR,
                    FiscalYear VARCHAR,
                    FiscalPeriod VARCHAR,
                    NetSales DOUBLE,
                    OperatingProfit DOUBLE,
                    OrdinaryProfit DOUBLE,
                    Profit DOUBLE,
                    EarningsPerShare DOUBLE,
                    TotalAssets DOUBLE,
                    NetAssets DOUBLE,
                    Equity DOUBLE,
                    EquityToAssetRatio DOUBLE,
                    BookValuePerShare DOUBLE,
                    CashFlowsFromOperatingActivities DOUBLE,
                    CashFlowsFromInvestingActivities DOUBLE,
                    CashFlowsFromFinancingActivities DOUBLE,
                    CashAndCashEquivalents DOUBLE,
                    accession_number VARCHAR,
                    session_id VARCHAR,
                    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (LocalCode, DisclosedDate, accession_number)
                )
            """
        },
        "reconciliation_audit": {
            "v1": """
                CREATE TABLE reconciliation_audit (
                    audit_id VARCHAR PRIMARY KEY,
                    code VARCHAR,
                    disclosed_date DATE,
                    label VARCHAR,
                    jquants_val DOUBLE,
                    edinet_val DOUBLE,
                    merged_val DOUBLE,
                    strategy VARCHAR,
                    reasoning VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
        }
    },
}

# Indexes are managed separately to allow versioned additions
INDEX_SCHEMAS: dict[str, list[str]] = {
    "traceability": [],
    "us": [
        "CREATE INDEX IF NOT EXISTS idx_us_facts_lookup ON company_facts (cik, tag, end_date)",
        "CREATE INDEX IF NOT EXISTS idx_us_tickers_symbol ON tickers (ticker)",
    ],
    "jp": [
        "CREATE INDEX IF NOT EXISTS idx_jp_tickers_symbol ON tickers (code)",
        "CREATE INDEX IF NOT EXISTS idx_jp_facts_date ON company_facts (LocalCode, DisclosedDate)",
    ],
    "edinet_raw": [
        "CREATE INDEX IF NOT EXISTS idx_facts_doc ON raw_facts(doc_id)",
        "CREATE INDEX IF NOT EXISTS idx_docs_date ON documents(submission_date)",
    ],
    "edinet_norm": [
        "CREATE INDEX IF NOT EXISTS idx_edinet_norm_lookup ON company_facts (LocalCode, DisclosedDate)",
    ],
}

# --- Documentation Generation ---

def generate_schema_docs(output_path: str = "docs/schema_definition.md"):
    """
    Generates a Markdown documentation file from the TABLE_SCHEMAS and INDEX_SCHEMAS.
    This ensures the documentation is always in sync with the Code-as-Schema.
    """
    lines = ["# Database Schema Definition (SSoT)", ""]
    lines.append("> [!NOTE]")
    lines.append("> This document is automatically generated from `src/core/schema.py`.")
    lines.append("> Do not edit this file manually.")
    lines.append("")

    for shard, tables in TABLE_SCHEMAS.items():
        lines.append(f"## Shard: `{shard}`")
        lines.append("")
        for table_name, versions in tables.items():
            lines.append(f"### Table: `{table_name}`")
            # Show the latest version DDL
            latest_version = sorted(versions.keys())[-1]
            ddl = versions[latest_version].strip()
            lines.append(f"Latest Version: `{latest_version}`")
            lines.append("```sql")
            lines.append(ddl)
            lines.append("```")
            lines.append("")

        if INDEX_SCHEMAS.get(shard):
            lines.append("### Indexes")
            lines.append("```sql")
            for idx in INDEX_SCHEMAS[shard]:
                lines.append(idx)
            lines.append("```")
            lines.append("")

        lines.append("---")
        lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Schema documentation generated at: {output_path}")


if __name__ == "__main__":
    generate_schema_docs()
