# トラブルシューティング：一括インジェスト中のDuckDB Cレベル・セグメンテーションフォールト

## 症状
EDGARの一括インジェスト（Bulk ZIPのパース）実行中に、Pythonプロセスが突然終了し、Pythonのトレースバックが表示されずに「Press any key to continue...」やCレベルのセグメンテーションフォールトが発生する。通常、数百件から数千件のバッチを処理した後に発生する。

## 環境
- OS: Windows
- DB: DuckDB
- データライブラリ: Pandas / PyArrow

## 原因
**UPSERT実行中のDuckDB ARTインデックスの破損**
根本原因は、Windows版DuckDBのART（Adaptive Radix Tree）インデックスの実装におけるバグである。**セカンダリインデックス**（例：`idx_filings_ticker`）が存在するテーブルに対して、高スループットな `INSERT OR REPLACE`（UPSERT）操作を行うと、DuckDB内部のインデックス用メモリ再割り当てに失敗し、メモリアクセス違反（セグメンテーションフォールト）を引き起こす。

また、Arrowテーブルのインメモリ登録（`conn.register`）を直接使用すると、PythonのガベージコレクションとDuckDBの内部スレッドプールの間でポインタの競合が発生し、不安定さを助長する場合がある。

## 解決策

### 1. インデックスのライフサイクル管理
バルク・インジェストを開始する前に、対象テーブルのすべてのセカンダリインデックスを削除（DROP）する。インデックスの再作成は、インジェストが完全に完了した後に行う。
```sql
-- インジェスト前
DROP INDEX IF EXISTS idx_filings_ticker;
DROP INDEX IF EXISTS idx_us_facts_lookup;

-- インジェスト完了後
CREATE INDEX IF NOT EXISTS idx_filings_ticker ON filings (ticker);
CREATE INDEX IF NOT EXISTS idx_us_facts_lookup ON company_facts (accession_number, fiscal_year, fiscal_period);
```

### 2. 物理ステージング（Parquet経由）
メモリポインタの競合を排除するため、データを一度Parquetファイルとしてディスクにシリアライズし、DuckDBの `read_parquet()` 関数を使用してロードする。これにより、DuckDBのC++エンジンがPythonのオブジェクト・ライフサイクルから独立してファイルI/Oを処理できるようになる。

### 3. 書き込みの直列化（Producer-Consumer パターン）
DuckDBへの書き込み専用のバックグラウンドスレッドを用意し、直列実行を保証する。スレッドセーフなキュー（`queue.Queue`）にサイズ制限（バックプレッシャー）を設けることで、解析スレッド（Producer）が書き込みスレッド（Consumer）を圧倒してメモリを枯渇させるのを防ぐ。

### 4. 定期的なチェックポイントの実行
5〜10バッチごとに `PRAGMA checkpoint;` を実行し、先行書き込みログ（WAL）をフラッシュしてメモリ使用量を安定させる。

## 予防策
- **DuckDBにおいて、セカンダリインデックスが有効な状態で大量のUPSERTを行わないこと。**
- 大規模なデータセットの場合は、直接のArrow登録よりも `read_parquet` や `read_csv` を優先すること。
- 複数のスレッドでデータをパースして単一のDuckDBに書き込む場合は、必ずシリアルライター（直列書き込みスレッド）を実装すること。
