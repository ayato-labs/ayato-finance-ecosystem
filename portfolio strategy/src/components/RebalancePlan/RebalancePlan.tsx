import React from 'react';
import { RebalancePlan as RebalancePlanType, Currency } from '../../types/portfolio';
import { formatCurrency } from '../../utils/formatter';
import { TrendingUp } from 'lucide-react';

interface RebalancePlanProps {
  plan: RebalancePlanType;
  baseCurrency: Currency;
}

export const RebalancePlan: React.FC<RebalancePlanProps> = ({ plan, baseCurrency }) => {
  if (plan.buyActions.length === 0) {
    return (
      <section className="bg-slate-900 text-white rounded-2xl shadow-xl p-8 text-center border border-slate-800">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-green-500/20 text-green-400 mb-4">
          <TrendingUp className="w-6 h-6" />
        </div>
        <h2 className="text-xl font-black mb-2">完璧なバランスです！</h2>
        <p className="text-slate-400 text-sm">現在の保有資産はすべて目標アロケーションの範囲内です。追加の購入は必要ありません。</p>
      </section>
    );
  }

  return (
    <section className="bg-slate-900 text-white rounded-2xl shadow-xl overflow-hidden">
      <div className="p-6 border-b border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-black tracking-tight">📊 ノーセル・リバランス提案</h2>
          <p className="text-slate-400 text-sm">資産を売却せず、追加購入のみで目標比率を達成するプラン</p>
        </div>
        <div className="text-right">
          <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">必要投資額 (追加分)</p>
          <p className="text-3xl font-black text-blue-400">
            {formatCurrency(plan.requiredInvestment, baseCurrency)}
          </p>
        </div>
      </div>

      <div className="p-6">
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-green-400 mb-4">
            <TrendingUp className="w-5 h-5" />
            <h3 className="font-black uppercase tracking-wider">推奨購入アクション</h3>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {plan.buyActions.map(action => (
              <div key={action.category} className="bg-slate-800/50 p-5 rounded-xl border border-slate-800 hover:border-slate-700 transition-colors">
                <div className="flex justify-between items-center mb-4">
                  <span className="font-black text-lg text-slate-200 uppercase tracking-tight">{action.label}</span>
                  <span className="font-black text-xl text-green-400">+{formatCurrency(action.amount, baseCurrency)}</span>
                </div>
                <div className="space-y-2">
                  {action.assetBreakdown.map(asset => (
                    <div key={asset.key} className="flex flex-col gap-1 py-2 border-t border-slate-700/50 first:border-0">
                      <div className="flex justify-between text-xs font-bold text-slate-400">
                        <span>{asset.label}</span>
                        <span className="text-slate-300">{formatCurrency(asset.amount, baseCurrency)}</span>
                      </div>
                      <div className="w-full h-1 bg-slate-700 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-blue-500"
                          style={{ width: `${asset.ratio * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="p-6 bg-slate-950/50 border-t border-slate-900 flex flex-col md:flex-row justify-between items-center gap-4">
        <div className="flex flex-col items-center md:items-start">
          <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">リバランス後の総資産額</p>
          <p className="text-xl font-black text-slate-300">
            {formatCurrency(plan.targetTotal, baseCurrency)}
          </p>
        </div>
        <p className="text-[10px] text-slate-500 uppercase font-bold tracking-widest text-center md:text-right max-w-md">
          ※ 現在の保有比率を維持して購入する前提の計算です。税金・手数料は考慮されていません。
        </p>
      </div>
    </section>
  );
};
