import React from 'react';
import {
  IonContent,
  IonHeader,
  IonPage,
  IonTitle,
  IonToolbar,
  IonList,
  IonItem,
  IonLabel,
  IonInput,
  IonSelect,
  IonSelectOption,
  IonListHeader,
} from '@ionic/react';
import { usePortfolioCalculator } from '../hooks/usePortfolioCalculator';
import type { CategoryKey } from '../types/portfolio';

const SettingsPage: React.FC = () => {
  const { inputs, targetAllocation, updateTargetRatio, updateSettings } = usePortfolioCalculator();
  const categoryKeys = Object.keys(targetAllocation) as CategoryKey[];

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle>設定</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent fullscreen>
        <div className="bg-slate-50 min-h-full">
          <IonListHeader className="text-slate-500 text-xs font-bold uppercase tracking-wider mt-4">
            基本設定
          </IonListHeader>
          <IonList inset={true} className="rounded-xl overflow-hidden shadow-sm mb-6">
            <IonItem>
              <IonLabel>表示通貨</IonLabel>
              <IonSelect
                value={inputs.baseCurrency}
                onIonChange={(e) => updateSettings({ baseCurrency: e.detail.value })}
              >
                <IonSelectOption value="JPY">JPY (日本円)</IonSelectOption>
                <IonSelectOption value="USD">USD (米ドル)</IonSelectOption>
              </IonSelect>
            </IonItem>
            <IonItem>
              <IonLabel position="stacked">許容誤差 (±%)</IonLabel>
              <IonInput
                type="number"
                value={inputs.okThreshold * 100}
                onIonInput={(e) => updateSettings({ okThreshold: (parseFloat(e.detail.value!) || 0) / 100 })}
                inputmode="decimal"
              />
            </IonItem>
          </IonList>

          <IonListHeader className="text-slate-500 text-xs font-bold uppercase tracking-wider">
            目標アセットアロケーション (%)
          </IonListHeader>
          <IonList inset={true} className="rounded-xl overflow-hidden shadow-sm">
            {categoryKeys.map((key) => (
              <IonItem key={key}>
                <div slot="start" className="w-3 h-3 rounded-full" style={{ backgroundColor: targetAllocation[key].color }} />
                <IonLabel position="stacked" className="font-bold text-slate-600">
                  {targetAllocation[key].label}
                </IonLabel>
                <IonInput
                  type="number"
                  value={targetAllocation[key].ratio * 100}
                  onIonInput={(e) => updateTargetRatio(key, (parseFloat(e.detail.value!) || 0) / 100)}
                  inputmode="decimal"
                />
              </IonItem>
            ))}
          </IonList>
          
          <div className="p-6 text-center text-xs text-slate-400">
            ※ 合計が100%になるように調整してください。
          </div>
          <div className="h-20" />
        </div>
      </IonContent>
    </IonPage>
  );
};

export default SettingsPage;
