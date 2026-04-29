# Financial Figures Unified API 仕様書 💹

本 API は、日米市場から収集された財務データを一元的に提供するデータハブです。独自の「AI名寄せエンジン」により、市場ごとの差異を吸収した標準化ラベル（NetSales, EPS 等）でのデータ取得が可能です。

---

## 1. システム概要 & 責務

- **責務**: 正規化された財務データの蓄積、差分更新、および高速な API 提供。
- **特長**: 日米の異なる会計基準（GAAP/IFRS）や開示形式を AI が解釈し、単一のインターフェースで提供します。
- **対象外**: 個別銘柄の分析・評価ロジック（これらは本 API を利用する「分析システム」の責務です）。

---

## 2. 実行ガイド (CLI)

本システムは `uv` (Fastest Python Manager) を前提に構築されています。

### 2.1 API サーバーの起動
```powershell
# デフォルト(ポート5006)で起動
$env:PYTHONPATH="."; uv run python src/api/server.py
```

### 2.2 マーケットデータの同期 (差分更新対応)
```powershell
# 市場全体の同期 (前回の同期から7日以内の銘柄を自動スキップ)
uv run python main.py --sync-market BOTH --incremental

# 特定の銘柄を指定して同期 (検証用)
uv run python main.py --sync AAPL MSFT --session reality-check
```

---

## 3. 基本情報

- **Base URL**: `http://localhost:5006`
- **Format**: JSON
- **対話型ドキュメント**: `http://localhost:5006/docs` (Swagger UI)

---

## 4. エンドポイント一覧

### 4.1 システム統計
#### `GET /stats`
市場ごとの登録銘柄数、ファクト数、同期セッション数などの統計情報を取得します。

### 4.2 銘柄情報
#### `GET /tickers`
銘柄リストを取得します。
- **Query Params**:
  - `market`: `US` または `JP` (大文字小文字不問)
  - `search`: 銘柄コードまたは名称の一部
  - `limit`: 取得件数 (1-1000)

### 4.3 標準化財務データ
#### `GET /financials/{symbol}`
特定の銘柄の**標準化済み財務データ**を最新順に取得します。
- **Path**: `symbol` (例: `TSLA`, `7203`)
- **Response Model**:
  - `market`: 市場区分 (`US` | `JP`)
  - `symbol`: 銘柄コード
  - `company_name`: 企業名称
  - `target_label`: 標準化ラベル (次項参照)
  - `value`: 数値
  - `unit`: 単位 (`USD`, `JPY` 等)
  - `period_date`: 報告対象期間の末日 (ISO 8601)
  - `fiscal_year`: 会計年度
  - `reasoning`: AIによるマッピング判定の根拠

---

## 5. 標準化ラベル・カタログ (Standardized Labels)

分析システムは以下のラベルを用いて、市場を意識せずに SQL/API レベルで比較分析が可能です。

### 5.1 業績・損益 (Performance)
| ラベル | 英語名 | 日本語名 (参考) |
| :--- | :--- | :--- |
| **NetSales** | Net Sales / Revenues | 売上高 |
| **OperatingProfit** | Operating Income | 営業利益 |
| **OrdinaryProfit** | Ordinary Income | 経常利益 (JP重視) |
| **NetProfit** | Net Income | 当期純利益 |
| **EPS** | Earnings Per Share | 一株当たり利益 |

### 5.2 成長・投資 (Growth & Investment) 🌟
| ラベル | 英語名 | 日本語名 (参考) |
| :--- | :--- | :--- |
| **ResearchAndDevelopment** | R&D Expenses | 研究開発費 |
| **CapitalExpenditure** | CapEx / IT Investment | 設備投資額 |

### 5.3 財務状態 (Financial Position)
| ラベル | 英語名 | 日本語名 (参考) |
| :--- | :--- | :--- |
| **TotalAssets** | Total Assets | 総資産 |
| **NetAssets** | Net Assets | 純資産 |
| **Equity** | Total Equity | 自己資本 |
| **EquityRatio** | Equity Ratio | 自己資本比率 |
| **CashAndDeposits** | Cash and Deposits | 現金預金 |
| **InterestBearingDebt** | Interest Bearing Debt | 有利子負債 |

### 5.4 キャッシュフロー (Cash Flow)
| ラベル | 英語名 | 日本語名 (参考) |
| :--- | :--- | :--- |
| **OperatingCashFlow** | Operating CF | 営業CF |
| **InvestingCashFlow** | Investing CF | 投資CF |
| **FinancingCashFlow** | Financing CF | 財務CF |

---

## 6. 技術特長 (分析システム開発者向け)

### 6.1 Semantic Normalization (AI 名寄せ)
市場独自のタグ（例: `us-gaap:Revenues` と `JP-tag:売上高`）を、AIが文脈を判断して単一の標準ラベルに統合します。これにより、クロスボーダーの投資効率分析が容易になります。

### 6.2 Windows Resilience & Fault Tolerance (堅牢性)
Windows 環境での稼働を考慮し、DBリソース（DuckDB）の排他制御を `AuditManager` が一元管理しています。

**レジリエンス機能**:
- **動的バッチ分割**: AI APIがタイムアウトやエラーを返した場合、自動的に処理単位（バッチ）を分割してリトライを試行し、部分的な成功を積み上げます。
- **厳格なタイムアウト**: 60秒の強制タイムアウトにより、外部APIのハングアップがシステム全体に波及するのを防ぎます。

### 6.3 Traceability & Observability (可観測性)
すべての標準化データには AI の判定根拠（`reasoning`）が付与されています。

**監査機能**:
- **実行統計の記録**: 同期セッションごとに、処理成功数、エラー数、エラーログを `traceability.duckdb` に記録。
- **マッピング履歴**: どのモデルがどの根拠でマッピングしたかの全履歴を保存。

---

## 7. 注意事項
- **単位**: 原則として、各社の報告単位（フル数、千、百万等）は `value` フィールド内で正規化されますが、通貨単位は維持されます。
- **更新頻度**: 15,000社の同期プロセスにより、最新の開示データが反映されます。`--incremental` 実行により負荷を抑えて最新状態を維持可能です。
