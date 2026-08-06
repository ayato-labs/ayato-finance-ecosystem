# フローチャート図 - EDGAR Sync & Repair Logic

SEC EDGAR 提出書類の差分同期・修復ロジックの全体フローを示します。
データの「完全性（Completeness）」を担保するための論理パスと、バッチ処理によるパフォーマンス最適化を含みます。

---

## 1. 全体構成

4つのエントリポイントから同一の差分判定ロジックが共有されます。

```
CLI (main.py)
  ├── sync       → sync_recent_us_filings()   # Daily Index ベルク同期
  ├── ticker     → process_us_tickers()        # ティッカー個別同期
  ├── repair-facts → repair_all_missing_facts() # 欠損Facts自動修復
  └── stats      → storage.get_stats()         # DB統計情報表示
```

---

## 2. 共通ロジック: 差分判定（Smart Repair）

`sync_recent_us_filings` と `process_us_tickers` の両方で使用される、
提出書類ごとの差分更新判定フローです。

```mermaid
graph TD
    Start(["書類を1件処理"]) --> CheckTicker{"ティッカーは解決できるか?"}

    CheckTicker -- No --> SkipUnknown["スキップ: UNKNOWN ティッカー"]
    SkipUnknown --> End(["処理終了"])

    CheckTicker -- Yes --> CheckFiling{"filing_exists?"}

    CheckFiling -- False --> NeedsFullSync["needs_full_sync = True"]
    CheckFiling -- True --> CheckFacts{"facts_exist?"}

    CheckFacts -- False --> NeedsFactsRepair["needs_facts_repair = True"]
    CheckFacts -- True --> SkipBoth["スキップ: 完全なデータ"]

    NeedsFullSync --> FullSyncPath
    NeedsFactsRepair --> FactsRepairPath
    SkipBoth --> End

    subgraph FullSyncPath ["Full Sync パス"]
        direction TB
        FS1["メタデータ解決: resolve_filing_metadata"] --> FS2{"解決できたか?"}
        FS2 -- No --> FSSkip(["その書類をスキップ"])
        FS2 -- Yes --> FS3["HTML書類をダウンロード (SEC制限: 0.11s待機)"]
        FS3 --> FS4{"HTTP 200?"}
        FS4 -- No --> FSDel["resp削除"]
        FS4 -- Yes --> FS5["パース: extract_all_sections (定性テキスト抽出)"]
        FS5 --> FS6{"sections があるか?"}
        FS6 -- No --> FSDel
        FS6 -- Yes --> FS7["データ整合性検証: _validate_filing"]
        FS7 --> FS8{"バリデーション成功?"}
        FS8 -- No --> FSDel
        FS8 -- Yes --> FS9["filings_buffer に追加"]
        FS9 --> FS10{"buffer >= BATCH_SIZE?"}
        FS10 -- No --> FSDel2(["後述のFacts処理へ"])
        FS10 -- Yes --> FS11["save_filings_batch + bufferクリア"]
        FS11 --> FSDel2
        FSDel --> FSDel2
    end

    subgraph FactsRepairPath ["Facts 修復パス"]
        direction TB
        FR1["EdgarQuantitative.extract_facts (XBRLから財務数値を抽出)"] --> FR2{"DataFrame が空でないか?"}
        FR2 -- No --> FR3(["Facts なし - スキップ"])
        FR2 -- Yes --> FR3a["_derive_fiscal_period (会計四半期決定)"]
        FR3a --> FR4["_validate_facts (データ整合性検証)"]
        FR4 --> FR5{"バリデーション成功?"}
        FR5 -- No --> FR3
        FR5 -- Yes --> FR6["facts_buffer に追加"]
        FR6 --> FR7{"buffer >= BATCH_SIZE?"}
        FR7 -- No --> FR8(["処理終了"])
        FR7 -- Yes --> FR9["save_facts_batch + bufferクリア"]
        FR9 --> FR8
    end

    FullSyncPath --> FactsRepairPath
    FSDel2 --> FactsRepairPath

    style NeedsFullSync fill:#fff9c4,stroke:#fbc02d
    style NeedsFactsRepair fill:#e1f5fe,stroke:#01579b
    style SkipBoth fill:#c8e6c9,stroke:#2e7d32
    style SkipUnknown fill:#f5f5f5,stroke:#9e9e9e
```

