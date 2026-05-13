import React from 'react';
import { AssetKey, Currency } from '../../types/portfolio';
import { parseNumber } from '../../utils/formatter';

interface AssetInputProps {
  assetKey: AssetKey;
  label: string;
  currency: Currency;
  value: number;
  onChange: (value: number) => void;
}

export const AssetInput: React.FC<AssetInputProps> = ({
  label,
  currency,
  value,
  onChange,
}) => {
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange(parseNumber(e.target.value));
  };

  const currencySymbol = currency === 'JPY' ? '円' : '$';

  return (
    <div className="bg-slate-50 p-4 rounded-lg border border-slate-200">
      <label className="block text-sm font-medium text-slate-600 mb-1">
        {label}
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
        <div className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-bold text-slate-400">
          {currencySymbol}
        </div>
      </div>
    </div>
  );
};
