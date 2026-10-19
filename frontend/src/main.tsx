import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource/roboto/400.css';
import '@fontsource/roboto/500.css';
import '@fontsource/roboto/700.css';
import 'leaflet/dist/leaflet.css';
import 'maplibre-gl/dist/maplibre-gl.css';
import './index.css';
import { ColorModeProvider } from './colorMode';
import { HistoryProvider } from './history/HistoryProvider';
import { FrequentPlacesProvider } from './places/FrequentPlacesProvider';
import { PreferencesProvider } from './preferences/PreferencesProvider';
import ErrorBoundary from './components/ErrorBoundary';
import App from './App';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <ColorModeProvider>
        <HistoryProvider>
          <PreferencesProvider>
            <FrequentPlacesProvider>
              <App />
            </FrequentPlacesProvider>
          </PreferencesProvider>
        </HistoryProvider>
      </ColorModeProvider>
    </ErrorBoundary>
  </StrictMode>,
);
