# DuckDB 大規模インジェスト時の強制終了 (Segmentation Fault)

## 症状
EDGAR のバルクインジェスト実行時、ログに `Saving transaction (XXXXX rows)...` と表示された直後に、Python プロセスが例外を投げずに強制終了（クラッシュ）する。

## 原因
調査の結果、以下の 2 つの要因が複合して発生する DuckDB エンジンの内部エラー（Segfault）であることが判明しました。

1. **同一バッチ内でのプライマリキー衝突 (In-batch PK Conflict)**
   SEC の `companyfacts.zip` に含まれる JSON データには、同一のプライマリキー（`ticker`, `accession_number`, `label`）を持つレコードが 1 つのファイル内に複数存在することがあります。
   DuckDB の `INSERT OR REPLACE`（UPSERT）エンジンは、1 つのバッチ（Pandas DataFrame 等）の中に重複する PK が存在する場合、それらを並列または一括で処理しようとして内部メモリ状態の競合を起こし、クラッシュすることがあります。

2. **セカンダリインデックスとの競合**
   `PRIMARY KEY` に加えて、検索用のセカンダリインデックス（`idx_us_facts_lookup` 等）が定義されているテーブルに対して大規模な `INSERT OR REPLACE` を行うと、インデックスの更新処理と UPSERT の競合により DuckDB の C++ 層でセグメンテーションフォールトが発生しやすくなる既知の不安定性があります。

## 解決策
以下の 「極限安定化対策 (Extreme Stability Measures)」 を `src/engine.py` に実装することで解決しました。

### 1. インデックスの動的制御 (Index Decoupling)
バルクインジェストのループに入る直前にセカンダリインデックスを一旦削除し、全てのデータ投入が完了した後に再構築するようにしました。
```sql
-- インジェスト開始前
DROP INDEX IF EXISTS idx_us_facts_lookup;

-- インジェスト完了後
CREATE INDEX IF NOT EXISTS idx_us_facts_lookup ON company_facts (...);
```
これにより、インジェスト中のクラッシュを完全に回避できるだけでなく、書き込み速度も大幅に向上しました。

### 2. Pandas による事前重複排除 (Pre-deduplication)
DuckDB にデータを渡す直前に、Python (Pandas) 側で同一 PK を持つレコードを排除するようにしました。
```python
df.drop_duplicates(subset=["ticker", "accession_number", "label"], keep="last", inplace=True)
```
これにより、DuckDB エンジンには「常にユニークな PK のみを持つクリーンなバッチ」が渡されるため、内部的な競合が発生しなくなりました。

### 3. サブバッチ処理 (Sub-batching)
大規模なファイル（6万〜8万行）であっても、内部的に 5,000 行ずつのサブバッチに分割して処理するようにしました。これにより、メモリ消費量を抑制し、万が一のエラー発生時も影響範囲を限定できるようにしました。
