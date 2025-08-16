import React from 'react';

export function ProcessSteps({ currentStep }: { currentStep: 1 | 2 | 3 }) {
  const steps = [
    { id: 1, label: 'Choose files', href: '#choose-files' },
    { id: 2, label: 'Set columns', href: '#set-columns' },
    { id: 3, label: 'Process', href: '#process' },
  ];

  return (
    <nav aria-label="Progress" className="">
      {/* Mobile: horizontal */}
      <ol className="flex lg:hidden items-center justify-between gap-3 rounded-xl border p-3 bg-white">
        {steps.map((s) => (
          <li key={s.id} className="flex-1">
            <a href={s.href} className="group flex items-center gap-2 justify-center">
              <span
                className={[
                  'inline-flex h-8 w-8 items-center justify-center rounded-full border text-sm font-semibold',
                  currentStep === s.id ? 'bg-blue-600 text-white border-blue-600' : 'bg-gray-50 text-gray-700 border-gray-300',
                ].join(' ')}
              >
                {s.id}
              </span>
              <span className={currentStep === s.id ? 'font-semibold text-gray-900' : 'text-gray-600'}>{s.label}</span>
            </a>
          </li>
        ))}
      </ol>

      {/* Desktop: vertical sticky */}
      <ol className="hidden lg:block space-y-3 rounded-xl border p-4 bg-white">
        {steps.map((s) => (
          <li key={s.id}>
            <a href={s.href} className="group flex items-start gap-3">
              <span
                className={[
                  'inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-sm font-semibold mt-0.5',
                  currentStep === s.id ? 'bg-blue-600 text-white border-blue-600' : 'bg-gray-50 text-gray-700 border-gray-300',
                ].join(' ')}
              >
                {s.id}
              </span>
              <span className={currentStep === s.id ? 'font-semibold text-gray-900' : 'text-gray-600'}>{s.label}</span>
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}


