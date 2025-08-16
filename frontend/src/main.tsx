import React from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';
import { ProcessSteps } from './components/ProcessSteps';

function App() {
  // Simple state signals to compute current step
  const [hasFiles, setHasFiles] = React.useState(false);
  const [hasColumns, setHasColumns] = React.useState(false);

  const currentStep = !hasFiles ? 1 : !hasColumns ? 2 : 3;

  return (
    <div className="p-4">
      <div className="max-w-5xl mx-auto grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6">
        <div>
          <section id="choose-files" className="mb-8">
            <h2 className="text-lg font-semibold mb-3">Choose files</h2>
            <input type="file" multiple accept='.xlsx' onChange={e => setHasFiles((e.target.files?.length ?? 0) > 0)} />
          </section>
          <section id="set-columns" className="mb-8">
            <h2 className="text-lg font-semibold mb-3">Set columns</h2>
            <div className="flex gap-2">
              <input placeholder="Image column (e.g., A)" className="border rounded px-2 py-1" onChange={e => setHasColumns(!!e.target.value)} />
              <input placeholder="Name column (e.g., B)" className="border rounded px-2 py-1" onChange={e => setHasColumns(prev => prev || !!e.target.value)} />
            </div>
          </section>
          <section id="process" className="mb-8">
            <h2 className="text-lg font-semibold mb-3">Process</h2>
            <button className="px-4 py-2 rounded bg-blue-600 text-white">Process</button>
          </section>
        </div>
        <div className="lg:sticky lg:top-4">
          <ProcessSteps currentStep={currentStep} />
        </div>
      </div>
    </div>
  );
}

createRoot(document.getElementById('root')!).render(<App />);


