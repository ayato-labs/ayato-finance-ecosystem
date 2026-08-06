# ADR-0009: 定性テキスト(Markdown)の外部Parquetストレージオフロードと透明参照

## ステータス

承認済み

## 概要

DuckDB本体のデータベースファイルサイズを劇的に削減（8.2 GB から最大 2〜3 GB 程度へ短縮）し、クエリ処理速度を向上させるため、長大な定性テキスト（Markdown本文）を ZSTD 圧縮 Parquet ファイルとして外部化し、DuckDBからは透明な View 経由で照会・結合するハイブリッドストレージ構造を導入する。

## 背景

`filing_sections` テーブルに保存される Markdown テキスト本文（`content_md`）は長大な自然言語テキストであり、DuckDBのデータベース物理サイズ（`edgar.duckdb`）の約70%以上を占めている。
DuckDBは列指向OLAPデータベースであり、数値データ（`company_facts`）やメタデータ（`filings`）の集計・検索に最適化されているため、巨大テキストを同一の `.duckdb` ファイル内に直接保持し続けることは以下の問題を引き起こす：

1. **DBファイルサイズの膨大化**: 全テキストを保持するため、ファイルサイズが数ギガ〜十数ギガバイトに達する。
2. **I/O効率の低下**: 財務数値の集計クエリを実行する際にも、同一DBファイル内の巨大テキストブロックがI/Oおよびメモリキャッシュに影響を与える。

## 決定事項

1. **定性テキストの外部 Parquet オフロード (`data/edgar/sections/`)**
   - セクション本文 (`content_md`) を DuckDB 内の `VARCHAR` カラムへ直接格納する代わりに、`zstd` 圧縮をかけた Parquet ファイル (`data/edgar/sections/{accession_number}.parquet`) として保存する。
2. **`filing_sections` テーブル構造の軽量化**
   - `filing_sections` テーブルには、`section_id`, `accession_number`, `section_name`, `parquet_path`, `updated_at` の軽量メタデータ列のみを保持する。
3. **DuckDB View による透過的テキスト参照 (`filing_sections_view`)**
   - DuckDBの `read_parquet()` 関数と View を組み合わせ、従来のクエリ（`SELECT content_md ...`）をそのまま変更せず透過的にテキスト取得できるようにする。
4. **既存 DB の自動・安全マイグレーション機構**
   - 既存の `edgar.duckdb` 内に保持されている `content_md` を自動検出・抽出して Parquet へ切り出し、DB本体を再コンパクション（リビルド）するマイグレーション関数を実装する。

## 利点

1. **大幅なストレージ削減**: ディスクストレージ消費量をさらに 50〜70% 削減（`edgar.duckdb` ファイル本体の超軽量化）。
2. **クエリ性能の向上**: 数値分析・メタデータ検索クエリが巨大テキストブロックの影響を受けず、超高速化。
3. **後方互換性と柔軟性**: View 経由で参照するため、上位レイヤーや既存の呼び出し側コードの修正を最小限に抑えられる。

## 変更対象コンポーネント

- `docs/ADR/ADR-0009-parquet-text-offloading.md` (新規)
- `src/db_schema.py` (FilingSectionSchemaの調整)
- `src/storage.py` (Parquet保存、View作成、自動マイグレーションの実装)
- `main.py` (オフロード・マイグレーションコマンドの追加)
- `tests/unit/test_storage.py` (Parquetオフロードのユニットテスト追加)
