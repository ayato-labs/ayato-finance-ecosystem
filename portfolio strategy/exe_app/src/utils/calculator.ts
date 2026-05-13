// src/utils/calculator.ts
import { 
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

import { 
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
import { logger } from './logger';

/**
 * アセットごとの計算結果を生成
 */
export function calcAssetResults(inputs: RawInputs): AssetResult[] {
  try {
    logger.debug('Calculating asset results', { inputKeys: Object.keys(inputs) });
    const results = (Object.keys(ASSET_CONFIG) as AssetKey[]).map(key => {
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
    return results;
  } catch (err) {
    logger.error('Failed to calculate asset results', { err, inputs });
    throw err; // 再スローしてエラーを握りつぶさない
  }
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
  try {
    logger.debug('Calculating category results', { portfolioTotal, okThreshold });
    const categories = Object.keys(targetAllocation) as CategoryKey[];
    
    const results = categories.map(key => {
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
    return results;
  } catch (err) {
    logger.error('Failed to calculate category results', { err, portfolioTotal });
    throw err;
  }
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
 */
export function generateRebalancePlan(
  categoryResults: CategoryResult[],
  portfolioTotal: number
): RebalancePlan {
  try {
    logger.info('Generating rebalance plan', { portfolioTotal });
    
    const requiredTotals = categoryResults
      .filter(cat => cat.key !== 'CASH')
      .map(cat => 
        cat.targetRatio > 0 ? cat.currentTotal / cat.targetRatio : 0
      );
    
    const newTotal = Math.max(...requiredTotals, portfolioTotal);
    const requiredInvestment = Math.max(0, newTotal - portfolioTotal);

    const buyActions: RebalanceAction[] = categoryResults.map(cat => {
      const newTargetAmount = newTotal * cat.targetRatio;
      const buyAmount = Math.max(0, newTargetAmount - cat.currentTotal);

      return {
        category: cat.key,
        label:    cat.label,
        amount:   buyAmount,
        assetBreakdown: calcBuyBreakdown(cat, buyAmount),
      };
    }).filter(action => action.amount > 0.01);

    logger.info('Rebalance plan generated successfully', { 
      requiredInvestment, 
      actionCount: buyActions.length 
    });

    return { 
      currentTotal: portfolioTotal, 
      targetTotal: newTotal, 
      requiredInvestment, 
      buyActions 
    };
  } catch (err) {
    logger.error('Failed to generate rebalance plan', { err, portfolioTotal });
    throw err;
  }
}
