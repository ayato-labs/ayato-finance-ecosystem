# ADR-0013: HTMLダウンロード・HTMLパース・DB書き込みの3段階完全非同期パイプライン化

## ステータス

承認済み

## 概要

SEC EDGAR からのデータ収集処理において、従来の 2 段階（API/Parse 同期ワーカー + DB コンシューマー）から、**「① API ダウンロード（Fetch Producer）」「② HTML/Markdown パース（Parse Worker）」「③ DuckDB 書き込み（DB Consumer）」の 3 段階非同期パイプライン構造** に完全再設計する。
これにより、重い HTML 解析処理による API 通信スレッドのブロッキングを排除し、SEC 制限枠（10 req/sec）上限ギリギリでネットワーク通信を極限まで加速する。

## 背景

ADR-0012 では Producer-Consumer パターンを導入したが、Producer 内で **「HTML ダウンロード」と「HTML の Markdown 変換・セクションパース（`extract_all_sections`）」が同一の同期コルーチン** として結合されていた。

巨大な HTML（数 MB 〜 数十 MB）のパースや BeautifulSoup / lxml による再帰処理が実行される際、**次のかんたんな API リクエスト送信が一時的にブロック** され、SEC 規約で許容されている 10 req/sec のネットワーク帯域をフル活用できていない問題が発生していた。

## 決定事項

1. **`raw_queue` による Fetch と Parse の非同期分離**
   - **Stage 1 (Fetch Producer)**: SEC から HTML をダウンロードし、パースを一切待たずにそのまま `raw_queue` （`asyncio.Queue(maxsize=200)`） へ即座に投入（`put_nowait`）する。0.11 秒間隔のウェイトにより SEC 制限を安全かつ最高効率で遵守する。
   - **Stage 2 (Parse Worker)**: バックグラウンドで常時待機する 4 並列の `_parse_worker` タスクが `raw_queue` から raw HTML を取得し、`asyncio.to_thread` 経由で CPU 非同期にパース（Markdown化・セクション分解）を実行して結果を `filings_queue` へ投入する。
   - **Stage 3 (DB Consumer)**: 従来通り `_filings_db_consumer` および `_facts_db_consumer` が DuckDB へバッチ（`BATCH_SIZE`）単位で一括保存する。

2. **マルチステージ・センチネル終了機構**
   - パイプライン終了時は、Stage 1 完了後に `raw_queue` に Worker 数分の `None` を投入して Parse Worker をフラッシュ・終了し、その後 Stage 2 完了後に `filings_queue` / `facts_queue` に `None` を投入して DB Consumer を安全に終了する。

## 利点

1. **API レート制限の限界利用**: HTML パースの計算コストに関わらず、API ダウンローダーは SEC 上限（10 req/sec）の最高速度でリクエストを投げ続ける。
2. **CPU リソースのマルチコア活用**: 重い Markdown パース処理が 4 並列の Worker スレッドに分散されるため、CPU ネックによるパイプライン全体の滞留が解消される。
3. **完全な責務分離**: ネットワーク通信、データ変換、ディスク I/O の 3 つのリソース層が完全に独立して駆動する。

## 変更対象コンポーネント

- `docs/ADR/ADR-0013-3stage-decoupled-async-pipeline.md` (新規)
- `src/pipeline.py` (3 段階非同期パイプライン実装)
- `pyproject.toml` (v0.1.3 へ更新)
