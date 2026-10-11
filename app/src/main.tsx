import './react-global';
import React from 'react';
import { createRoot } from 'react-dom/client';
import './generated/tokens.css';
import '../../design_system/components/bundle.css';
import 'maplibre-gl/dist/maplibre-gl.css';
import 'pannellum/build/pannellum.css';
import './app.css';
import './focus.css';
import './streetview.css';
import './welcome.css';
import './investigation.css';
import { App } from './App';

createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>);
