import { useState, useMemo, useCallback } from 'react';
import { 
  RawInputs, 
  CalculationResult, 
  AssetKey 
} from '../types/portfolio';
import { DEFAULT_INPUTS } from '../constants/allocation';
import { 
  calcAssetResults, 
  calcCategoryResults, 
  generateRebalancePlan 
} from '../utils/calculator';

export function usePortfolioCalculator() {
  const [inputs, setInputs] = useState<RawInputs>(DEFAULT_INPUTS);

  const result = useMemo<CalculationResult | null>(() => {
    // 全てのアセットが0の場合は計算をスキップ
    const hasValue = (Object.keys(DEFAULT_INPUTS) as AssetKey[]).some(
      key => inputs[key] > 0
    );
    if (!hasValue) return null;

    // Step 1: 換算
    const assetResults = calcAssetResults(inputs);

    // Step 2: 合計
    const portfolioTotal = assetResults.reduce((sum, a) => sum + a.valueInBase, 0);
    if (portfolioTotal === 0) return null;

    // Step 3: カテゴリ集計・差分
    const categoryResults = calcCategoryResults(assetResults, portfolioTotal, inputs.okThreshold);

    // Step 4: リバランスプラン
    const rebalancePlan = generateRebalancePlan(categoryResults, portfolioTotal);

    return { assetResults, categoryResults, rebalancePlan, portfolioTotal };
  }, [inputs]);

  const updateAsset = useCallback((key: AssetKey, value: number) => {
    setInputs(prev => ({ ...prev, [key]: value }));
  }, []);

  const updateSettings = useCallback((settings: Partial<Pick<RawInputs, 'fxRate' | 'baseCurrency' | 'okThreshold'>>) => {
    setInputs(prev => ({ ...prev, ...settings }));
  }, []);

  const reset = useCallback(() => setInputs(DEFAULT_INPUTS), []);

  const setSampleData = useCallback(() => {
    setInputs({
      ...DEFAULT_INPUTS,
      sp500: 4000,
      orkan: 100000,
      us_stock: 1200,
      jp_stock: 150000,
      usd_cash: 500,
      jpy_cash: 20000,
      btc: 0.05, // 単位がUSD想定なら5000とかにするべきか？設計書ではUSD
      fxRate: 155.0,
    });
  }, []);

  return { inputs, result, updateAsset, updateSettings, reset, setSampleData };
}
