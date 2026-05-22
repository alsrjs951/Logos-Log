import React from 'react';
import ChatWindow from './components/ChatWindow';
import { BrainCircuit } from 'lucide-react';
import './App.css';

function App() {
  return (
    <div className="app-container glass-panel">
      <header className="app-header">
        <div className="logo-icon">
          <BrainCircuit size={24} />
        </div>
        <div className="header-titles">
          <h1>Logos-Log AI</h1>
          <p>Your psychological & logotherapy assistant</p>
        </div>
      </header>
      
      <ChatWindow />
    </div>
  );
}

export default App;