---

## 3. sync_recent_us_filings（Daily Index ベルク同期）

SEC Daily Index を使用して、米国上場企業全体の提出書類を日単位で遡及同期します。

```mermaid
graph TD
    SyncStart(["sync 開始"]) --> InitBuffers["バッファ初期化: filings_buffer, facts_buffer"]
    InitBuffers --> DayLoop{"range days の各日付"}

    DayLoop -- 完了 --> FlushFinal["残バッファを一括書き込み"]
    FlushFinal --> SyncEnd(["同期完了"])

    DayLoop -- 次の日 --> CalcDate["target_date = today - i 日"]
    CalcDate --> FetchIndex["SEC Daily Index 取得: list_daily_filings"]

    FetchIndex --> IndexExist{"提出書類があるか?"}
    IndexExist -- No --> NextDay(["次の日へ (休日・祝日)"])
    IndexExist -- Yes --> FilingLoop{"各書類を処理"}

    FilingLoop -- 完了 --> DailySummary["日次サマリー出力: processed / skipped"]
    DailySummary --> NextDay

    FilingLoop -- 次の書類 --> DifferentialCheck{"差分判定 (共通ロジック)"}

    DifferentialCheck -- Skip --> DailySkip["daily_skipped += 1"]
    DifferentialCheck -- FullSync --> FullSyncProc["Full Sync 実行"]
    DifferentialCheck -- FactsRepair --> FactsRepairProc["Facts 修復実行"]

    DailySkip --> FilingLoop
    FullSyncProc --> FilingLoop
    FactsRepairProc --> FilingLoop

    style DifferentialCheck fill:#e8eaf6,stroke:#3f51b5
    style DailySummary fill:#c8e6c9,stroke:#2e7d32
```

---

## 4. process_us_tickers（ティッカー個別同期）

指定したティッカーシンボル群について、直近の提出書類をピンポイントで同期します。

```mermaid
graph TD
    TickerStart(["ticker 開始"]) --> InitBuffers["バッファ初期化: filings_buffer, facts_buffer"]
    InitBuffers --> ThresholdDate["基準日付を計算: threshold_date = today - days"]
    ThresholdDate --> TickerLoop{"各ティッカーを処理"}

    TickerLoop -- 完了 --> FlushFinal["残バッファを一括書き込み"]
    FlushFinal --> TickerEnd(["同期完了"])

    TickerLoop -- 次のティッカー --> FetchSubs["提出履歴メタデータ取得: get_latest_submissions"]

    FetchSubs --> SubsExist{"データがあるか?"}
    SubsExist -- No --> WarnNoSubs["WARNING: データなし"]
    SubsExist -- Yes --> FilterFilings["10-K, 10-Q にフィルタ: filter_relevant_filings"]

    FilterFilings --> HasRelevant{"対象書類があるか?"}
    HasRelevant -- No --> WarnNoFiling["WARNING: 対象なし"]
    HasRelevant -- Yes --> ApplyThreshold["基準日付でフィルタ: filingDate >= threshold"]

    ApplyThreshold --> LogFound["件数ログ出力: total / in_range"]
    LogFound --> FilingLoop2{"対象書類を処理"}

    FilingLoop2 -- 完了 --> TickerSummary["ティッカーごとサマリー: processed / skipped"]
    TickerSummary --> NextTicker(["次のティッカーへ"])
    WarnNoSubs --> NextTicker
    WarnNoFiling --> NextTicker

    FilingLoop2 -- 次の書類 --> DifferentialCheck{"差分判定 (共通ロジック)"}

    DifferentialCheck -- Skip --> TickerSkip["skipped_count += 1"]
    DifferentialCheck -- FullSync --> FullSyncProc["Full Sync 実行"]
    DifferentialCheck -- FactsRepair --> FactsRepairProc["Facts 修復実行"]

    TickerSkip --> FilingLoop2
    FullSyncProc --> FilingLoop2
    FactsRepairProc --> FilingLoop2

    style DifferentialCheck fill:#e8eaf6,stroke:#3f51b5
    style TickerSummary fill:#c8e6c9,stroke:#2e7d32
```

