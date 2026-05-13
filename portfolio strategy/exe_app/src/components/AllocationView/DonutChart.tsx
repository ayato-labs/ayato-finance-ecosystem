import React from 'react';
import { 
  PieChart, 
  Pie, 
  Cell, 
  ResponsiveContainer, 
  Tooltip
} from 'recharts';
import { CategoryResult } from '../../types/portfolio';
import { formatPercent } from '../../utils/formatter';

interface DonutChartProps {
  data: CategoryResult[];
  title: string;
  type: 'current' | 'target';
}

export const DonutChart: React.FC<DonutChartProps> = ({ data, title, type }) => {
  const chartData = data.map(cat => ({
    name: cat.label,
    value: type === 'current' ? cat.currentRatio : cat.targetRatio,
    amount: type === 'current' ? cat.currentTotal : cat.targetTotal,
    color: cat.color,
  }));

  return (
    <div className="flex flex-col items-center">
      <h3 className="text-xs font-black text-slate-400 uppercase tracking-widest mb-4">{title}</h3>
      <div className="w-full h-64">
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
                <Cell key={`cell-${index}`} fill={entry.color} stroke="none" />
              ))}
            </Pie>
            <Tooltip 
              formatter={(value: number) => formatPercent(value)}
              contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
