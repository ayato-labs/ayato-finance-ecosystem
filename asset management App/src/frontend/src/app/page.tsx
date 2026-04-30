'use client';

import { useEffect, useState } from "react";
import Link from "next/link";

interface Asset {
  id: string;
  ticker: string;
  total_quantity: number;
  average_price: number;
  current_price: number | null;
  market_value: number;
  unrealized_gain: number;
  gain_percent: number;
  weight: number;
  currency: string;
  asset_type: string;
  benchmark_gain_percent?: number;
  benchmark_unrealized_gain?: number;
  crypto_metadata?: {
    circulating_supply: number;
    total_supply: number;
    max_supply: number | null;
    market_cap: number;
    description: string;
  } | null;
}

interface Benchmark {
  name: string;
  ticker: string;
  gain_percent: number;
}

interface PortfolioSummary {
  total_market_value: number;
  total_unrealized_gain: number;
  gain_percent: number;
  display_currency: string;
  assets: Asset[];
  benchmarks: Benchmark[];
  macro_indicators: Record<string, number>;
  shadow_gain_percent?: number;
  shadow_unrealized_gain?: number;
}

const getCurrencySymbol = (currency: string) => {
  switch (currency.toUpperCase()) {
    case 'JPY': return '¥';
    case 'USD': return '$';
    case 'EUR': return '€';
    case 'CNY': return '元';
    default: return currency;
  }
};