---

## 5. repair_all_missing_facts（Facts 自動修復）

データベース内の全レコードを走査し、定性データはあるが定量データ（Facts）が
欠落しているレコードを検出し、自動的に XBRL データを再抽出して修復します。

```mermaid
graph TD
    RepairStart(["repair-facts 開始"]) --> QueryGaps["LEFT JOIN で Facts が欠落している accession_number を抽出"]
    QueryGaps --> LogFound["検出件数をログ出力"]
    LogFound --> InitBuffer["バッファ初期化: facts_buffer"]
    InitBuffer --> TargetLoop{"各対象を処理"}

    TargetLoop -- 完了 --> FlushFinal["残バッファを一括書き込み"]
    FlushFinal --> RepairEnd(["修復完了"])

    TargetLoop -- 次の対象 --> ExtractFacts["EdgarQuantitative.extract_facts (XBRLから財務数値を抽出)"]

    ExtractFacts --> FactsEmpty{"DataFrame が空か?"}
    FactsEmpty -- Yes --> WarnNoFacts["WARNING: Facts なし"]
    FactsEmpty -- No --> DerivePeriod["_derive_fiscal_period (会計四半期決定)"]
    DerivePeriod --> ValidateFacts["_validate_facts (データ整合性検証)"]
    ValidateFacts --> ValidCheck{"バリデーション成功?"}
    ValidCheck -- No --> WarnNoFacts
    ValidCheck -- Yes --> AppendBuffer["facts_buffer に追加"]

    AppendBuffer --> CheckBatch{"buffer >= BATCH_SIZE?"}
    CheckBatch -- No --> SleepWait["0.1s 待機"]
    CheckBatch -- Yes --> FlushBatch["save_facts_batch + bufferクリア"]

    SleepWait --> TargetLoop
    FlushBatch --> TargetLoop
    WarnNoFacts --> SleepWait

    style ExtractFacts fill:#e1f5fe,stroke:#01579b
    style DerivePeriod fill:#e1f5fe,stroke:#01579b
    style ValidateFacts fill:#e1f5fe,stroke:#01579b
    style FlushBatch fill:#c8e6c9,stroke:#2e7d32
```

---

## 6. バッチバッファの仕組み

3つの関数すべてで共通して使用される、メモリ上的バッファリングと一括書き込みの仕組みです。

```
  処理対象 N 件
       │
       ▼
  ┌─────────────┐
  │  バッファに   │  filings_buffer: (metadata, sections)
  │  追加        │  facts_buffer: (ticker, acc_no, facts_df)
  └──────┬──────┘
         │
         ▼
  ┌─────────────────┐
  │ len(buffer) >=   │  BATCH_SIZE（.env で設定、デフォルト: 10）
  │ BATCH_SIZE ?     │
  └────┬───────┬────┘
       │ Yes   │ No
       ▼       ▼
  ┌─────────┐  ┌──────────┐
  │ 一括保存 │  │ 次の件を  │
  │ + クリア  │  │ 追加      │
  └─────────┘  └──────────┘

  処理完了後:
    残バッファが存在すれば一括保存（Final Flush）
```

---

## 7. DB テーブル構造

差分判定に使用されるテーブルとメソッドの対応です。

| メソッド | クエリ対象テーブル | 判定内容 |
|---|---|---|
| `filing_exists(acc_no)` | `filings` | 書類メタデータの存在有無 |
| `facts_exist(acc_no)` | `company_facts` | 財務数値データの存在有無 |
| `get_accession_numbers_needing_repair()` | `filings LEFT JOIN company_facts` | メタデータはあるが Facts が欠落 |

### テーブル定義

