import React from 'react';
import { AssetKey, Currency } from '../../types/portfolio';
import { parseNumber } from '../../utils/formatter';

interface AssetInputProps {
  assetKey: AssetKey;
  label: string;
  currency: Currency;
  value: number;
  onChange: (value: number) => void;
  baseCurrencyValue?: string; // 基準通貨換算額
}

export const AssetInput: React.FC<AssetInputProps> = ({
  label,
  currency,
  value,
  onChange,
  baseCurrencyValue,
}) => {
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange(parseNumber(e.target.value));
  };

  return (
    <div className="bg-slate-50 p-4 rounded-lg border border-slate-200">
      <label className="block text-sm font-medium text-slate-600 mb-1">
        {label} <span className="text-xs text-slate-400">[{currency}]</span>
      </label>
      <div className="relative">
        <input
          type="text"
          inputMode="numeric"
          className="w-full px-3 py-2 bg-white border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all text-lg font-semibold"
          value={value === 0 ? '' : value.toLocaleString()}
          onChange={handleChange}
          placeholder="0"
        />
      </div>
      {baseCurrencyValue && (
        <p className="mt-1 text-xs text-slate-500 text-right">
          {baseCurrencyValue}
        </p>
      )}
    </div>
  );
};
