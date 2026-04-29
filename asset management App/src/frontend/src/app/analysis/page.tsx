'use client';

import { useEffect, useState } from "react";

interface AssetSummary {
  ticker: string;
  asset_type: string;
  market_value: number;
  unrealized_gain: number;
  benchmark_unrealized_gain: number;
}

interface PortfolioSummary {
  total_market_value: number;
  total_unrealized_gain: number;
  gain_percent: number;
  display_currency: string;
  display_symbol: string;
  volatility: number | null;
  sharpe_ratio: number | null;
  max_drawdown: number | null;
  sortino_ratio: number | null;
  beta: number | null;
  correlation: number | null;
  macro_indicators: Record<string, number>;
  shadow_market_value: number | null;
  shadow_unrealized_gain: number | null;
  alpha_value: number | null;
  alpha_percent: number | null;
  benchmark_volatility: number | null;
  benchmark_sharpe: number | null;
  benchmark_max_drawdown: number | null;
  assets: AssetSummary[];
}

export default function AnalysisPage() {
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [currency, setCurrency] = useState('JPY');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch(`http://127.0.0.1:5007/portfolio?currency=${currency}`);
        setPortfolio(await res.json());
      } catch (err) {
        console.error("Failed to fetch data:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [currency]);

  if (loading) return <div style={{ padding: '2rem', color: 'rgba(255,255,255,0.5)' }}>Loading Evaluation Data...</div>;

  const alpha = portfolio?.alpha_value || 0;
  const alphaPct = portfolio?.alpha_percent || 0;
  const symbol = portfolio?.display_symbol || '¥';

  return (
    <main style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto' }}>
      <header style={{ marginBottom: '3rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <h1 className="gradient-text" style={{ fontSize: '3rem', margin: 0 }}>Investment Quality</h1>
          <p style={{ fontSize: '1.1rem', opacity: 0.7, marginTop: '0.5rem' }}>Decision Debugger & Risk Analysis</p>
        </div>
        <div style={{ display: 'flex', background: 'rgba(255,255,255,0.05)', borderRadius: '12px', padding: '4px' }}>
          {['JPY', 'USD', 'EUR', 'GBP', 'AUD', 'CAD'].map((c) => (
            <button
              key={c}
              onClick={() => setCurrency(c)}
              style={{
                padding: '6px 16px',
                borderRadius: '8px',
                border: 'none',
                background: currency === c ? 'var(--accent-primary)' : 'transparent',
                color: currency === c ? 'white' : 'rgba(255,255,255,0.6)',
                fontSize: '0.875rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.2s'
              }}
            >
              {c}
            </button>
          ))}
        </div>
      </header>

      {/* Alpha Analysis Section */}
      <section className="glass-card" style={{ padding: '2.5rem', marginBottom: '3rem', border: '1px solid var(--accent-primary)', position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', top: 0, left: 0, width: '4px', height: '100%', background: 'var(--accent-primary)' }}></div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <p className="stat-label" style={{ color: 'var(--accent-primary)', fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Total Portfolio Alpha (vs S&P 500)</p>
            <h2 style={{ fontSize: '3.5rem', margin: '1rem 0', color: alpha >= 0 ? 'var(--success)' : 'var(--danger)' }}>
              {alpha >= 0 ? '+' : ''}{alphaPct.toFixed(2)}%
            </h2>
            <p style={{ fontSize: '1.2rem', opacity: 0.8 }}>
              { alpha >= 0 ? 'Outperforming' : 'Underperforming' } the market by <strong>{symbol}{Math.abs(alpha).toLocaleString()}</strong>
            </p>
          </div>
          <div style={{ textAlign: 'right' }}>
            <p className="stat-label">S&P 500 Equivalent Value</p>
            <p style={{ fontSize: '1.5rem', fontWeight: 600 }}>{symbol}{portfolio?.shadow_market_value?.toLocaleString()}</p>
            <p style={{ fontSize: '0.9rem', opacity: 0.5 }}>Passive Strategy Benchmark</p>
          </div>
        </div>
        <div style={{ marginTop: '2rem', padding: '1rem', background: 'rgba(255,255,255,0.02)', borderRadius: '8px', fontSize: '0.875rem', color: 'rgba(255,255,255,0.5)', lineHeight: 1.6 }}>
          <strong>How it works:</strong> We calculate your <strong>Geometric Alpha</strong> by comparing your portfolio value against a simulated passive strategy. We simulate what would have happened if you had invested exactly the same USD amount into the S&P 500 on the same days you bought your assets. This eliminates currency noise and shows the pure quality of your stock picking and timing.
        </div>
      </section>

      {/* Crypto Alpha Section */}
      {portfolio?.assets.some(a => a.asset_type === 'CRYPTO') && (() => {
        const cryptoAssets = portfolio.assets.filter(a => a.asset_type === 'CRYPTO');
        const cAlphaVal = cryptoAssets.reduce((sum, a) => sum + (a.unrealized_gain - a.benchmark_unrealized_gain), 0);
        const cMarketVal = cryptoAssets.reduce((sum, a) => sum + a.market_value, 0);
        const cShadowVal = cryptoAssets.reduce((sum, a) => sum + (a.market_value - (a.unrealized_gain - a.benchmark_unrealized_gain)), 0);
        const cAlphaPct = cShadowVal > 0 ? (cAlphaVal / cShadowVal) * 100 : 0;

        return (
          <section className="glass-card" style={{ padding: '2.5rem', marginBottom: '3rem', border: '1px solid #F59E0B', position: 'relative', overflow: 'hidden' }}>
            <div style={{ position: 'absolute', top: 0, left: 0, width: '4px', height: '100%', background: '#F59E0B' }}></div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <p className="stat-label" style={{ color: '#F59E0B', fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Crypto Alpha (vs S&P 500)</p>
                <h2 style={{ fontSize: '3.5rem', margin: '1rem 0', color: cAlphaVal >= 0 ? 'var(--success)' : 'var(--danger)' }}>
                  {cAlphaVal >= 0 ? '+' : ''}{cAlphaPct.toFixed(2)}%
                </h2>
                <p style={{ fontSize: '1.2rem', opacity: 0.8 }}>
                  Your Crypto picks are { cAlphaVal >= 0 ? 'beating' : 'trailing' } S&P 500 by <strong>{symbol}{Math.abs(cAlphaVal).toLocaleString()}</strong>
                </p>
              </div>
              <div style={{ textAlign: 'right' }}>
                <p className="stat-label">Crypto Market Value</p>
                <p style={{ fontSize: '1.5rem', fontWeight: 600 }}>{symbol}{cMarketVal.toLocaleString()}</p>
                <p style={{ fontSize: '0.9rem', opacity: 0.5 }}>Active Crypto Exposure</p>
              </div>
            </div>
          </section>
        );
      })()}

      {/* Risk Analysis Grid */}
      <section style={{ marginBottom: '3rem' }}>
        <h3 className="stat-label" style={{ marginBottom: '1.5rem', fontSize: '1rem' }}>Risk-Adjusted Performance</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '2rem' }}>
          
          <div className="glass-card" style={{ padding: '2rem' }}>
            <p className="stat-label">Sharpe Ratio</p>
            <h4 style={{ fontSize: '2.5rem', margin: '0.5rem 0', color: (portfolio?.sharpe_ratio || 0) > (portfolio?.benchmark_sharpe || 0) ? 'var(--success)' : 'white' }}>
              {portfolio?.sharpe_ratio?.toFixed(2) ?? "N/A"}
            </h4>
            <p style={{ fontSize: '0.875rem', opacity: 0.6 }}>
              Market Benchmark: {portfolio?.benchmark_sharpe?.toFixed(2) ?? "N/A"}
            </p>
          </div>

          <div className="glass-card" style={{ padding: '2rem' }}>
            <p className="stat-label">Annual Volatility</p>
            <h4 style={{ fontSize: '2.5rem', margin: '0.5rem 0' }}>{portfolio?.volatility?.toFixed(2) ?? "N/A"}%</h4>
            <p style={{ fontSize: '0.875rem', opacity: 0.6 }}>
              Market Benchmark: {portfolio?.benchmark_volatility?.toFixed(2) ?? "N/A"}%
            </p>
          </div>

          <div className="glass-card" style={{ padding: '2rem' }}>
            <p className="stat-label">Max Drawdown</p>
            <h4 style={{ fontSize: '2.5rem', margin: '0.5rem 0', color: Math.abs(portfolio?.max_drawdown || 0) < Math.abs(portfolio?.benchmark_max_drawdown || 0) ? 'var(--success)' : 'var(--danger)' }}>
              {portfolio?.max_drawdown?.toFixed(2) ?? "N/A"}%
            </h4>
            <p style={{ fontSize: '0.875rem', opacity: 0.6 }}>
              Market Benchmark: {portfolio?.benchmark_max_drawdown?.toFixed(2) ?? "N/A"}%
            </p>
          </div>
        </div>

        <h3 style={{ margin: '2rem 0 1rem', opacity: 0.8 }}>Advanced Risk Diagnostics</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem' }}>
          <div className="glass-card" style={{ padding: '2rem' }}>
            <p className="stat-label">Sortino Ratio</p>
            <h4 style={{ fontSize: '2.5rem', margin: '0.5rem 0', color: (portfolio?.sortino_ratio || 0) > (portfolio?.sharpe_ratio || 0) ? 'var(--success)' : 'white' }}>
              {portfolio?.sortino_ratio?.toFixed(2) ?? "N/A"}
            </h4>
            <p style={{ fontSize: '0.875rem', opacity: 0.6 }}>Downside-adjusted efficiency. Higher than Sharpe is good.</p>
          </div>

          <div className="glass-card" style={{ padding: '2rem' }}>
            <p className="stat-label">Portfolio Beta (β)</p>
            <h4 style={{ fontSize: '2.5rem', margin: '0.5rem 0' }}>{portfolio?.beta?.toFixed(2) ?? "N/A"}</h4>
            <p style={{ fontSize: '0.875rem', opacity: 0.6 }}>Market sensitivity. 1.0 means same as S&P 500.</p>
          </div>

          <div className="glass-card" style={{ padding: '2rem' }}>
            <p className="stat-label">Market Correlation</p>
            <h4 style={{ fontSize: '2.5rem', margin: '0.5rem 0' }}>{portfolio?.correlation?.toFixed(2) ?? "N/A"}</h4>
            <p style={{ fontSize: '0.875rem', opacity: 0.6 }}>1.0 is perfect sync. Lower means better diversification.</p>
          </div>
        </div>
      </section>

      {/* Macro Correlation (Coming soon placeholder or basic view) */}
      <section className="glass-card" style={{ padding: '2rem', opacity: 0.6 }}>
        <p className="stat-label">Macro Correlation Analysis</p>
        <p style={{ marginTop: '1rem' }}>Analysis of how interest rates (Fed Funds, 10Y Yield) affect your portfolio alpha is in progress...</p>
      </section>
    </main>
  );
}
