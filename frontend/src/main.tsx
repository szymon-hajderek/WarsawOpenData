import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource/roboto/400.css';
import '@fontsource/roboto/500.css';
import '@fontsource/roboto/700.css';
import 'leaflet/dist/leaflet.css';
import 'maplibre-gl/dist/maplibre-gl.css';
import './index.css';
import { ColorModeProvider } from './colorMode';
import { MapVariantProvider } from './mapVariant';
import App from './App';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ColorModeProvider>
      <MapVariantProvider>
        <App />
      </MapVariantProvider>
    </ColorModeProvider>
  </StrictMode>,
);
