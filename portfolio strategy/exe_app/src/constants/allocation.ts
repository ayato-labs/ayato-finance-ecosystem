// src/constants/allocation.ts
import { AssetKey, CategoryKey, Currency } from '../types/portfolio';

export interface CategoryConfig {
  ratio: number;
  label: string;
  color: string;
}

export const TARGET_ALLOCATION: Record<CategoryKey, CategoryConfig> = {
  INDEX: { ratio: 0.60, label: 'インデックス', color: '#3B82F6' },
  STOCK: { ratio: 0.25, label: '個別株/ETF',   color: '#10B981' },
  BOND:  { ratio: 0.00, label: '債券',        color: '#8B5CF6' },
  GOLD:  { ratio: 0.00, label: '金 (Gold)',   color: '#EAB308' },
  CASH:  { ratio: 0.10, label: '現金・MMF',    color: '#F59E0B' },
  CRYPTO:{ ratio: 0.05, label: 'BTC',          color: '#F97316' },
};

export const ASSET_CONFIG: Record<AssetKey, { label: string; category: CategoryKey }> = {
  sp500:    { label: 'S&P500',      category: 'INDEX' },
  orkan:    { label: 'オルカン',      category: 'INDEX' },
  us_stock: { label: '米国株/ETF',   category: 'STOCK' },
  jp_stock: { label: '日本株/ETF',   category: 'STOCK' },
  jp_bond:  { label: '日本国債',     category: 'BOND' },
  us_bond:  { label: '米ドル債',     category: 'BOND' },
  physical_gold: { label: '金 (現物/積立)', category: 'GOLD' },
  gold_etf:      { label: '金 ETF',       category: 'GOLD' },
  usd_cash: { label: '外貨現金/MMF', category: 'CASH' },
  jpy_cash: { label: '日本円',       category: 'CASH' },
  btc:      { label: '暗号資産 (BTC)', category: 'CRYPTO' },
};

export const DEFAULT_INPUTS = {
  sp500: 0,
  orkan: 0,
  us_stock: 0,
  jp_stock: 0,
  jp_bond: 0,
  us_bond: 0,
  physical_gold: 0,
  gold_etf: 0,
  usd_cash: 0,
  jpy_cash: 0,
  btc: 0,
  baseCurrency: 'JPY' as Currency,
  okThreshold: 0.02,
};
