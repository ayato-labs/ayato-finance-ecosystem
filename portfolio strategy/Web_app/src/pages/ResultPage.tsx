import React from 'react';
import {
  IonContent,
  IonHeader,
  IonPage,
  IonTitle,
  IonToolbar,
  IonCard,
  IonCardContent,
  IonCardHeader,
  IonCardTitle,
  IonCardSubtitle,
  IonBadge,
  IonIcon,
} from '@ionic/react';
import { 
  PieChart, 
  Pie, 
  Cell, 
  ResponsiveContainer, 
  Tooltip 
} from 'recharts';
import { checkmarkCircleOutline, alertCircleOutline } from 'ionicons/icons';
import { usePortfolioCalculator } from '../hooks/usePortfolioCalculator';
import { formatCurrency, formatPercent } from '../utils/formatter';

const ResultPage: React.FC = () => {
  const { inputs, result } = usePortfolioCalculator();

  if (!result) {
    return (
      <IonPage>
        <IonHeader>
          <IonToolbar>
            <IonTitle>分析・プラン</IonTitle>
          </IonToolbar>
        </IonHeader>
        <IonContent fullscreen>
          <div className="flex flex-col items-center justify-center h-full p-10 text-center opacity-40">
            <IonIcon icon={alertCircleOutline} className="text-6xl mb-4" />
            <p className="text-lg font-medium">資産を入力すると分析結果が表示されます</p>
          </div>
        </IonContent>
      </IonPage>
    );
  }

  const chartData = result.categoryResults.map(cat => ({
    name: cat.label,
    value: cat.currentTotal,
    color: cat.color
  }));

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle>分析・プラン</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent fullscreen>
        <div className="bg-slate-50 min-h-full pb-10">
          {/* Total Value Summary */}
          <div className="bg-white p-6 border-b border-slate-100 text-center mb-4">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Total Portfolio Value</p>
            <p className="text-3xl font-black text-slate-900">
              {formatCurrency(result.portfolioTotal, inputs.baseCurrency)}
            </p>
          </div>

          {/* Chart Section */}
          <IonCard className="rounded-2xl shadow-sm border-none mx-4 mb-6">
            <IonCardHeader>
              <IonCardTitle className="text-sm font-bold text-slate-500 uppercase tracking-wider">Current Allocation</IonCardTitle>
            </IonCardHeader>
            <IonCardContent>
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={chartData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={80}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {chartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip 
                      formatter={(value: number | string) => formatCurrency(Number(value), inputs.baseCurrency)}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="grid grid-cols-2 gap-2 mt-4">
                {result.categoryResults.map(cat => (
                  <div key={cat.key} className="flex items-center gap-2 text-xs">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: cat.color }} />
                    <span className="text-slate-500 truncate">{cat.label}</span>
                    <span className="font-bold ml-auto">{formatPercent(cat.currentRatio)}</span>
                  </div>
                ))}
              </div>
            </IonCardContent>
          </IonCard>

          {/* Rebalance Plan Section */}
          <div className="px-4 mb-4">
            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3 ml-2">Rebalance Plan</h2>
            
            {result.rebalancePlan.buyActions.length === 0 ? (
              <div className="bg-green-500 text-white p-6 rounded-2xl shadow-lg flex items-center gap-4">
                <IonIcon icon={checkmarkCircleOutline} className="text-3xl" />
                <div>
                  <p className="font-black text-lg">バランス良好！</p>
                  <p className="text-xs opacity-90">追加の購入は必要ありません。</p>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="bg-slate-900 text-white p-6 rounded-2xl shadow-xl">
                  <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">追加投資必要額</p>
                  <p className="text-3xl font-black text-blue-400">
                    {formatCurrency(result.rebalancePlan.requiredInvestment, inputs.baseCurrency)}
                  </p>
                  <p className="text-[10px] text-slate-500 mt-2">※ 売却を伴わない「ノーセル・リバランス」プランです</p>
                </div>

                {result.rebalancePlan.buyActions.map(action => (
                  <IonCard key={action.category} className="m-0 rounded-2xl border-none shadow-sm">
                    <IonCardHeader className="flex flex-row justify-between items-center py-4">
                      <div>
                        <IonCardSubtitle className="text-slate-400 text-[10px] font-black uppercase tracking-widest">Buy for</IonCardSubtitle>
                        <IonCardTitle className="text-lg font-black">{action.label}</IonCardTitle>
                      </div>
                      <IonBadge color="success" className="text-base px-3 py-1">
                        +{formatCurrency(action.amount, inputs.baseCurrency)}
                      </IonBadge>
                    </IonCardHeader>
                    <IonCardContent className="pt-0">
                      <div className="space-y-3">
                        {action.assetBreakdown.map(asset => (
                          <div key={asset.key} className="border-t border-slate-100 pt-2 first:border-0">
                            <div className="flex justify-between text-xs mb-1">
                              <span className="font-bold text-slate-600">{asset.label}</span>
                              <span className="text-slate-900">{formatCurrency(asset.amount, inputs.baseCurrency)}</span>
                            </div>
                            <div className="w-full h-1 bg-slate-100 rounded-full overflow-hidden">
                              <div 
                                className="h-full bg-blue-500"
                                style={{ width: `${asset.ratio * 100}%` }}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    </IonCardContent>
                  </IonCard>
                ))}
              </div>
            )}
          </div>
          
          <div className="h-20" />
        </div>
      </IonContent>
    </IonPage>
  );
};

export default ResultPage;
