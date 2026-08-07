# ADR-0012: Producer-Consumer パターンによる API 通信と DB 保存の非同期分離

## ステータス

承認済み

## 概要

SEC EDGAR からのデータ収集処理において、API 受信・データパース処理（Producer）と DuckDB へのディスク書き込み処理（Consumer）を `asyncio.Queue` を介して非同期に完全分離する。
これにより、DB 書き込み時のディスク I/O 待ちによる API 通信の空転・ブロッキングを排除し、SEC 規約の許可上限（秒間 8〜10 リクエスト）を常にフル活用したハイスループットなデータ同期を実現する。

## 背景

これまでのパイプライン実装（ADR-0011）では、`asyncio.Semaphore(8)` を用いて並列ダウンロードを行っていたが、バッファが `BATCH_SIZE`（例: 10件）に達した際に `storage.save_filings_batch()` や `storage.save_facts_batch()` が呼び出され、**非同期 API ワーカータスクが DuckDB へのディスク書き込み完了を同期的に待機（ブロッキング）** していた。

この設計には以下の課題が存在した：
1. **API レート制限枠の浪費**: ディスク書き込み待ち時間中、SEC API のリクエスト枠（Token Bucket）が利用されず空転していた。
2. **スループット低下**: ネットワーク通信とディスク I/O が互いにブロッキングし合っており、リソースが並列化されていなかった。

## 決定事項

1. **`asyncio.Queue` による Producer-Consumer アーキテクチャの導入**
   - API 受信・パースを担当する非同期ワーカー（Producer）は、結果を `asyncio.Queue` へ非ブロッキングで投入（`put_nowait`）し、直ちに次の API リクエストへ遷移する。
2. **単一のバックグラウンド DB コンシューマー（Consumer Task）の導入**
   - `filings` および `facts` のそれぞれに専用のバックグラウンドタスク（`_filings_db_consumer`, `_facts_db_consumer`）を起動し、Queue からバッチサイズごとにデータを取り出して `asyncio.to_thread` で非同期に DuckDB へ一括保存する。
3. **バックプレッシャー制御と安全なクローズ機構**
   - `asyncio.Queue(maxsize=200)` で上限を設定しメモリ溢れを防ぐ。
   - パイプライン終了時にはセンチネル値（`None`）を投入し、Queue 内の全残余データをフラッシュして安全にタスクを終了する。

## 利点

1. **ネットワーク帯域の最大活用**: API ダウンローダーが DB 保存待ちで停止せず、常に SEC API の上限速度で受信用スロットを埋め続ける。
2. **同期全体の高速化**: 通信と DB I/O の完全オーバーラップにより、データ同期時間が 30〜50% さらに短縮される。
3. **DB ロック競合の全廃**: 単一の Consumer タスクが書き込みを一括管理するため、DuckDB のシングルライター制約に完全に合致する。

## 変更対象コンポーネント

- `docs/ADR/ADR-0012-async-producer-consumer-pipeline.md` (新規)
- `src/pipeline.py` (Queue ベースの Producer-Consumer パイプライン実装)
- `tests/unit/test_pipeline.py` (動作検証および統合テストの更新)
