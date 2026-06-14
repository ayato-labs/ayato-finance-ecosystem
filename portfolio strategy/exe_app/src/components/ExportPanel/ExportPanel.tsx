import React, { useState } from 'react';
import { CalculationResult, RawInputs } from '../../types/portfolio';
import { formatCurrency, formatPercent } from '../../utils/formatter';
import { Copy, Check, FileText, Table } from 'lucide-react';

interface ExportPanelProps {
  result: CalculationResult;
  inputs: RawInputs;
}

export const ExportPanel: React.FC<ExportPanelProps> = ({
  result,
  inputs,
}) => {
  const [copiedType, setCopiedType] = useState<'md' | 'csv' | null>(null);

  const getJstTimestamp = () => {
    const now = new Date();
    const jstOffset = 9 * 60; // JST is UTC+9
    const localOffset = now.getTimezoneOffset();
    const jstTime = new Date(now.getTime() + (jstOffset + localOffset) * 60000);
    const Y = jstTime.getFullYear();
    const M = String(jstTime.getMonth() + 1).padStart(2, '0');
    const D = String(jstTime.getDate()).padStart(2, '0');
    const h = String(jstTime.getHours()).padStart(2, '0');
    const m = String(jstTime.getMinutes()).padStart(2, '0');
    return `${Y}年${M}月${D}日 ${h}時${m}分 (JST)`;
  };

  const mdText = React.useMemo(() => {
    const timestamp = getJstTimestamp();
    const currency = inputs.baseCurrency;
    let md = `# Portfolio Rebalance Report\n**生成日時**: ${timestamp}\n\n`;
    md += `## 1. 概要\n- **総資産額**: ${formatCurrency(result.portfolioTotal, currency)}\n- **必要投資額**: ${formatCurrency(result.rebalancePlan.requiredInvestment, currency)}\n- **通貨モード**: ${currency}\n- **許容誤差**: ±${(inputs.okThreshold * 100).toFixed(1)}%\n\n`;
    md += `## 2. 目標戦略\n| カテゴリ | 目標 | 現在 | ステータス |\n| :--- | :---: | :---: | :---: |\n`;
    result.categoryResults.forEach(cat => {
      md += `| ${cat.label} | ${formatPercent(cat.targetRatio)} | ${formatPercent(cat.currentRatio)} | ${cat.status} |\n`;
    });
    md += `\n## 3. アセット内訳\n| アセット名 | カテゴリ | 評価額 | 構成比 |\n| :--- | :--- | :---: | :---: |\n`;
    result.assetResults.forEach(asset => {
      md += `| ${asset.label} | ${asset.category} | ${formatCurrency(asset.valueInBase, currency)} | ${formatPercent(asset.valueInBase / result.portfolioTotal)} |\n`;
    });
    md += `\n## 4. 推奨アクション\n`;
    if (result.rebalancePlan.buyActions.length === 0) {
      md += `リバランス不要。目標比率を維持しています。\n`;
    } else {
      result.rebalancePlan.buyActions.forEach(action => {
        md += `### ${action.label} 購入 (+${formatCurrency(action.amount, currency)})\n`;
        action.assetBreakdown.forEach(ab => md += `- ${ab.label}: **${formatCurrency(ab.amount, currency)}**\n`);
      });
    }
    return md;
  }, [result, inputs]);

  const csvText = React.useMemo(() => {
    const timestamp = getJstTimestamp();
    const currency = inputs.baseCurrency;
    let csv = `Generated At,${timestamp}\nCurrency,${currency}\n\nType,Name,Category,Value,Ratio(%),TargetRatio(%),Status\n`;
    result.assetResults.forEach(asset => {
      csv += `Asset,${asset.label},${asset.category},${asset.valueInBase},${(asset.valueInBase / result.portfolioTotal * 100).toFixed(2)},-,\n`;
    });
    result.categoryResults.forEach(cat => {
      csv += `Category,${cat.label},-,${cat.currentTotal},${(cat.currentRatio * 100).toFixed(2)},${(cat.targetRatio * 100).toFixed(2)},${cat.status}\n`;
    });
    return csv;
  }, [result, inputs]);

  const handleCopy = (text: string, type: 'md' | 'csv') => {
    navigator.clipboard.writeText(text);
    setCopiedType(type);
    setTimeout(() => setCopiedType(null), 2000);
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-8">
      {/* Markdown Export */}
      <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden flex flex-col shadow-sm">
        <div className="px-4 py-3 bg-slate-800 text-white flex justify-between items-center">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-blue-400" />
            <span className="text-xs font-black uppercase tracking-wider">AI分析用 (Markdown)</span>
          </div>
          <button 
            onClick={() => handleCopy(mdText, 'md')}
            className="flex items-center gap-1.5 px-2 py-1 bg-slate-700 hover:bg-slate-600 rounded-md transition-colors text-[10px] font-bold"
          >
            {copiedType === 'md' ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
            {copiedType === 'md' ? 'COPIED!' : 'COPY'}
          </button>
        </div>
        <textarea 
          readOnly 
          className="p-4 text-[11px] font-mono text-slate-600 bg-slate-50/50 h-48 outline-none resize-none leading-relaxed"
          value={mdText}
        />
      </div>

      {/* CSV Export */}
      <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden flex flex-col shadow-sm">
        <div className="px-4 py-3 bg-slate-50 border-b border-slate-100 flex justify-between items-center">
          <div className="flex items-center gap-2 text-slate-600">
            <Table className="w-4 h-4 text-green-600" />
            <span className="text-xs font-black uppercase tracking-wider">データ管理用 (CSV)</span>
          </div>
          <button 
            onClick={() => handleCopy(csvText, 'csv')}
            className="flex items-center gap-1.5 px-2 py-1 bg-white border border-slate-200 hover:bg-slate-50 rounded-md transition-colors text-[10px] font-bold text-slate-600"
          >
            {copiedType === 'csv' ? <Check className="w-3 h-3 text-green-600" /> : <Copy className="w-3 h-3" />}
            {copiedType === 'csv' ? 'COPIED!' : 'COPY'}
          </button>
        </div>
        <textarea 
          readOnly 
          className="p-4 text-[11px] font-mono text-slate-500 bg-white h-48 outline-none resize-none leading-relaxed"
          value={csvText}
        />
      </div>
    </div>
  );
};