**1. `filings` テーブル**
```sql
CREATE TABLE filings (
    accession_number VARCHAR PRIMARY KEY,
    ticker VARCHAR,
    cik VARCHAR,
    form VARCHAR,           -- "10-K", "10-Q"
    filing_date DATE,
    metadata JSON,          -- SECメタデータ全体
    updated_at TIMESTAMP
);
```

**2. `filing_sections` テーブル**
```sql
CREATE TABLE filing_sections (
    section_id VARCHAR PRIMARY KEY,  -- MD5(accession_number|section_name)
    accession_number VARCHAR,
    section_name VARCHAR,
    content_md TEXT,                  -- セクション本文
    updated_at TIMESTAMP
);
```

**3. `company_facts` テーブル**
```sql
CREATE TABLE company_facts (
    fact_id VARCHAR PRIMARY KEY,  -- MD5(ticker|accession_number|concept|period_start|period_end|period_instant)
    accession_number VARCHAR,
    ticker VARCHAR,
    concept VARCHAR,              -- XBRL概念名
    label VARCHAR,
    value DOUBLE,                 -- 数値
    unit VARCHAR,
    fiscal_year INTEGER,
    fiscal_period VARCHAR,        -- "Q1", "Q2", "Q3", "Q4", "FY"
    period_start DATE,
    period_end DATE,
    period_instant DATE
);
```

### インデックス

| インデックス名 | 対象カラム | 用途 |
|---|---|---|
| `idx_edgar_facts_lookup` | (ticker, concept, period_end) | 財務データ検索用 |
| `idx_edgar_sections_lookup` | (accession_number, section_name) | セクション検索用 |

---

## 8. エラーハンドリング方針

| レベル | 方法 | 例 |
|--------|------|-----|
| ネットワークエラー | 指数バックオフリトライ | `_request_with_retry()`（max_retries=5） |
| レート制限（429） | 指数バックオフ + ランダムウェイト | `(2^attempt) + random(0,1)` |
| データ整合性エラー | `DataIntegrityError`例外 | `_validate_filing()`, `_validate_facts()` |
| 個別書類処理エラー | 例外キャッチ+ログ+continue | pipeline.py内のループ処理 |
| バッチ保存エラー | 個別キャッチ+スキップ | `save_filings_batch()`内のtry-except |
| HTTPエラー（200以外） | ダウンロードスキップ | `fetch_filing_content()` |
| メタデータ解決失敗 | その書類をスキップ | `resolve_filing_metadata()` |

### データ整合性検証

**`_validate_filing()`**: 書類メタデータとセクションの検証
- 必須フィールドチェック: `accessionNumber`, `ticker`, `form`, `filingDate`
- セクション空チェック
- テキスト量チェック: 合計100文字以上

**`_validate_facts()`**: 財務数値データの検証
- DataFrame空チェック
- 必須カラムチェック: `concept`, `numeric_value`

### SEC API制限への対応

1. **リクエスト間隔制御**
   - sync/ticker: `asyncio.sleep(0.11)` （約9リクエスト/秒）
   - repair-facts: `asyncio.sleep(0.1)` （10リクエスト/秒）

2. **User-Agent設定**（SEC規約準拠）
   ```
   USER_AGENT="edgar-provider/1.0 (contact: admin@example.com)"
   ```

---

## 9. 環境変数設定

| 変数名 | デフォルト | 説明 |
|--------|-----------|------|
| `BATCH_SIZE` | 10 | バッチバッファサイズ |
| `USER_AGENT` | "edgar-provider/1.0 (contact: admin@example.com)" | SEC User-Agent |
| `SEC_IDENTITY` | "UnknownAdmin admin@example.com" | SEC連絡先 |
| `EDGAR_DATA_DIR` | "finance/data/edgar/edgar.duckdb" | DuckDBパス |
| `DUCKDB_MEMORY_LIMIT` | 2GB | DuckDBメモリ制限 |
| `DUCKDB_THREADS` | 4 | DuckDB並列スレッド数 |
| `DUCKDB_CHECKPOINT_THRESHOLD` | 1GB | チェックポイント閾値 |
