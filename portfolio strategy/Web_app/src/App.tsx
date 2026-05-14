import { Redirect, Route } from 'react-router-dom';
import {
  IonApp,
  IonIcon,
  IonLabel,
  IonRouterOutlet,
  IonTabBar,
  IonTabButton,
  IonTabs,
} from '@ionic/react';
import { IonReactRouter } from '@ionic/react-router';
import { walletOutline, pieChartOutline, settingsOutline } from 'ionicons/icons';
import InputPage from './pages/InputPage';
import ResultPage from './pages/ResultPage';
import SettingsPage from './pages/SettingsPage';

const App: React.FC = () => (
  <IonApp>
    <IonReactRouter>
      <IonTabs>
        <IonRouterOutlet>
          <Route exact path="/input">
            <InputPage />
          </Route>
          <Route exact path="/result">
            <ResultPage />
          </Route>
          <Route path="/settings">
            <SettingsPage />
          </Route>
          <Route exact path="/">
            <Redirect to="/input" />
          </Route>
        </IonRouterOutlet>
        <IonTabBar slot="bottom">
          <IonTabButton tab="input" href="/input">
            <IonIcon icon={walletOutline} />
            <IonLabel>資産入力</IonLabel>
          </IonTabButton>
          <IonTabButton tab="result" href="/result">
            <IonIcon icon={pieChartOutline} />
            <IonLabel>分析・プラン</IonLabel>
          </IonTabButton>
          <IonTabButton tab="settings" href="/settings">
            <IonIcon icon={settingsOutline} />
            <IonLabel>設定</IonLabel>
          </IonTabButton>
        </IonTabBar>
      </IonTabs>
    </IonReactRouter>
  </IonApp>
);

export default App;
