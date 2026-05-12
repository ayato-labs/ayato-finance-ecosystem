// src/utils/calculator.test.ts
import { describe, it, expect } from 'vitest';
import { 
  calcAssetResults, 
  calcCategoryResults, 
  generateRebalancePlan 
} from './calculator';
import { RawInputs } from '../types/portfolio';
import { DEFAULT_INPUTS, TARGET_ALLOCATION } from '../constants/allocation';

describe('calculator logic (Dual Mode)', () => {
  describe('JPY Mode', () => {
    const mockInputs: RawInputs = {
      ...DEFAULT_INPUTS,
      sp500: 600000,
      orkan: 100000,
      us_stock: 150000,
      jp_stock: 100000,
      jp_bond: 0,
      us_bond: 0,
      physical_gold: 0,
      gold_etf: 0,
      usd_cash: 0,
      jpy_cash: 50000,
      btc: 0,
      baseCurrency: 'JPY',
      okThreshold: 0.02,
    };

    it('should calculate correct totals in JPY', () => {
      const assetResults = calcAssetResults(mockInputs);
      const portfolioTotal = assetResults.reduce((sum, a) => sum + a.valueInBase, 0);
      expect(portfolioTotal).toBe(1000000);
    });
  });

  describe('USD Mode', () => {
    const mockInputs: RawInputs = {
      ...DEFAULT_INPUTS,
      sp500: 4000,
      orkan: 1000,
      us_stock: 2000,
      jp_stock: 1000,
      usd_cash: 1000,
      jpy_cash: 500,
      btc: 500,
      baseCurrency: 'USD',
      okThreshold: 0.02,
    };

    // Total = 4000+1000+2000+1000+1000+500+500 = 10,000 USD

    it('should calculate correct totals in USD', () => {
      const assetResults = calcAssetResults(mockInputs);
      const portfolioTotal = assetResults.reduce((sum, a) => sum + a.valueInBase, 0);
      expect(portfolioTotal).toBe(10000);

      const categoryResults = calcCategoryResults(assetResults, portfolioTotal, mockInputs.okThreshold, TARGET_ALLOCATION);
      const plan = generateRebalancePlan(categoryResults, portfolioTotal);

      // Target INDEX is 60% = 6,000. Current INDEX = 4,000 + 1,000 = 5,000.
      // Need +1,000 in INDEX if other categories are not over.
      expect(plan.currentTotal).toBe(10000);
    });
  });

  describe('Excess Cash Scenario', () => {
    const mockInputs: RawInputs = {
      ...DEFAULT_INPUTS,
      sp500: 100000, // Target 60% (Floor: 166k)
      orkan: 0,
      us_stock: 0,
      jp_stock: 0,
      usd_cash: 900000, // Excess Cash
      jpy_cash: 0,
      btc: 0,
      baseCurrency: 'JPY',
      okThreshold: 0.02,
    };

    it('should use existing cash instead of asking for more investment', () => {
      const assetResults = calcAssetResults(mockInputs);
      const portfolioTotal = 1000000;
      const categoryResults = calcCategoryResults(assetResults, portfolioTotal, 0.02, TARGET_ALLOCATION);
      const plan = generateRebalancePlan(categoryResults, portfolioTotal);

      // INDEX floor is 100k / 0.6 = 166k.
      // Total is 1M. So NewTotal should be 1M (CurrentTotal).
      expect(plan.targetTotal).toBe(1000000);
      expect(plan.requiredInvestment).toBe(0);
      
      // Should suggest buying INDEX using the 900k cash.
      const indexBuy = plan.buyActions.find(a => a.category === 'INDEX')!;
      expect(indexBuy.amount).toBe(500000); // Target 60% of 1M = 600k. 600k - 100k = 500k.
    });
  });
});
