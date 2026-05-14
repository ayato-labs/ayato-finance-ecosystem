// src/utils/formatter.ts

import type { Currency } from '../types/portfolio';

/**
 * 金額を指定された通貨形式でフォーマットする
 */
export function formatCurrency(value: number, currency: Currency): string {
  if (currency === 'JPY') {
    return new Intl.NumberFormat('ja-JP', {
      style: 'currency',
      currency: 'JPY',
      maximumFractionDigits: 0,
    }).format(Math.round(value));
  } else {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0,
    }).format(Math.round(value));
  }
}

export function formatPercent(value: number): string {
  return new Intl.NumberFormat('ja-JP', {
    style: 'percent',
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(value);
}

export function parseNumber(value: string): number {
  const cleaned = value.replace(/[,，￥$\s]/g, '');
  const parsed = parseFloat(cleaned);
  return isNaN(parsed) || parsed < 0 ? 0 : parsed;
}
