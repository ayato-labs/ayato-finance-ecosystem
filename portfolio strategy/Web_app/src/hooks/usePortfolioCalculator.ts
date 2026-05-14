import { useState, useMemo, useCallback, useEffect } from 'react';
import type { 
  RawInputs, 
  CalculationResult, 
  AssetKey,
  CategoryKey,
  CategoryConfig
} from '../types/portfolio';
import { DEFAULT_INPUTS, ASSET_CONFIG, TARGET_ALLOCATION } from '../constants/allocation';
import { 
  calcAssetResults, 
  calcCategoryResults, 
  generateRebalancePlan 
} from '../utils/calculator';

const STORAGE_KEYS = {
  INPUTS: 'alloc_inputs',
  ALLOCATION: 'alloc_target_config',
};

export function usePortfolioCalculator() {
  // 初期化時にlocalStorageから読み込む
  const [inputs, setInputs] = useState<RawInputs>(() => {
    const saved = localStorage.getItem(STORAGE_KEYS.INPUTS);
    return saved ? { ...DEFAULT_INPUTS, ...JSON.parse(saved) } : DEFAULT_INPUTS;
  });

  const [targetAllocation, setTargetAllocation] = useState<Record<CategoryKey, CategoryConfig>>(() => {
    const saved = localStorage.getItem(STORAGE_KEYS.ALLOCATION);
    if (!saved) return TARGET_ALLOCATION;
    
    // 保存されたデータと最新のデフォルトをマージ（新しく追加されたカテゴリを表示させるため）
    const parsed = JSON.parse(saved);
    return { ...TARGET_ALLOCATION, ...parsed };
  });

  // 変更があるたびに保存
  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.INPUTS, JSON.stringify(inputs));
  }, [inputs]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.ALLOCATION, JSON.stringify(targetAllocation));
  }, [targetAllocation]);

  const result = useMemo<CalculationResult | null>(() => {
    // 全てのアセットが0の場合は計算をスキップ
    const hasValue = (Object.keys(ASSET_CONFIG) as AssetKey[]).some(
      key => inputs[key] > 0
    );
    if (!hasValue) return null;

    // Step 1: 換算
    const assetResults = calcAssetResults(inputs);

    // Step 2: 合計
    const portfolioTotal = assetResults.reduce((sum, a) => sum + a.valueInBase, 0);
    if (portfolioTotal === 0) return null;

    // Step 3: カテゴリ集計・差分
    const categoryResults = calcCategoryResults(assetResults, portfolioTotal, inputs.okThreshold, targetAllocation);

    // Step 4: リバランスプラン
    const rebalancePlan = generateRebalancePlan(categoryResults, portfolioTotal);

    return { assetResults, categoryResults, rebalancePlan, portfolioTotal };
  }, [inputs, targetAllocation]);

  const updateAsset = useCallback((key: AssetKey, value: number) => {
    setInputs(prev => ({ ...prev, [key]: value }));
  }, []);

  const updateTargetRatio = useCallback((key: CategoryKey, ratio: number) => {
    setTargetAllocation(prev => ({
      ...prev,
      [key]: { ...prev[key], ratio }
    }));
  }, []);

  const updateSettings = useCallback((settings: Partial<Pick<RawInputs, 'okThreshold' | 'baseCurrency'>>) => {
    setInputs(prev => ({ ...prev, ...settings }));
  }, []);

  const reset = useCallback(() => setInputs(DEFAULT_INPUTS), []);

  const setSampleData = useCallback(() => {
    setInputs({
      ...DEFAULT_INPUTS,
      sp500: 600000,
      orkan: 100000,
      us_stock: 200000,
      jp_stock: 150000,
      jp_bond: 50000,
      us_bond: 50000,
      physical_gold: 30000,
      gold_etf: 20000,
      usd_cash: 100000,
      jpy_cash: 20000,
      btc: 10000,
    });
  }, []);

  return { inputs, result, targetAllocation, updateAsset, updateTargetRatio, updateSettings, reset, setSampleData };
}
