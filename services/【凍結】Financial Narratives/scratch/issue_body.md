## 背景
Financial Narratives の基盤が完成したため、次のフェーズとして抽出データの詳細分析(Gate 1: Capex, R&D, Governance)の実装と、SEC API やストレージの堅牢性(Robustness)の強化を行う。

## 受け入れ条件
- [ ] **Robustness**:
  - `EdgarFetcher` に 429 エラー時の指数バックオフリトライを実装。
  - `FinancialNarrativeStorage` にバリデーションを追加し、不完全なデータでのクラッシュを防止。
  - `tests/robustness/test_adversarial.py` の全テストがリトライを含めてパスすることを確認。
- [ ] **Gate 1 Analysis**:
  - `src/analyzer.py` の新規作成(Gemini を使用した詳細分析)。
  - `Capex` (設備投資), `R&D` (研究開発), `Governance` (資本配分・規律) の構造化抽出。
- [ ] **API 拡張**:
  - `GET /narratives/{ticker}` または新規エンドポイントで分析結果を取得可能にする。

## 影響範囲
- `src/edgar_fetcher.py`
- `src/storage.py`
- `src/analyzer.py` (新規)
- `src/api/app.py`
- `src/api/models.py`
