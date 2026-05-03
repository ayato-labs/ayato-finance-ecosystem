# Daily Stock Price API 仕様書

本システムは、**始値・高値・安値・終値・出来高・株式分割の「6つの基本次元」**に特化した、高精度かつ軽量な日次株価データエンジンです。10年以上のヒストリカルデータを高圧縮Parquet/DuckDBベースで提供します。

## 🚀 基本情報
- **ベースURL**: デフォルトは `http://127.0.0.1:5005` (CLI引数で変更可能)
- **ポート指定**: `--port 5005` (デフォルト)
- **ホスト指定**: `--host 127.0.0.1` (デフォルト)
- **CORS**: 有効化済 (全ドメイン `*` 許可)
- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`

---

## 📌 エンドポイント一覧

### 1. ルート (ヘルスチェック)
サーバーの稼働状態と利用可能な主要エンドポイントの一覧を返します。

- **Method**: `GET`
- **Path**: `/`
- **Response**:
    ```json
    {
        "message": "Daily Stock Price API is running",
        "endpoints": ["/status", "/prices/{ticker}", "/query", "/sync/{ticker}"],
        "docs": "/docs"
    }
    ```

---

### 2. ステータス確認
データベースの統計情報(レコード数、銘柄数、ストレージ使用量)を返します。

- **Method**: `GET`
- **Path**: `/status`
- **Response**:
    - `catalog_stats`: カタログ内のインデックス統計 (total_mappings, unique_tickers, unique_files)
    - `last_updated`: 最終更新時間

---

### 3. 価格データの取得
特定の銘柄のヒストリカル価格データを取得します。重複はエンジン側で自動的に除外(最新のLoadTimestampを優先)されます。

- **Method**: `GET`
- **Path**: `/prices/{ticker}`
- **Parameters**:
    - `ticker` (Path, 必須): 銘柄コード (例: `AAPL`, `7203.T`)
    - `start_date` (Query, 任意): 開始日 (YYYY-MM-DD)
    - `end_date` (Query, 任意): 終了日 (YYYY-MM-DD)
- **Response**: `List[PriceRecord]`
    ```json
    [
        {
            "Date": "2024-01-01T00:00:00",
            "Ticker": "AAPL",
            "Open": 150.0,
            "High": 155.0,
            "Low": 149.0,
            "Close": 153.0,
            "Volume": 1000000,
            "StockSplits": 0.0,
            "Source": "yfinance",
            "LoadTimestamp": "2024-01-02T12:00:00"
        }
    ]
    ```

#### PriceRecord スキーマ (高精度定義)
- **Date**: 時刻情報なしの日付 (Date32)
- **Ticker**: 銘柄コード (Category型)
- **Open / High / Low / Close / StockSplits**: **float32** (精度とオーバーフロー耐性を両立)
- **Volume**: **int64** (21億株超の巨大出来高に対応)
- **Source**: データソース名
- **LoadTimestamp**: データロード時のタイムスタンプ

---

### 4. 個別銘柄の同期 (オンデマンド)
指定した銘柄の最新データを外部API(yfinance等)から取得し、データベースを更新します。

- **Method**: `POST`
- **Path**: `/sync/{ticker}`
- **Parameters**:
    - `ticker` (Path, 必須): 同期する銘柄コード
    - `days` (Query, 任意): 遡って取得する日数 (デフォルトはインクリメンタル更新)
- **Response**:
    ```json
    {
        "status": "success",
        "ticker": "AAPL",
        "message": "Manual sync completed."
    }
    ```

---

### 5. アドホックSQLクエリ
データレイク全体に対して DuckDB の強力な分析 SQL を直接実行します。

- **Method**: `POST`
- **Path**: `/query`
- **Request Body**:
    - `sql` (必須): 実行する SQL 文。`{T}` プレースホルダを使用すると全Parquetファイルが対象になります。
    - `limit` (任意): 最大取得件数 (デフォルト 100)
- **Usage Example**:
    ```json
    {
        "sql": "SELECT Ticker, AVG(Close) as AvgPrice FROM {T} GROUP BY Ticker HAVING AvgPrice > 100",
        "limit": 10
    }
    ```
- **Response**:
    - `columns`: カラム名のリスト
    - `data`: 結果レコードのリスト

---

## 🛡 データ整合性
- **重複排除**: データ取得時に `LoadTimestamp` を付与し、API提供時には最新のデータを優先するビューを提供します。
- **圧縮**: カラム指向の Apache Parquet (Zstandard 圧縮) を採用しており、ディスク消費を最小限に抑えています。
