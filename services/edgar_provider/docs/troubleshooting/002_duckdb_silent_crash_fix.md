# トラブルシューティング：DuckDB バルクインジェスト中のサイレントクラッシュ

## 症状
- `main.py --bulk` の実行中、特定のバッチ（例：約5万行の保存時）でプログラムが突然終了する。
- Pythonの Traceback や例外ログが一切出力されず、終了コード（Exit Code 1）のみが残る。
- `Saving transaction...` というログの直後で停止し、後続の `Batch saved successfully.` に到達しない。

## 原因分析

### 1. DuckDB の C++ レベルでの Segmentation Fault
最大の原因は、DuckDB の **Pandas/PyArrow ゼロコピー・スキャナー** と **`INSERT OR REPLACE`（コンフリクト解消ロジック）** の組み合わせに起因するメモリ不整合です。
- ファイルベースのデータベース（`.duckdb`）に書き込む際、Pandas DataFrame のメモリを直接参照しながら同時に Primary Key の重複チェックを行うと、特定のデータパターン（NaN/Nullを含む複雑なデータ）で DuckDB の内部エンジンがセグメンテーション違反を起こし、Python プロセスごと即死していました。

### 2. 頻繁な `CHECKPOINT` による競合
当初、書き込みのたびに実行していた `conn.execute("CHECKPOINT;")` が、WAL（Write-Ahead Log）のフラッシュと進行中のトランザクション間でロック競合を引き起こし、不安定性を助長していました。

### 3. 名前衝突による `InvalidInputException`
DuckDB が SQL 内のテーブル名（例：`filings`）を、Python 側の同名のローカル変数（リスト型）と誤認し、スキャンしようとして失敗する「名前衝突」が発生していました。

## 解決策

### 1. TEMP TABLE + `conn.append` パターンの採用
データの読み取りとデータベースへの統合を物理的に分離しました。
- **読み取り**: `conn.append("temp_table", df)` を使用。これは SQL エンジンを介さず、DuckDB の `Appender` C++ API を直接叩くため、極めて高速かつ安全です。
- **統合**: DuckDB ネイティブのメモリ上にある `TEMP TABLE` から目的のテーブルへ `INSERT OR REPLACE` を実行します。これにより、メモリ参照の不整合を完全に回避しました。

### 2. 安定化 PRAGMA の導入
インジェスト開始時に以下の設定を強制し、エンジンの挙動を固定しました。
- `SET threads=1;`: 並列処理による競合を排除。
- `SET memory_limit='2GB';`: メモリ使用量を制限し、OSによるキルを防止。
- `SET wal_autocheckpoint='1GB';`: 自動チェックポイントを抑制し、WALサイズが十分に大きくなるまでディスク同期を遅延。

### 3. 変数名の明示的な分離
引数名やローカル変数を `batch_filings_list` 等にリネームし、SQL内のテーブル名と衝突しないように修正しました。

## 教訓
大規模なバルクデータ（1,000万件超）を DuckDB に流し込む際は、**「Pandas/PyArrow から直接 INSERT してはいけない」** というのが鉄則です。必ず **`Appender` API (conn.append)** を介して中間テーブルに載せてから、純粋な SQL でマージすることで、100%の安定性を確保できます。
