import React from 'react';
import { AssetInput } from './AssetInput';
import { RawInputs, AssetKey, AssetResult } from '../../types/portfolio';
import { ASSET_CONFIG } from '../../constants/allocation';
import { formatCurrency } from '../../utils/formatter';

interface InputPanelProps {
  inputs: RawInputs;
  assetResults: AssetResult[] | undefined;
  onUpdateAsset: (key: AssetKey, value: number) => void;
  onReset: () => void;
  onSample: () => void;
}

export const InputPanel: React.FC<InputPanelProps> = ({
  inputs,
  assetResults,
  onUpdateAsset,
  onReset,
  onSample,
}) => {
  const assetKeys = Object.keys(ASSET_CONFIG) as AssetKey[];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {assetKeys.map((key) => {
          const config = ASSET_CONFIG[key];
          const result = assetResults?.find((r) => r.key === key);
          
          return (
            <AssetInput
              key={key}
              assetKey={key}
              label={config.label}
              currency={config.currency}
              value={inputs[key]}
              onChange={(val) => onUpdateAsset(key, val)}
              baseCurrencyValue={
                result ? formatCurrency(result.valueInBase, inputs.baseCurrency) : undefined
              }
            />
          );
        })}
      </div>
      
      <div className="flex justify-end gap-3">
        <button
          onClick={onSample}
          className="px-4 py-2 text-sm font-medium text-blue-600 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors"
        >
          サンプル入力を試す
        </button>
        <button
          onClick={onReset}
          className="px-4 py-2 text-sm font-medium text-slate-600 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors"
        >
          クリア
        </button>
      </div>
    </div>
  );
};
