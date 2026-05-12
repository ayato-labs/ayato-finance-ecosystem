import React from 'react';

import { Currency } from '../../types/portfolio';

interface HeaderProps {
  baseCurrency: Currency;
  okThreshold: number;
  onUpdateSettings: (settings: { baseCurrency?: Currency; okThreshold?: number }) => void;
}

export const Header: React.FC<HeaderProps> = ({
  baseCurrency,
  okThreshold,
  onUpdateSettings,
}) => {
  return (
    <header className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 mb-8">
      <div className="flex items-center gap-4">
        <div className="bg-slate-900 text-white p-3 rounded-2xl shadow-lg shadow-blue-500/20">
          <h1 className="text-2xl font-black tracking-tighter leading-none">ALLOC</h1>
        </div>
        <div>
          <p className="text-slate-900 font-black text-lg leading-tight">Portfolio Rebalancer</p>
          <p className="text-slate-400 text-xs font-bold uppercase tracking-widest">v1.0.0 • Professional</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        {/* Threshold Slider */}
        <div className="bg-white p-3 rounded-xl shadow-sm border border-slate-200 flex flex-col gap-1 min-w-[180px]">
          <div className="flex justify-between items-center">
            <span className="text-[10px] font-black text-slate-400 uppercase tracking-wider">Tolerance</span>
            <span className="text-xs font-black text-blue-600">±{(okThreshold * 100).toFixed(1)}%</span>
          </div>
          <input
            type="range"
            min="0.005"
            max="0.1"
            step="0.005"
            className="w-full h-1.5 bg-slate-100 rounded-lg appearance-none cursor-pointer accent-blue-500"
            value={okThreshold}
            onChange={(e) => onUpdateSettings({ okThreshold: parseFloat(e.target.value) })}
          />
        </div>

        {/* Base Currency Mode */}
        <div className="flex items-center bg-white p-2.5 rounded-xl shadow-sm border border-slate-200 gap-3">
          <span className="text-[10px] font-black text-slate-400 uppercase tracking-wider">Display Mode</span>
          <select
            className="bg-transparent text-xs font-black text-slate-800 outline-none cursor-pointer hover:text-blue-600 transition-colors"
            value={baseCurrency}
            onChange={(e) => onUpdateSettings({ baseCurrency: e.target.value as Currency })}
          >
            <option value="JPY">JPY Only (¥)</option>
            <option value="USD">USD Only ($)</option>
          </select>
        </div>
      </div>
    </header>
  );
};
