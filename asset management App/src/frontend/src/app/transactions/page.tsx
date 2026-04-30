'use client';

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

export default function TransactionsPage() {
  const router = useRouter();
  const [transactions, setTransactions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);

  const getLocalISOString = (date: Date) => {
    const tzOffset = date.getTimezoneOffset() * 60000;
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
    timestamp: getLocalISOString(new Date()),
  });

  useEffect(() => {
    fetchTransactions();
  }, []);

  const fetchTransactions = async () => {
    try {
      const res = await fetch("http://127.0.0.1:5007/transactions");
      setTransactions(await res.json());
    } catch (err) {
      console.error("Failed to fetch transactions:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const url = editingId 
      ? `http://127.0.0.1:5007/transactions/${editingId}`
      : "http://127.0.0.1:5007/transactions";
    const method = editingId ? "PUT" : "POST";

    try {
      const res = await fetch(url, {
        method: method,
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
        setFormData({ ...formData, ticker: "", quantity: "", price: "" });
        setEditingId(null);
        fetchTransactions();
      }
    } catch (err) {
      console.error(`Failed to ${editingId ? 'update' : 'add'} trade:`, err);
    }
  };

  const handleEdit = (tx: any) => {
    setEditingId(tx.id);
    setFormData({
      ticker: tx.ticker,
      type: tx.type,
      asset_type: tx.asset_type,
      quantity: tx.quantity.toString(),
      price: tx.price.toString(),
      fee: tx.fee.toString(),
      timestamp: getLocalISOString(new Date(tx.timestamp)),
    });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setFormData({
      ticker: "",
      type: "BUY",
      asset_type: "STOCK",
      quantity: "",
      price: "",
      fee: "0",
      timestamp: getLocalISOString(new Date()),
    });
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Are you sure?")) return;
    try {
      await fetch(`http://127.0.0.1:5007/transactions/${id}`, { method: "DELETE" });
      fetchTransactions();
    } catch (err) {
      console.error("Delete failed:", err);
    }
  };

  if (loading) return <div style={{ padding: '2rem', color: 'rgba(255,255,255,0.5)' }}>Loading History...</div>;

  return (
    <main style={{ padding: '2rem', maxWidth: '1000px', margin: '0 auto' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: '2rem' }}>
        
        {/* Registration Form */}
        <div style={{ position: 'sticky', top: '5rem', height: 'fit-content' }}>
          <div className="glass-card" style={{ padding: '2rem', border: editingId ? '1px solid var(--accent-primary)' : 'none' }}>
            <h2 className="gradient-text" style={{ fontSize: '1.25rem', marginBottom: '1.5rem' }}>
              {editingId ? "Edit Transaction" : "Add New Trade"}
            </h2>
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <label className="stat-label">Asset & Time</label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: '0.5rem' }}>
                  <input 
                    type="text" 
                    placeholder="Ticker" 
                    value={formData.ticker} 
                    onChange={(e) => setFormData({...formData, ticker: e.target.value.toUpperCase()})}
                    required
                  />
                  <input 
                    type="datetime-local" 
                    value={formData.timestamp} 
                    onChange={(e) => setFormData({...formData, timestamp: e.target.value})}
                    required
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  <label className="stat-label">Type</label>
                  <select value={formData.type} onChange={(e) => setFormData({...formData, type: e.target.value})}>
                    <option value="BUY">BUY</option>
                    <option value="SELL">SELL</option>
                  </select>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  <label className="stat-label">Asset Type</label>
                  <select value={formData.asset_type} onChange={(e) => setFormData({...formData, asset_type: e.target.value})}>
                    <option value="STOCK">Stock</option>
                    <option value="CRYPTO">Crypto</option>
                  </select>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  <label className="stat-label">Quantity</label>
                  <input type="number" step="any" value={formData.quantity} onChange={(e) => setFormData({...formData, quantity: e.target.value})} required />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  <label className="stat-label">Price</label>
                  <input type="number" step="any" value={formData.price} onChange={(e) => setFormData({...formData, price: e.target.value})} required />
                </div>
              </div>

              <div style={{ display: 'flex', gap: '1rem' }}>
                <button type="submit" style={{ flex: 2, marginTop: '1rem', padding: '1rem' }}>
                  {editingId ? "Update Record" : "Save Record"}
                </button>
                {editingId && (
                  <button 
                    type="button" 
                    onClick={cancelEdit}
                    style={{ flex: 1, marginTop: '1rem', padding: '1rem', background: 'rgba(255,255,255,0.05)', color: 'white' }}
                  >
                    Cancel
                  </button>
                )}
              </div>
            </form>
          </div>
        </div>

        {/* Transaction History */}
        <div className="glass-card" style={{ padding: '2rem' }}>
          <h2 className="gradient-text" style={{ fontSize: '1.25rem', marginBottom: '1.5rem' }}>Audit Log</h2>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--glass-border)', color: 'rgba(255,255,255,0.4)' }}>
                  <th style={{ paddingBottom: '1rem' }}>Date</th>
                  <th style={{ paddingBottom: '1rem' }}>Asset</th>
                  <th style={{ paddingBottom: '1rem' }}>Type</th>
                  <th style={{ paddingBottom: '1rem' }}>Qty</th>
                  <th style={{ paddingBottom: '1rem', textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((tx) => (
                  <tr key={tx.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                    <td style={{ padding: '1rem 0' }}>{new Date(tx.timestamp).toLocaleDateString()}</td>
                    <td style={{ fontWeight: 600 }}>{tx.ticker}</td>
                    <td style={{ color: tx.type === 'BUY' ? 'var(--success)' : 'var(--danger)' }}>{tx.type}</td>
                    <td>{tx.quantity}</td>
                    <td style={{ textAlign: 'right', display: 'flex', justifyContent: 'flex-end', gap: '1rem', padding: '1rem 0' }}>
                      <button 
                        onClick={() => handleEdit(tx)}
                        style={{ background: 'transparent', border: 'none', color: 'var(--accent-primary)', cursor: 'pointer', fontWeight: 600 }}
                      >
                        Edit
                      </button>
                      <button 
                        onClick={() => handleDelete(tx.id)}
                        style={{ background: 'transparent', border: 'none', color: 'rgba(255,255,255,0.3)', cursor: 'pointer' }}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </main>
  );
}
