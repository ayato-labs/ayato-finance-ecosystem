# ADR-0004: Comprehensive Refactoring, Schema Migration, and Pipeline Optimization

- **Date**: 2026-06-06
- **Status**: Accepted
- **Deciders**: ayato-labs, Antigravity (AI Agent)

## Context

5年間のEDINETバックフィル（推定18万ドキュメント、8500万ファクト）を安定かつ高速に処理し、データ利便性を最大化するため、現状の224日分の蓄積データおよびコードベースを監査した。結果、以下の重大な課題が特定された：

1.  **データアクセスの阻害（BLOB）**: 叙述テキスト（`content_md`）がPython側でzstd圧縮された `BLOB` として保存されており、SQL（`LIKE`, `LENGTH`, 全文検索等）での直接クエリが不可能。読み込みパスも実装されていない。
2.  **ストレージの無駄（3.4 GB超）**: レガシーな非同期/同期パイプライン（`async_pipeline.py`, `pipeline.py`）が残存し、それぞれ独自のスキーマで `facts_mcp.duckdb` (3.28 GB) などの重複データベースファイルを生成している。
3.  **スループットの直列化ボトルネック**: RateLimiterが同期用の `threading.Lock` の内部で `time.sleep()` を実行しているため、マルチスレッドのダウンロード処理が直列化され、実効スループットが理論値の1/3に低下している。
4.  **リソースリーク・運用の不安定さ**: WALファイルの明示的チェックポイントがなく肥大化リスクがある点、ライターのQueueサイズが無制限である点、`manifest.py` が接続マネージャーをバイパスして直接接続しロック競合を起こすリスクがある点など。

## Decision

上記の課題をすべて解消するため、以下のリファクタリング、スキーマ移行、および最適化を全面的に実施する。

### 1. 叙述テキスト（Narratives）の VARCHAR 移行とマイグレーション
- `narratives.content_md` を `BLOB` から `VARCHAR` に変更する。
- 既存データ移行スクリプト（`scripts/migrate_blob_to_varchar.py`）を作成し、既存の2,592,157行のBLOBをPython側で展開して `VARCHAR` カラムに書き換える。
- DuckDBは内部でネイティブのZSTD圧縮（`VARCHAR USING COMPRESSION ZSTD` 相当）を自動適用するため、ディスクサイズ増加を最小限（推定サイズ増加率 +5%以下）に抑えつつ、SQLからキャストなしでテキストデータを操作可能とする。
- Pydanticモデル（`NarrativeBlock.content_md: str`）とDBスキーマの型整合性を復元する。

### 2. レガシーコード・重複データベースの完全クリーンアップ
- 以下のレガシーファイルを物理削除する：
  - `src/datalake/service/async_pipeline.py`
  - `src/datalake/service/pipeline.py`
- 以下の孤立・重複したデータベースファイルをディスクから削除する（合計約3.45 GB）：
  - `data/datalake/facts_mcp.duckdb`
  - `data/datalake/facts_tools.duckdb`
  - `data/datalake/facts_csv.duckdb`
  - `data/database/edinet_database.duckdb`（`edinet_master.duckdb` と完全重複するレガシーコピー）

### 3. スループットとリソース管理の最適化
- **RateLimitManagerの改善**: ロック取得は状態の読み取りと更新時のみに限定し、`time.sleep()` はロック外で実行するスレッドセーフな非ブロッキング構造に書き換える。
- **WALチェックポイント**: `DuckDBManager` に `CHECKPOINT` 発行メソッドを追加し、ライターでの永続化後および `JPEDINETEngine` の `VACUUM` 実行前に明示的に呼び出す。
- **ライターバックプレッシャー**: `DatabaseWriter` のQueueに `maxsize=500` の上限を設定し、書き込み遅延が発生した際にパース側を一時停止させ、メモリ肥大化を防止する。
- **マニフェスト接続の統合**: `manifest.py` を `DuckDBManager` を経由する形に書き換え、DBロック競合のリスクを排除する。

### 4. コード衛生の向上
- `contracts.py` の `FiscalPeriod` に欠落していた `Q4` を追加する。
- `trace.py` と `tracing.py` の重複トレースロジックを `trace.py` に一本化し、`tracing.py` を削除する。
- `ensemble_parser.py` 内に残存していたデバッグ用JSONダンプ出力を削除する。
- `governance.py`（未使用）と `psutil` 依存ライブラリを削除する。

## Consequences

### Positive
- **クエリ利便性の飛躍的向上**: 叙述データをDuckDB上で直接テキスト検索（`LIKE '%リスク%'` 等）可能になり、NLP分析の前処理が劇的に簡略化される。
- **ディスク容量の大幅削減**: 不要・レガシーなDBファイルを一掃することで、ディスク使用量を約11 GBから約6.2 GB（約44%削減）まで圧縮。
- **並列処理性能の最大化**: レートリミッタのロックフリー化により、ダウンロードスレッド（最大3）が真に並列で動作し、バックフィル完了時間を90時間から推定19〜25時間へと短縮。
- **メモリ安全性と堅牢性の向上**: キュー制限によるバックプレッシャー制御、チェックポイントによるWALの安全なクローズ、および単一接続マネージャーによるロック競合防止。

### Negative / Risks
- **移行時のダウンタイム**: BLOBからVARCHARへの260万行のマイグレーション実行中（推定10〜20分）、DuckDBが排他ロックされるため、インジェスト処理を停止する必要がある。
- **過去データ移行の手間**: スキーマ移行スクリプトを安全に実装し、バッチ処理でエラーを検知・ログ出力する必要がある。

## References
- 改善計画: [implementation_plan.md](file:///C:/Users/saiha/.gemini/antigravity/brain/608a4fee-6e1a-43e2-90e5-030bdd2f3018/implementation_plan.md)
- 関連コンポーネント:
  - `src/datalake/service/writer.py`
  - `src/datalake/service/ingestor.py`
  - `src/datalake/shared/infra/db.py`
  - `src/datalake/shared/infra/rate_limit.py`
  - `src/datalake/shared/infra/manifest.py`
  - `src/datalake/shared/domain/contracts.py`
