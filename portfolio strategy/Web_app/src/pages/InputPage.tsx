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
  IonButtons,
  IonButton,
  IonIcon,
} from '@ionic/react';
import { trashOutline, colorWandOutline } from 'ionicons/icons';
import { usePortfolioCalculator } from '../hooks/usePortfolioCalculator';
import { ASSET_CONFIG } from '../constants/allocation';
import type { AssetKey } from '../types/portfolio';

const InputPage: React.FC = () => {
  const { inputs, updateAsset, reset, setSampleData } = usePortfolioCalculator();
  const assetKeys = Object.keys(ASSET_CONFIG) as AssetKey[];

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle>資産入力</IonTitle>
          <IonButtons slot="end">
            <IonButton onClick={setSampleData}>
              <IonIcon slot="icon-only" icon={colorWandOutline} />
            </IonButton>
            <IonButton onClick={reset}>
              <IonIcon slot="icon-only" icon={trashOutline} />
            </IonButton>
          </IonButtons>
        </IonToolbar>
      </IonHeader>
      <IonContent fullscreen>
        <div className="p-4 bg-slate-50 min-h-full">
          <p className="text-sm text-slate-500 mb-4 px-2">
            現在保有している資産の評価額を入力してください ({inputs.baseCurrency})。
          </p>
          
          <IonList inset={true} className="rounded-xl overflow-hidden shadow-sm">
            {assetKeys.map((key) => (
              <IonItem key={key}>
                <IonLabel position="stacked" className="font-bold text-slate-600">
                  {ASSET_CONFIG[key].label}
                </IonLabel>
                <IonInput
                  type="number"
                  placeholder="0"
                  value={inputs[key] || ''}
                  onIonInput={(e) => updateAsset(key, parseFloat(e.detail.value!) || 0)}
                  inputmode="numeric"
                  className="text-lg"
                />
              </IonItem>
            ))}
          </IonList>
          
          <div className="h-20" /> {/* Spacer for footer tabs */}
        </div>
      </IonContent>
    </IonPage>
  );
};

export default InputPage;
