// src/utils/calculator.ts
import type { 
  RawInputs, 
  AssetResult, 
  CategoryResult, 
  RebalancePlan, 
  AssetKey, 
  CategoryKey, 
  RebalanceAction,
  AssetBreakdown
} from '../types/portfolio';
import { ASSET_CONFIG } from '../constants/allocation';

/**
 * アセットごとの計算結果を生成
 */
export function calcAssetResults(inputs: RawInputs): AssetResult[] {
  return (Object.keys(ASSET_CONFIG) as AssetKey[]).map(key => {
    const config = ASSET_CONFIG[key];
    const inputValue = inputs[key];
    
    return {
      key,
      label: config.label,
      inputValue,
      valueInBase: inputValue, // すべてJPY前提
      category: config.category,
    };
  });
}

/**
 * カテゴリごとの集計と目標額算出
 */
export function calcCategoryResults(
  assetResults: AssetResult[], 
  portfolioTotal: number, 
  okThreshold: number,
  targetAllocation: Record<CategoryKey, { ratio: number; label: string; color: string }>
): CategoryResult[] {
  const categories = Object.keys(targetAllocation) as CategoryKey[];
  
  return categories.map(key => {
    const config = targetAllocation[key];
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
  // ただし、CASHカテゴリは「売却（使用）」可能とするため、フロア計算からは除外する。
  // これにより、余剰現金がある場合はそれを先に使い切る提案になる。
  const requiredTotals = categoryResults
    .filter(cat => cat.key !== 'CASH') // 現金は使い切って良いため、目標比率維持のための強制力を持たせない
    .map(cat => 
      cat.targetRatio > 0 ? cat.currentTotal / cat.targetRatio : 0
    );
  
  // 2. それらの最大値が、証券を売却せずに目標比率を達成できる最小の合計額
  // ただし、現在の総資産額を下回ることはない（現金を使い切るだけで済む場合もあるため）
  const newTotal = Math.max(...requiredTotals, portfolioTotal);
  const requiredInvestment = Math.max(0, newTotal - portfolioTotal);

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
