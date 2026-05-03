# Conceptual Requirements Definition: Premium Local Finance

## 1. Project Overview
### Goal
資産管理に特化した**高精度なUIダッシュボード兼API利用層**を構築する。複雑なデータベース管理や高度な分析は本システムの直接の責務とはせず、外部APIとの疎結合な連携によって機能拡張を行う。

### Design Philosophy
- **UI-Centric**: ユーザー体験(UX/UI)と情報の可視化に100%の責任を持つ。
- **API-Driven**: 本システムは「APIを叩き、結果を表示する」層であり、重いロジックや高度な分析は外部API(Port 5005/5006等)に委ねる。
- **Decoupled Architecture**: データベースや分析モジュールは本システムのコアから切り離し、将来的な入れ替えや拡張を容易にする。

---

## 2. Functional Requirements (What to implement with What)

| Category | Requirement (What) | Technology/Approach (With) |
| :--- | :--- | :--- |
| **Data Engine** | 取引履歴の永続化・高速多次元分析 | **DuckDB** |
| **Quant Logic** | 収益率(CAGR), リスク(Sharpe Ratio), 相関分析 | **Python (Logic Atoms)** |
| **Frontend** | プレミアム・ダークモード、動的チャート | **Next.js + Vanilla CSS** |
| **AI Assistant** | 手動入力の正規化、資産カテゴリ自動推定 | **google-genai (Gemma 4 31b)** |
| **Security** | ローカル暗号化・オフライン動作保証 | **Native File System API / SQLite-based config** |
| **Asset Support** | 株式(日本・米国)、暗号資産(BIP39対応)、現金 | **Unified Asset Schema** |

---

## 3. Out of Scope (What NOT to implement with What)

| Category | Exclusion (What NOT) | Reason (Why NOT) |
| :--- | :--- | :--- |
| **Analytics** | 取引に関する推奨・提案システム | 本システムがアクセスするAPI側で疎結合に提供すべき機能であり、本UIは管理に徹するため。 |
| **Analysis Type** | 定性的な分析機能(ニュース・感情分析等) | 同上。API層での解決を前提とし、本システムは過去の投資結果の数学的分析のみを扱う。 |
| **Sync** | 証券・銀行口座との自動API連携 | APIの保守コスト・不安定性・セキュリティ懸念の排除。 |
| **Infrastructure** | クラウド型DB (PostgreSQL / Firebase) | レイテンシの排除と完全なデータ・ポータビリティの確保。 |
| **Complexity** | リアルタイム・ティックデータ監視 | 中長期的な資産管理にフォーカスし、デイトレード用途は除外。 |
| **Taxation** | 精緻な税金計算・節税シミュレーション | 税金関連は「魔境」とも言える複雑性を持ち、頻繁な法改正による保守コストが膨大になるため。開発の現段階では数学的なリスク・リターン分析の純粋性を優先し、実装を見送る。 |

---

## 4. Operational Strategy: Value-Added Manual Entry
手動入力を単なる「事務作業」から「投資判断のアップデート」へ転換する。

- **Input Feedback**: 入力した瞬間に、ポートフォリオ全体のベータ値や分散効果の変化を即座に計算・表示する。
- **Smart Import**: 手動入力を補完するため、証券会社発行のCSVファイルをAIが解釈し、半自動的にトランザクションへ変換する。
- **Auditability**: 全ての計算過程をログとして保持し、なぜその数字になったのかを遡及可能にする。

---

## 5. Success Metrics
- **Performance**: 10万件の取引データに対しても、分析ダッシュボードが1秒以内に更新されること。
- **Aesthetics**: ユーザーが「毎日開きたくなる」と感じる、一貫性のあるプレミアムなデザインシステム。
- **Accuracy**: 手動入力された取引ログから、配当・手数料を考慮した正確な実効利回りが算出されること(税金は現状スコープ外)。
