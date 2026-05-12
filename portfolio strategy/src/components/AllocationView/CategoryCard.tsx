import React from 'react';
import { CategoryResult, Currency } from '../../types/portfolio';
import { formatCurrency, formatPercent } from '../../utils/formatter';

interface CategoryCardProps {
  result: CategoryResult;
  baseCurrency: Currency;
}

export const CategoryCard: React.FC<CategoryCardProps> = ({ result, baseCurrency }) => {
  const statusColors = {
    OVER: 'bg-red-100 text-red-700 border-red-200',
    UNDER: 'bg-amber-100 text-amber-700 border-amber-200',
    OK: 'bg-green-100 text-green-700 border-green-200',
  };

  const statusLabels = {
    OVER: 'OVER',
    UNDER: 'UNDER',
    OK: 'OK',
  };

  return (
    <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div 
            className="w-3 h-3 rounded-full" 
            style={{ backgroundColor: result.color }}
          />
          <h3 className="font-bold text-slate-800">{result.label}</h3>
        </div>
        <span className={`text-[10px] font-black px-2 py-0.5 rounded border ${statusColors[result.status]}`}>
          {statusLabels[result.status]}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-tight">Current</p>
          <p className="text-lg font-black text-slate-800">
            {formatCurrency(result.currentTotal, baseCurrency)}
          </p>
          <p className="text-xs font-medium text-slate-500">
            {formatPercent(result.currentRatio)}
          </p>
        </div>
        <div className="text-right">
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-tight">Target</p>
          <p className="text-lg font-black text-slate-400">
            {formatCurrency(result.targetTotal, baseCurrency)}
          </p>
          <p className="text-xs font-medium text-slate-400">
            {formatPercent(result.targetRatio)}
          </p>
        </div>
      </div>

      <div className="space-y-1">
        <div className="flex justify-between text-[10px] font-bold text-slate-500 uppercase">
          <span>Deviation</span>
          <span className={result.deviation > 0 ? 'text-red-500' : result.deviation < 0 ? 'text-amber-500' : 'text-green-500'}>
            {result.deviation > 0 ? '+' : ''}
            {formatCurrency(result.deviation, baseCurrency)} ({formatPercent(result.deviationRatio)})
          </span>
        </div>
        <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
          <div 
            className="h-full transition-all duration-500"
            style={{ 
              width: `${Math.min(100, (result.currentRatio / result.targetRatio) * 50)}%`,
              backgroundColor: result.color 
            }}
          />
        </div>
      </div>
      
      <div className="mt-2 border-t border-slate-50 pt-3">
        {result.assets.map(asset => (
          <div key={asset.key} className="flex justify-between items-center text-xs mb-1">
            <span className="text-slate-500">{asset.label}</span>
            <span className="text-slate-700 font-medium">
              {formatCurrency(asset.valueInBase, baseCurrency)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};
