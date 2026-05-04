# Financial Narratives

日米の金融開示書類（10-K, 10-Q, 有価証券報告書等）から定性情報を取得し、事実ベースで構造化抽出を行うサービス。

## システムの責務

本サービスは「データの取得」と「事実の構造化（Structuring）」に特化しています。
投資判断や感情分析などの「解釈（Interpretation/Analysis）」は本システムのスコープ外であり、後続の分析システムが担当します。

### 主な機能
- **SEC EDGAR Sync**: 米国株の提出書類を自動取得し、Markdown形式にパース。
- **EDINET Sync**: 日本株のiXBRL書類を取得し、セクションごとに抽出。
- **Filing Structurer**: Gemini (google-genai) を使用し、設備投資(Capex)、研究開発(R&D)、ガバナンスに関する事実を構造化（JSON化）。
- **FastAPI Server**: 構造化された定性データへのアクセスAPIを提供。

## セットアップ

### 依存関係のインストール
```bash
uv sync
```

### 環境変数
- `GOOGLE_API_KEY`: Geminiによる構造化抽出に使用。
- `EDINET_API_KEY`: EDINET API v2へのアクセスに使用。

## 使用方法

### APIサーバーの起動
```bash
python main.py --api
```

### データの同期
```bash
# 特定銘柄の同期と構造化
curl -X POST http://localhost:5013/sync/AAPL

# 全銘柄の同期
curl -X POST http://localhost:5013/sync/all
```

## アーキテクチャ

1. **Collector**: `EdgarFetcher`, `EdinetFetcher` (取得)
2. **Parser**: `EdgarParser`, `EdinetParser` (パース・Markdown化)
3. **Structurer**: `FilingStructurer` (事実抽出・JSON化)
4. **Storage**: DuckDB (永続化)
