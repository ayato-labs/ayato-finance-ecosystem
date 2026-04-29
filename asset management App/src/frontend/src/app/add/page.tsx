"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function AddTrade() {
  const router = useRouter();
  const getLocalISOString = (date: Date) => {
    const tzOffset = date.getTimezoneOffset() * 60000; // offset in milliseconds
    const localISOTime = new Date(date.getTime() - tzOffset).toISOString().slice(0, 16);
    return localISOTime;
  };

  const [formData, setFormData] = useState({
    ticker: "",
    type: "BUY",
    asset_type: "STOCK",
    quantity: "",
    price: "",
    fee: "0",
    timestamp: getLocalISOString(new Date()), // Local time YYYY-MM-DDTHH:MM
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch("http://127.0.0.1:5007/transactions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: formData.ticker,
          type: formData.type,
          asset_type: formData.asset_type,
          quantity: parseFloat(formData.quantity),
          price: parseFloat(formData.price),
          fee: parseFloat(formData.fee),
          timestamp: new Date(formData.timestamp).toISOString(),
        }),
      });
      if (res.ok) {
        router.push("/");
      }
    } catch (err) {
      console.error("Failed to add trade:", err);
    }
  };

  return (
    <div style={{ padding: '2rem', maxWidth: '600px', margin: '0 auto' }}>
      <div className="glass-card" style={{ padding: '2rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
          <h2 className="gradient-text" style={{ margin: 0 }}>Record Transaction</h2>
          <button 
            onClick={() => router.push("/")}
            style={{ 
              background: 'transparent', 
              border: 'none', 
              color: 'rgba(255,255,255,0.5)', 
              cursor: 'pointer',
              fontSize: '0.875rem'
            }}
          >
            ✁EClose
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* ... existing form fields ... */}
          <div className="form-group">
            <label className="stat-label">Transaction Date & Time</label>
            <input 
              type="datetime-local"
              value={formData.timestamp}
              onChange={(e) => setFormData({...formData, timestamp: e.target.value})}
              required
              style={{ width: '100%', padding: '0.8rem', borderRadius: '8px', border: '1px solid var(--glass-border)', background: 'rgba(255,255,255,0.05)', color: 'white' }}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div className="form-group">
              <label className="stat-label">Ticker Symbol</label>
              <input 
                type="text" 
                placeholder="AAPL, BTC, etc."
                value={formData.ticker}
                onChange={(e) => setFormData({...formData, ticker: e.target.value.toUpperCase()})}
                required
                style={{ width: '100%' }}
              />
            </div>
            <div className="form-group">
              <label className="stat-label">Asset Type</label>
              <select 
                value={formData.asset_type}
                onChange={(e) => setFormData({...formData, asset_type: e.target.value})}
                style={{ width: '100%', padding: '0.8rem', borderRadius: '8px', border: '1px solid var(--glass-border)', background: 'rgba(255,255,255,0.05)', color: 'white' }}
              >
                <option value="STOCK">Stock</option>
                <option value="CRYPTO">Crypto</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label className="stat-label">Transaction Type</label>
            <select 
              value={formData.type}
              onChange={(e) => setFormData({...formData, type: e.target.value})}
              style={{ width: '100%', padding: '0.8rem', borderRadius: '8px', border: '1px solid var(--glass-border)', background: 'rgba(255,255,255,0.05)', color: 'white' }}
            >
              <option value="BUY">Buy</option>
              <option value="SELL">Sell</option>
            </select>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div className="form-group">
              <label className="stat-label">Quantity</label>
              <input 
                type="number" 
                step="any"
                value={formData.quantity}
                onChange={(e) => setFormData({...formData, quantity: e.target.value})}
                required
                style={{ width: '100%' }}
              />
            </div>
            <div className="form-group">
              <label className="stat-label">Price</label>
              <input 
                type="number" 
                step="any"
                value={formData.price}
                onChange={(e) => setFormData({...formData, price: e.target.value})}
                required
                style={{ width: '100%' }}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="stat-label">Fee (Optional)</label>
            <input 
              type="number" 
              step="any"
              value={formData.fee}
              onChange={(e) => setFormData({...formData, fee: e.target.value})}
              style={{ width: '100%' }}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginTop: '1rem' }}>
            <button 
              type="button"
              onClick={() => router.push("/")}
              className="glass-card"
              style={{ 
                padding: '1rem', 
                background: 'rgba(255,255,255,0.05)', 
                border: '1px solid var(--glass-border)', 
                color: 'white',
                cursor: 'pointer'
              }}
            >
              Cancel
            </button>
            <button 
              type="submit" 
              className="glass-card" 
              style={{ 
                padding: '1rem', 
                background: 'var(--accent-primary)', 
                border: 'none', 
                color: 'white', 
                fontWeight: 'bold',
                cursor: 'pointer'
              }}
            >
              Save Transaction
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