const formatValue = (value: number, currency: string) => {
  const symbol = getCurrencySymbol(currency);
  if (currency === 'JPY') {
    return `${symbol}${Math.round(value).toLocaleString()}`;
  }
  return `${symbol}${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

export default function DashboardPage() {
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [currency, setCurrency] = useState('JPY');

  useEffect(() => {
    fetchData();
  }, [currency]);

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

  if (loading) return <div style={{ padding: '2rem', color: 'rgba(255,255,255,0.5)' }}>Loading Dashboard...</div>;
  if (!portfolio) return <div style={{ padding: '2rem', color: 'var(--danger)' }}>Failed to load portfolio data. Please check if the backend is running.</div>;

  const symbol = portfolio?.display_symbol || '¥';

  return (
    <main style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto' }}>
      <header style={{ marginBottom: '3rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '2rem', marginBottom: '0.5rem' }}>
            <h1 className="gradient-text" style={{ fontSize: '3rem', margin: 0 }}>Portfolio Overview</h1>
            <div style={{ display: 'flex', background: 'rgba(255,255,255,0.05)', borderRadius: '12px', padding: '4px', marginTop: '8px' }}>
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
          </div>
          <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: '1.1rem' }}>Real-time Market Exposure & Performance</p>
        </div>
        <div style={{ textAlign: 'right' }}>
          <p className="stat-label">Total Market Value</p>
          <div style={{ fontSize: '2.5rem', fontWeight: 800 }}>
            {formatValue(portfolio?.total_market_value || 0, portfolio?.display_currency || 'JPY')}
          </div>
        </div>
      </header>

      {/* Summary Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem', marginBottom: '3rem' }}>
        <div className="glass-card" style={{ padding: '2rem', background: 'rgba(99, 102, 241, 0.05)' }}>
          <p className="stat-label">Total Unrealized Gain</p>
          <h2 style={{ fontSize: '2.5rem', color: (portfolio?.total_unrealized_gain || 0) >= 0 ? 'var(--success)' : 'var(--danger)' }}>
            {portfolio?.total_unrealized_gain && portfolio.total_unrealized_gain >= 0 ? '+' : ''}
            {formatValue(portfolio?.total_unrealized_gain || 0, portfolio?.display_currency || 'JPY')}
          </h2>
          <p style={{ fontSize: '1.1rem', fontWeight: 600, opacity: 0.5 }}>
            {(portfolio?.gain_percent ?? 0).toFixed(2)}% Return Rate
          </p>
        </div>

        <div className="glass-card" style={{ padding: '2rem' }}>
          <p className="stat-label">S&P 500 Benchmark</p>
          <h2 style={{ fontSize: '2.5rem', color: (portfolio?.shadow_gain_percent ?? 0) >= 0 ? 'var(--success)' : 'var(--danger)' }}>
            {(portfolio?.shadow_gain_percent ?? 0) >= 0 ? '+' : ''}{(portfolio?.shadow_gain_percent ?? 0).toFixed(2)}%
          </h2>
          <p style={{ fontSize: '1.1rem', fontWeight: 600, opacity: 0.5 }}>
            {(portfolio?.shadow_unrealized_gain ?? 0) >= 0 ? '+' : ''}{formatValue(portfolio?.shadow_unrealized_gain || 0, portfolio?.display_currency || 'JPY')} Potential
          </p>
        </div>

        {(portfolio?.benchmarks || []).filter(b => b.ticker !== '^GSPC').map((bench) => (
          <div key={bench.ticker} className="glass-card" style={{ padding: '2rem' }}>
            <p className="stat-label">{bench.name} Benchmark</p>
            <h2 style={{ fontSize: '2.5rem', color: (bench.gain_percent ?? 0) >= 0 ? 'var(--success)' : 'var(--danger)' }}>
              {(bench.gain_percent ?? 0) >= 0 ? '+' : ''}{(bench.gain_percent ?? 0).toFixed(2)}%
            </h2>
            <p style={{ fontSize: '0.875rem', opacity: 0.5 }}>Passive Market Context</p>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '2rem' }}>
        {/* Assets Table */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          {/* Stock Assets Table */}
          {portfolio?.assets.some(a => a.asset_type === 'STOCK') && (
            <div className="glass-card" style={{ padding: '2rem' }}>
              <h3 className="gradient-text" style={{ fontSize: '1.25rem', marginBottom: '1.5rem' }}>Stock Portfolio</h3>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--glass-border)', color: 'rgba(255,255,255,0.4)', fontSize: '0.875rem' }}>
                    <th style={{ paddingBottom: '1rem' }}>Asset</th>
                    <th style={{ paddingBottom: '1rem' }}>Weight</th>
                    <th style={{ paddingBottom: '1rem' }}>Market Value</th>
                    <th style={{ paddingBottom: '1rem', textAlign: 'right' }}>S&P 500 Benchmark</th>
                    <th style={{ paddingBottom: '1rem', textAlign: 'right' }}>Performance</th>
                  </tr>
                </thead>
                <tbody>
                  {(portfolio?.assets || []).filter(a => a.asset_type === 'STOCK').sort((a,b) => b.market_value - a.market_value).map((asset) => (
                    <tr key={asset.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                      <td style={{ padding: '1.25rem 0' }}>
                        <div style={{ fontWeight: 700 }}>{asset.ticker}</div>
                        <div style={{ fontSize: '0.75rem', opacity: 0.5 }}>{asset.total_quantity} Units</div>
                      </td>
                      <td>
                        <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>{(asset.weight ?? 0).toFixed(1)}%</div>
                        <div style={{ width: '60px', height: '4px', background: 'rgba(255,255,255,0.1)', borderRadius: '2px', marginTop: '4px' }}>
                          <div style={{ width: `${asset.weight}%`, height: '100%', background: 'var(--accent-primary)' }} />
                        </div>
                      </td>
                      <td>
                        <div style={{ fontSize: '1rem', fontWeight: 600 }}>
                          {formatValue(asset.market_value, portfolio.display_currency)}
                        </div>
                        {asset.total_quantity !== 1 && (
                          <div style={{ fontSize: '0.75rem', opacity: 0.5 }}>
                            Price: {formatValue(asset.current_price || 0, portfolio.display_currency)}
                          </div>
                        )}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ color: (asset.benchmark_gain_percent ?? 0) >= 0 ? 'var(--success)' : 'var(--danger)', fontWeight: 600 }}>
                          {(asset.benchmark_gain_percent ?? 0) >= 0 ? '+' : ''}{(asset.benchmark_gain_percent ?? 0).toFixed(2)}%
                        </div>
                        <div style={{ fontSize: '0.85rem', fontWeight: 500, opacity: 0.8 }}>
                          {(asset.benchmark_unrealized_gain ?? 0) >= 0 ? '+' : ''}{formatValue(asset.benchmark_unrealized_gain || 0, portfolio.display_currency)}
                        </div>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ color: (asset.unrealized_gain ?? 0) >= 0 ? 'var(--success)' : 'var(--danger)', fontWeight: 700, fontSize: '1.1rem' }}>
                          {(asset.gain_percent ?? 0) >= 0 ? '+' : ''}{(asset.gain_percent ?? 0).toFixed(2)}%
                        </div>
                        <div style={{ fontSize: '0.75rem', opacity: 0.5 }}>
                          {asset.unrealized_gain >= 0 ? '+' : ''}{formatValue(asset.unrealized_gain, portfolio.display_currency)}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Crypto Assets Table */}
          {portfolio?.assets.some(a => a.asset_type === 'CRYPTO') && (
            <div className="glass-card" style={{ padding: '2rem', border: '1px solid rgba(245, 158, 11, 0.2)' }}>
              <h3 className="gradient-text" style={{ fontSize: '1.25rem', marginBottom: '1.5rem', background: 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)', WebkitBackgroundClip: 'text' }}>Crypto Portfolio</h3>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--glass-border)', color: 'rgba(255,255,255,0.4)', fontSize: '0.875rem' }}>
                    <th style={{ paddingBottom: '1rem' }}>Asset</th>
                    <th style={{ paddingBottom: '1rem' }}>Weight</th>
                    <th style={{ paddingBottom: '1rem' }}>Market Value</th>
                    <th style={{ paddingBottom: '1rem', textAlign: 'right' }}>S&P 500 Benchmark</th>
                    <th style={{ paddingBottom: '1rem', textAlign: 'right' }}>Performance</th>
                  </tr>
                </thead>
                <tbody>
                  {(portfolio?.assets || []).filter(a => a.asset_type === 'CRYPTO').sort((a,b) => b.market_value - a.market_value).map((asset) => (
                    <tr key={asset.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                      <td style={{ padding: '1.25rem 0' }}>
                        <div style={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span style={{ color: '#F59E0B' }}>₿</span> {asset.ticker}
                        </div>
                        <div style={{ fontSize: '0.75rem', opacity: 0.5 }}>{asset.total_quantity} Units</div>
                        {asset.crypto_metadata && (
                          <div style={{ fontSize: '0.65rem', opacity: 0.4, marginTop: '4px', fontStyle: 'italic' }}>
                            Supply: {(asset.crypto_metadata.circulating_supply / 1000000).toLocaleString(undefined, {maximumFractionDigits: 1})}M
                            {asset.crypto_metadata.max_supply ? ` / ${(asset.crypto_metadata.max_supply / 1000000).toLocaleString(undefined, {maximumFractionDigits: 1})}M` : ' (No Cap)'}
                          </div>
                        )}
                      </td>
                      <td>
                        <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>{(asset.weight ?? 0).toFixed(1)}%</div>
                        <div style={{ width: '60px', height: '4px', background: 'rgba(255,255,255,0.1)', borderRadius: '2px', marginTop: '4px' }}>
                          <div style={{ width: `${asset.weight}%`, height: '100%', background: '#F59E0B' }} />
                        </div>
                      </td>
                      <td>
                        <div style={{ fontSize: '1rem', fontWeight: 600 }}>
                          {formatValue(asset.market_value, portfolio.display_currency)}
                        </div>
                        <div style={{ fontSize: '0.75rem', opacity: 0.5 }}>
                          Price: {formatValue(asset.current_price || 0, portfolio.display_currency)}
                        </div>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ color: (asset.benchmark_gain_percent ?? 0) >= 0 ? 'var(--success)' : 'var(--danger)', fontWeight: 600 }}>
                          {(asset.benchmark_gain_percent ?? 0) >= 0 ? '+' : ''}{(asset.benchmark_gain_percent ?? 0).toFixed(2)}%
                        </div>
                        <div style={{ fontSize: '0.85rem', fontWeight: 500, opacity: 0.8 }}>
                          {(asset.benchmark_unrealized_gain ?? 0) >= 0 ? '+' : ''}{formatValue(asset.benchmark_unrealized_gain || 0, portfolio.display_currency)}
                        </div>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ color: (asset.unrealized_gain ?? 0) >= 0 ? 'var(--success)' : 'var(--danger)', fontWeight: 700, fontSize: '1.1rem' }}>
                          {(asset.gain_percent ?? 0) >= 0 ? '+' : ''}{(asset.gain_percent ?? 0).toFixed(2)}%
                        </div>
                        <div style={{ fontSize: '0.75rem', opacity: 0.5 }}>
                          {asset.unrealized_gain >= 0 ? '+' : ''}{formatValue(asset.unrealized_gain, portfolio.display_currency)}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Macro & Sidebar */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          <div className="glass-card" style={{ padding: '2rem' }}>
            <h3 className="stat-label" style={{ marginBottom: '1.5rem' }}>Macro Environment</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              {portfolio?.macro_indicators && Object.entries(portfolio.macro_indicators).map(([name, value]) => (
                <div key={name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.875rem', opacity: 0.7 }}>{name}</span>
                  <span style={{ fontSize: '1.25rem', fontWeight: 700 }}>{(value ?? 0).toFixed(2)}%</span>
                </div>
              ))}
            </div>
          </div>

          <div className="glass-card" style={{ padding: '2rem', border: '1px dashed var(--accent-primary)', textAlign: 'center' }}>
            <p style={{ fontSize: '0.875rem', marginBottom: '1rem', opacity: 0.8 }}>Ready to audit your performance?</p>
            <Link href="/analysis" style={{ textDecoration: 'none' }}>
              <button style={{ width: '100%' }}>View Alpha Analysis</button>
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
