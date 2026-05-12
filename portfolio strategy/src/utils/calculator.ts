// src/utils/calculator.ts
import { 
  RawInputs, 
  AssetResult, 
  CategoryResult, 
  RebalancePlan, 
  AssetKey, 
  CategoryKey, 
  Currency,
  RebalanceAction,
  AssetBreakdown
} from '../types/portfolio';
import { TARGET_ALLOCATION, ASSET_CONFIG } from '../constants/allocation';

/**
 * 通貨を基準通貨に換算する (1 USD = fxRate JPY)
 */
export function toBase(value: number, inputCurrency: Currency, baseCurrency: Currency, fxRate: number): number {
  if (inputCurrency === baseCurrency) return value;
  if (baseCurrency === 'JPY') return value * fxRate; // USD -> JPY
  return value / fxRate; // JPY -> USD
}

/**
 * アセットごとの計算結果を生成
 */
export function calcAssetResults(inputs: RawInputs): AssetResult[] {
  return (Object.keys(ASSET_CONFIG) as AssetKey[]).map(key => {
    const config = ASSET_CONFIG[key];
    const inputValue = inputs[key];
    const valueInBase = toBase(inputValue, config.currency, inputs.baseCurrency, inputs.fxRate);
    
    return {
      key,
      label: config.label,
      inputValue,
      valueInBase,
      category: config.category,
      currency: config.currency,
    };
  });
}

/**
 * カテゴリごとの集計と目標額算出
 */
export function calcCategoryResults(assetResults: AssetResult[], portfolioTotal: number, okThreshold: number): CategoryResult[] {
  const categories = Object.keys(TARGET_ALLOCATION) as CategoryKey[];
  
  return categories.map(key => {
    const config = TARGET_ALLOCATION[key];
    const assets = assetResults.filter(a => a.category === key);
    const currentTotal = assets.reduce((sum, a) => sum + a.valueInBase, 0);
    const targetTotal = portfolioTotal * config.ratio;
    const deviation = currentTotal - targetTotal;
    const currentRatio = portfolioTotal > 0 ? currentTotal / portfolioTotal : 0;
    const deviationRatio = currentRatio - config.ratio;

    const status: 'OVER' | 'UNDER' | 'OK' =
      Math.abs(deviationRatio) <= okThreshold ? 'OK'
      : deviation > 0 ? 'OVER'
      : 'UNDER';

    return {
      key,
      label: config.label,
      color: config.color,
      currentTotal,
      targetTotal,
      targetRatio: config.ratio,
      currentRatio,
      deviation,
      deviationRatio,
      status,
      assets,
    };
  });
}

/**
 * 購入内訳の計算: 現在のカテゴリ内比率を維持したまま購入金額を按分
 * (アセットが0の場合は均等に分配)
 */
function calcBuyBreakdown(cat: CategoryResult, totalBuy: number): AssetBreakdown[] {
  const totalCurrent = cat.assets.reduce((s, a) => s + a.valueInBase, 0);
  return cat.assets.map(asset => {
    const ratio = totalCurrent > 0 ? asset.valueInBase / totalCurrent : 1 / cat.assets.length;
    return {
      key:    asset.key,
      label:  asset.label,
      ratio,
      amount: totalBuy * ratio,
    };
  });
}

/**
 * リバランスプランの生成 (ノーセル・リバランス戦略)
 * 現在の資産を一切売却せず、追加投資のみで目標アロケーションを達成するための計算を行う。
 */
export function generateRebalancePlan(
  categoryResults: CategoryResult[],
  portfolioTotal: number
): RebalancePlan {
  // 1. 各カテゴリについて「現在の保有額が目標比率以下になるために必要な最小のポートフォリオ合計額」を算出
  // NewTotal >= CurrentTotal_i / TargetRatio_i
  const requiredTotals = categoryResults.map(cat => 
    cat.targetRatio > 0 ? cat.currentTotal / cat.targetRatio : 0
  );
  
  // 2. それらの最大値が、誰も売却せずに目標比率を達成できる最小の合計額
  const newTotal = Math.max(...requiredTotals, portfolioTotal);
  const requiredInvestment = newTotal - portfolioTotal;

  // 3. 各カテゴリの不足分（新目標額 - 現在額）を購入アクションとする
  const buyActions: RebalanceAction[] = categoryResults.map(cat => {
    const newTargetAmount = newTotal * cat.targetRatio;
    const buyAmount = Math.max(0, newTargetAmount - cat.currentTotal);

    return {
      category: cat.key,
      label:    cat.label,
      amount:   buyAmount,
      assetBreakdown: calcBuyBreakdown(cat, buyAmount),
    };
  }).filter(action => action.amount > 0.01); // 微小な差分は除外

  return { 
    currentTotal: portfolioTotal, 
    targetTotal: newTotal, 
    requiredInvestment, 
    buyActions 
  };
}
