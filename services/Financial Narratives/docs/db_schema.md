# Database Schema Documentation

**Current Schema Version: 1**

This document is automatically generated from `src/db/schema.py`. **Do not edit manually.**

## Table of Contents
- [filings](#filings)
- [structured_data](#structured_data)
- [schema_migrations](#schema_migrations)

<a id='filings'></a>
## Table: `filings`

提出書類の生データおよびパースされた定性情報を保存するテーブル

| Column | Type | PK | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `accession_number` | `VARCHAR` | ✅ | - | 書類固有の受付番号 (SEC/EDINET共通) |
| `ticker` | `VARCHAR` |  | - | 銘柄ティッカーまたは証券コード |
| `cik` | `VARCHAR` |  | - | SEC固有の企業識別番号 (米国株のみ) |
| `form` | `VARCHAR` |  | - | 書類の種類 (10-K, 10-Q, 有価証券報告書など) |
| `filing_date` | `DATE` |  | - | 書類の提出日 |
| `sections` | `JSON` |  | - | パースされたセクション情報 (JSON形式) |
| `metadata` | `JSON` |  | - | 補足的なメタデータ (JSON形式) |
| `updated_at` | `TIMESTAMP` |  | `CURRENT_TIMESTAMP` | レコードの最終更新日時 |

<a id='structured_data'></a>
## Table: `structured_data`

LLMによって構造化された事実情報を保存するテーブル

| Column | Type | PK | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `accession_number` | `VARCHAR` | ✅ | - | 紐付け用の受付番号 |
| `ticker` | `VARCHAR` |  | - | 銘柄ティッカーまたは証券コード |
| `structured_facts` | `JSON` |  | - | AIが抽出した構造化事実 (JSON形式) |
| `updated_at` | `TIMESTAMP` |  | `CURRENT_TIMESTAMP` | AI処理の最終更新日時 |

<a id='schema_migrations'></a>
## Table: `schema_migrations`

スキーマのバージョン管理用テーブル

| Column | Type | PK | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `version` | `INTEGER` | ✅ | - | スキーマバージョン番号 |
| `applied_at` | `TIMESTAMP` |  | `CURRENT_TIMESTAMP` | 適用日時 |
| `description` | `VARCHAR` |  | - | 変更内容の説明 |