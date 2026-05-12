// src/types/portfolio.ts

export type AssetKey = 
  | 'sp500' | 'orkan' 
  | 'us_stock' | 'jp_stock' 
  | 'usd_cash' | 'jpy_cash' 
  | 'btc';

export type CategoryKey = 'INDEX' | 'STOCK' | 'CASH' | 'CRYPTO';

export type Currency = 'JPY' | 'USD';

// ユーザー入力
export interface RawInputs {
  sp500:    number;   // USD
  orkan:    number;   // JPY
  us_stock: number;   // USD
  jp_stock: number;   // JPY
  usd_cash: number;   // USD
  jpy_cash: number;   // JPY
  btc:      number;   // USD
  fxRate:   number;   // USD/JPY レート (1 USD = ? JPY)
  baseCurrency: Currency;
  okThreshold: number; // ±% (例: 0.02)
}

// アセット単位の計算結果
export interface AssetResult {
  key:        AssetKey;
  label:      string;
  inputValue: number;          // 入力値（元通貨）
  valueInBase: number;         // 基準通貨換算額
  category:   CategoryKey;
  currency:   Currency;
}

// カテゴリ単位の計算結果
export interface CategoryResult {
  key:           CategoryKey;
  label:         string;
  color:         string;
  currentTotal:  number;       // 現在額（基準通貨）
  targetTotal:   number;       // 目標額（基準通貨）
  targetRatio:   number;       // 目標比率
  currentRatio:  number;       // 現在比率
  deviation:     number;       // 差分 = current - target（正=超過、負=不足）
  deviationRatio: number;      // 差分比率
  status:        'OVER' | 'UNDER' | 'OK';
  assets:        AssetResult[];
}

// リバランスアクション
export interface AssetBreakdown {
  key:    AssetKey;
  label:  string;
  amount: number;   // このアセットへの割り当て額 (基準通貨)
  ratio:  number;   // カテゴリ内の構成比
}

export interface RebalanceAction {
  category:      CategoryKey;
  label:         string;
  amount:        number;       // 売却/購入額（基準通貨）
  assetBreakdown: AssetBreakdown[];
}

// リバランス提案
export interface RebalancePlan {
  currentTotal:    number;
  targetTotal:     number;       // 全てを目標比率にするために必要な新合計額
  requiredInvestment: number;    // 追加で必要な投資総額
  buyActions:      RebalanceAction[];
}

export interface CalculationResult {
  assetResults: AssetResult[];
  categoryResults: CategoryResult[];
  rebalancePlan: RebalancePlan;
  portfolioTotal: number;
}
