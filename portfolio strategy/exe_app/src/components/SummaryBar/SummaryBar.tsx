import React from 'react';
import { CategoryResult } from '../../types/portfolio';
import { CheckCircle2, AlertTriangle, XCircle } from 'lucide-react';

interface SummaryBarProps {
  categoryResults: CategoryResult[];
}

export const SummaryBar: React.FC<SummaryBarProps> = ({ categoryResults }) => {
  const counts = {
    OK: categoryResults.filter(r => r.status === 'OK').length,
    OVER: categoryResults.filter(r => r.status === 'OVER').length,
    UNDER: categoryResults.filter(r => r.status === 'UNDER').length,
  };

  return (
    <div className="flex flex-wrap items-center justify-center gap-6 px-6 py-3 bg-white border-b border-slate-100">
      <div className="flex items-center gap-2">
        <CheckCircle2 className="w-4 h-4 text-green-500" />
        <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">OK:</span>
        <span className="text-sm font-black text-slate-800">{counts.OK}</span>
      </div>
      <div className="flex items-center gap-2">
        <XCircle className="w-4 h-4 text-red-500" />
        <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">OVER:</span>
        <span className="text-sm font-black text-slate-800">{counts.OVER}</span>
      </div>
      <div className="flex items-center gap-2">
        <AlertTriangle className="w-4 h-4 text-amber-500" />
        <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">UNDER:</span>
        <span className="text-sm font-black text-slate-800">{counts.UNDER}</span>
      </div>
    </div>
  );
};
