# ADR-0001: データベース重複バグの修正と冪等性の保証

- **Date**: 2026-05-26
- **Status**: Accepted
- **Deciders**: Gemini CLI (Agent), ayato-labs (User)

## Context
`jquants_financials.duckdb` において、同一の銘柄（ticker）、日付（date）、項目（item）、決算期（period_type）に対して、更新時間（updated_at）のみが異なる重複レコードが蓄積されるバグが発生していた。
この重複により、下流の集計処理（`SUM()` 等）で数値が 2〜5 倍に膨れ上がり、財務指標の計算やスクリーニングモデル（Gate 0）に重大な誤りが生じていた。

## Decision
以下の 3 点を実施し、根本的な解決を図った：

1. **データベースのクリーンアップと制約追加**:
    - 重複レコードを削除し、最新の `DisclosedTime` または `ingested_at` を持つレコードのみを保持するようにクリーンアップした。
    - DuckDB の `ALTER TABLE` では一意性制約の追加がサポートされていないため、テーブルを再作成し、`(LocalCode, DisclosedDate, FiscalYear, FiscalPeriod, Type)` に対する **`UNIQUE` 制約** を定義した。

2. **同期ロジックの変更 (UPSERT)**:
    - `src/engine.py` のインジェスト処理において、`INSERT OR IGNORE` を **`INSERT OR REPLACE`** に変更した。これにより、修正開示等で新しいデータが届いた場合に既存レコードが最新情報で更新される（冪等性が保証される）ようになった。

3. **主キー (fact_id) 生成の改善**:
    - `fact_id` の生成ロジックに `fiscal_year` と `fiscal_period` を含めるように変更し、決算期ごとの一意識別精度を向上させた。

## Consequences
### Positive
- 集計処理における数値の重複加算が解消され、正確な財務指標が算出可能になった。
- データベースレベルで一意性が強制されるため、将来的に同様のバグが再発する可能性を排除した。
- `INSERT OR REPLACE` により、データの修正開示にも自動的に対応可能になった。

### Negative / Risks
- 重複していた古いデータ（過去の誤ったレコードなど）は削除され、最新の 1 件のみが保持される。
- `UNIQUE` 制約に違反する不完全なデータが供給された場合、挿入時にエラー（または上書き）が発生する。

## References
- Issue: Duplication Bug Diagnostic Report
- PR: N/A (Direct Fix)
- Files: `src/engine.py`, `data/jquants_financials.duckdb`
