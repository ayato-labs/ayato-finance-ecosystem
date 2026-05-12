// src/utils/calculator.test.ts
import { describe, it, expect } from 'vitest';
import { 
  toBase, 
  calcAssetResults, 
  calcCategoryResults, 
  generateRebalancePlan 
} from './calculator';
import { RawInputs } from '../types/portfolio';
import { DEFAULT_INPUTS } from '../constants/allocation';

describe('calculator logic', () => {
  describe('toBase', () => {
    it('should convert USD to JPY correctly', () => {
      expect(toBase(100, 'USD', 'JPY', 150)).toBe(15000);
    });

    it('should convert JPY to USD correctly', () => {
      expect(toBase(15000, 'JPY', 'USD', 150)).toBe(100);
    });

    it('should return same value if currencies match', () => {
      expect(toBase(100, 'USD', 'USD', 150)).toBe(100);
      expect(toBase(100, 'JPY', 'JPY', 150)).toBe(100);
    });
  });

  describe('comprehensive calculation (No-Sell)', () => {
    const mockInputs: RawInputs = {
      ...DEFAULT_INPUTS,
      sp500: 4000,     // USD -> 600,000 JPY (at 150)
      orkan: 100000,   // JPY
      us_stock: 1000,  // USD -> 150,000 JPY
      jp_stock: 100000, // JPY
      usd_cash: 0,
      jpy_cash: 50000, // JPY
      btc: 0,
      fxRate: 150,
      baseCurrency: 'JPY',
      okThreshold: 0.02,
    };

    // Total Portfolio = 600k + 100k + 150k + 100k + 50k = 1,000,000 JPY
    // Current Allocation:
    // INDEX: 700k (70%) -> Target 60%
    // STOCK: 250k (25%) -> Target 25%
    // CASH:  50k  (5%)  -> Target 10%
    // CRYPTO: 0   (0%)  -> Target 5%

    // No-Sell Strategy Calculation:
    // Required Total to make INDEX 60%: 700k / 0.6 = 1,166,666.67
    // Required Total to make STOCK 25%: 250k / 0.25 = 1,000,000
    // Required Total to make CASH 10%:  50k / 0.1 = 500,000
    // Max Required Total = 1,166,666.67
    // Required Investment = 166,666.67

    it('should calculate correct totals and status', () => {
      const assetResults = calcAssetResults(mockInputs);
      const portfolioTotal = assetResults.reduce((sum, a) => sum + a.valueInBase, 0);
      expect(portfolioTotal).toBe(1000000);

      const categoryResults = calcCategoryResults(assetResults, portfolioTotal, mockInputs.okThreshold);
      
      const index = categoryResults.find(c => c.key === 'INDEX')!;
      expect(index.currentTotal).toBe(700000);
      expect(index.status).toBe('OVER');

      const stock = categoryResults.find(c => c.key === 'STOCK')!;
      expect(stock.currentTotal).toBe(250000);
      expect(stock.status).toBe('OK'); // 25% matches exactly

      const cash = categoryResults.find(c => c.key === 'CASH')!;
      expect(cash.currentTotal).toBe(50000);
      expect(cash.status).toBe('UNDER');

      const crypto = categoryResults.find(c => c.key === 'CRYPTO')!;
      expect(crypto.currentTotal).toBe(0);
      expect(crypto.status).toBe('UNDER');
    });

    it('should generate buy-only rebalance plan correctly', () => {
      const assetResults = calcAssetResults(mockInputs);
      const portfolioTotal = assetResults.reduce((sum, a) => sum + a.valueInBase, 0);
      const categoryResults = calcCategoryResults(assetResults, portfolioTotal, mockInputs.okThreshold);
      const plan = generateRebalancePlan(categoryResults, portfolioTotal);

      // Verify overall plan
      expect(plan.currentTotal).toBe(1000000);
      expect(plan.targetTotal).toBeCloseTo(1166666.67, 1);
      expect(plan.requiredInvestment).toBeCloseTo(166666.67, 1);

      // Verify buy actions
      // INDEX should have NO buy action because it is the "bottleneck"
      const indexBuy = plan.buyActions.find(a => a.category === 'INDEX');
      expect(indexBuy).toBeUndefined();

      // STOCK: (1,166,666.67 * 0.25) - 250,000 = 41,666.67
      const stockBuy = plan.buyActions.find(a => a.category === 'STOCK')!;
      expect(stockBuy.amount).toBeCloseTo(41666.67, 1);

      // CASH: (1,166,666.67 * 0.1) - 50,000 = 66,666.67
      const cashBuy = plan.buyActions.find(a => a.category === 'CASH')!;
      expect(cashBuy.amount).toBeCloseTo(66666.67, 1);

      // CRYPTO: (1,166,666.67 * 0.05) - 0 = 58,333.33
      const cryptoBuy = plan.buyActions.find(a => a.category === 'CRYPTO')!;
      expect(cryptoBuy.amount).toBeCloseTo(58333.33, 1);

      // Sum of buy actions should equal required investment
      const totalBuy = plan.buyActions.reduce((s, a) => s + a.amount, 0);
      expect(totalBuy).toBeCloseTo(plan.requiredInvestment, 1);
    });
  });
});
