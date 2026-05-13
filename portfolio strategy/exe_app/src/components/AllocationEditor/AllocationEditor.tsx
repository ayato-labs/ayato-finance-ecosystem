import React from 'react';
import { CategoryKey, CategoryConfig } from '../../types/portfolio';
import { formatPercent, parseNumber } from '../../utils/formatter';

interface AllocationEditorProps {
  allocation: Record<CategoryKey, CategoryConfig>;
  onUpdateRatio: (key: CategoryKey, ratio: number) => void;
}

export const AllocationEditor: React.FC<AllocationEditorProps> = ({
  allocation,
  onUpdateRatio,
}) => {
  const categories = Object.keys(allocation) as CategoryKey[];
  const totalRatio = categories.reduce((sum, key) => sum + allocation[key].ratio, 0);
  // 小数点精度の誤差を考慮して 0.01% 未満の差は許容
  const isError = Math.abs(totalRatio - 1) > 0.0001;

  const handleTextChange = (key: CategoryKey, valueStr: string) => {
    // パーセント入力（例: 60）を割合（例: 0.6）に変換
    const numValue = parseNumber(valueStr);
    onUpdateRatio(key, numValue / 100);
  };

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden mb-8">
      <div className="p-6 border-b border-slate-100 bg-slate-50/50 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="text-lg font-bold text-slate-800">目標アロケーション設定</h2>
          <p className="text-sm text-slate-500">各カテゴリの理想的な比率を数値またはスライダーで指定してください。</p>
        </div>
        <div className={`px-4 py-2 rounded-xl text-sm font-black border transition-all duration-300 ${
          isError 
            ? 'bg-red-50 text-red-600 border-red-200 shadow-sm shadow-red-100' 
            : 'bg-green-50 text-green-600 border-green-200 shadow-sm shadow-green-100'
        }`}>
          合計: {formatPercent(totalRatio)}
          {isError && <span className="ml-2">⚠️ 100%に調整してください</span>}
        </div>
      </div>
      
      <div className="p-6">
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {categories.map((key) => {
            const config = allocation[key];
            const percentValue = Math.round(config.ratio * 100);
            
            return (
              <div key={key} className="p-4 rounded-xl border border-slate-100 bg-slate-50/30 flex flex-col gap-3">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full" style={{ backgroundColor: config.color }} />
                  <span className="text-[10px] font-black text-slate-400 uppercase tracking-wider">{config.label}</span>
                </div>
                
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    inputMode="numeric"
                    className="w-16 px-2 py-1 text-sm font-black bg-white border border-slate-200 rounded-md focus:ring-2 focus:ring-blue-500 outline-none text-center"
                    value={percentValue}
                    onChange={(e) => handleTextChange(key, e.target.value)}
                  />
                  <span className="text-xs font-bold text-slate-400">%</span>
                </div>

                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.01"
                  className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-500"
                  value={config.ratio}
                  onChange={(e) => onUpdateRatio(key, parseFloat(e.target.value))}
                />
              </div>
            );
          })}
        </div>
        
        {isError && (
          <div className="mt-6 p-3 bg-red-50 border border-red-100 rounded-xl text-center">
            <p className="text-xs font-bold text-red-500">
              現在の合計は <span className="text-sm font-black">{(totalRatio * 100).toFixed(1)}%</span> です。リバランス計算を正確に行うために、合計が 100% になるよう調整をお願いします。
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
