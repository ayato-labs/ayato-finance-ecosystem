// src/constants/allocation.ts
import { AssetKey, CategoryKey, Currency } from '../types/portfolio';

export interface CategoryConfig {
  ratio: number;
  label: string;
  color: string;
}

export const TARGET_ALLOCATION: Record<CategoryKey, CategoryConfig> = {
  INDEX: { ratio: 0.60, label: 'インデックス', color: '#3B82F6' },
  STOCK: { ratio: 0.25, label: '個別株',       color: '#10B981' },
  CASH:  { ratio: 0.10, label: '現金・MMF',    color: '#F59E0B' },
  CRYPTO:{ ratio: 0.05, label: 'BTC',          color: '#F97316' },
};

export const ASSET_CONFIG: Record<AssetKey, { label: string; category: CategoryKey; currency: Currency }> = {
  sp500:    { label: 'S&P500',         category: 'INDEX',  currency: 'USD' },
  orkan:    { label: 'eMAXIS Slim オルカン', category: 'INDEX',  currency: 'JPY' },
  us_stock: { label: '米国個別株',      category: 'STOCK',  currency: 'USD' },
  jp_stock: { label: '日本個別株',      category: 'STOCK',  currency: 'JPY' },
  usd_cash: { label: 'USD現金/MMF',    category: 'CASH',   currency: 'USD' },
  jpy_cash: { label: '日本円',         category: 'CASH',   currency: 'JPY' },
  btc:      { label: 'ビットコイン',    category: 'CRYPTO', currency: 'USD' },
};

export const DEFAULT_INPUTS = {
  sp500: 0,
  orkan: 0,
  us_stock: 0,
  jp_stock: 0,
  usd_cash: 0,
  jpy_cash: 0,
  btc: 0,
  fxRate: 155.0,
  baseCurrency: 'JPY' as Currency,
  okThreshold: 0.02,
};
