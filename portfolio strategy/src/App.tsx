import { Header } from './components/Header/Header';
import { InputPanel } from './components/InputPanel/InputPanel';
import { SummaryBar } from './components/SummaryBar/SummaryBar';
import { CategoryCard } from './components/AllocationView/CategoryCard';
import { DonutChart } from './components/AllocationView/DonutChart';
import { RebalancePlan } from './components/RebalancePlan/RebalancePlan';
import { usePortfolioCalculator } from './hooks/usePortfolioCalculator';
import { formatCurrency } from './utils/formatter';

function App() {
  const { 
    inputs, 
    result, 
    updateAsset, 
    updateSettings, 
    reset, 
    setSampleData 
  } = usePortfolioCalculator();

  return (
    <div className="min-h-screen bg-slate-50 pb-20 px-4 sm:px-6 lg:px-8">
      <div className="max-w-5xl mx-auto pt-8">
        <Header 
          baseCurrency={inputs.baseCurrency}
          fxRate={inputs.fxRate}
          okThreshold={inputs.okThreshold}
          onUpdateSettings={updateSettings}
        />
        
        <section className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden mb-8">
          <div className="p-6 border-b border-slate-100 bg-slate-50/50">
            <h2 className="text-lg font-bold text-slate-800">資産入力</h2>
            <p className="text-sm text-slate-500">現在保有している資産の評価額を入力してください。</p>
          </div>
          <div className="p-6">
            <InputPanel 
              inputs={inputs}
              assetResults={result?.assetResults}
              onUpdateAsset={updateAsset}
              onReset={reset}
              onSample={setSampleData}
            />
          </div>
          {result && <SummaryBar categoryResults={result.categoryResults} />}
        </section>

        {result && (
          <>
            <section className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden mb-8 p-6 text-center">
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Total Portfolio Value</p>
              <p className="text-4xl font-black text-slate-900">
                {formatCurrency(result.portfolioTotal, inputs.baseCurrency)}
              </p>
            </section>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                <DonutChart data={result.categoryResults} title="Current Allocation" type="current" />
              </div>
              <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                <DonutChart data={result.categoryResults} title="Target Allocation" type="target" />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
              {result.categoryResults.map(cat => (
                <CategoryCard key={cat.key} result={cat} baseCurrency={inputs.baseCurrency} />
              ))}
            </div>

            <RebalancePlan plan={result.rebalancePlan} baseCurrency={inputs.baseCurrency} />
          </>
        )}

        {!result && (
          <div className="text-center py-20 opacity-40">
            <p className="text-lg font-medium">アセットの金額を入力すると計算結果が表示されます</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
