# フローチャート図 - EDGAR Sync & Repair Logic

SEC EDGAR 提出書類の差分同期・修復ロジックの全体フローを示します。
データの「完全性（Completeness）」を担保するための論理パスと、バッチ処理によるパフォーマンス最適化を含みます。

---

## 1. 全体構成

3つのエントリポイントから同一の差分判定ロジックが共有されます。

```
CLI (main.py)
  ├── sync       → sync_recent_us_filings()   # Daily Index ベルク同期
  ├── ticker     → process_us_tickers()        # ティッカー個別同期
  └── repair-facts → repair_all_missing_facts() # 欠損Facts自動修復
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
        FS6 -- Yes --> FS7["filings_buffer に追加"]
        FS7 --> FS8{"buffer >= BATCH_SIZE?"}
        FS8 -- No --> FSDel2(["後述のFacts処理へ"])
        FS8 -- Yes --> FS9["save_filings_batch + bufferクリア"]
        FS9 --> FSDel2
        FSDel --> FSDel2
    end

    subgraph FactsRepairPath ["Facts 修復パス"]
        direction TB
        FR1["EdgarQuantitative.extract_facts (XBRLから財務数値を抽出)"] --> FR2{"DataFrame が空でないか?"}
        FR2 -- No --> FR3(["Facts なし - スキップ"])
        FR2 -- Yes --> FR4["facts_buffer に追加"]
        FR4 --> FR5{"buffer >= BATCH_SIZE?"}
        FR5 -- No --> FR6(["処理終了"])
        FR5 -- Yes --> FR7["save_facts_batch + bufferクリア"]
        FR7 --> FR6
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
    FactsEmpty -- No --> AppendBuffer["facts_buffer に追加"]

    AppendBuffer --> CheckBatch{"buffer >= BATCH_SIZE?"}
    CheckBatch -- No --> SleepWait["0.1s 待機"]
    CheckBatch -- Yes --> FlushBatch["save_facts_batch + bufferクリア"]

    SleepWait --> TargetLoop
    FlushBatch --> TargetLoop
    WarnNoFacts --> SleepWait

    style ExtractFacts fill:#e1f5fe,stroke:#01579b
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

---

## 8. エラーハンドリング方針

- **個別書類の例外**: `try/except` で catching し、ログ出力後に次の書類へ処理を継続
- **日付単位の例外**: `try/except` で catching し、ログ出力後に次の日付へ処理を継続
- **SEC レート制限**: `asyncio.sleep(0.11)` で1秒10リクエストを遵守
- **HTTP エラー**: ステータスコードが 200 以外の場合、ダウンロードをスキップ
- **メタデータ解決失敗**: `resolve_filing_metadata` が `None` を返した場合、その書類をスキップ
