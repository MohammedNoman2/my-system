import React from 'react';
import { Check } from 'lucide-react';
import { cn } from '../../utils/cn';

interface Step {
  id: number;
  title: string;
  description: string;
}

interface StepperProps {
  steps: Step[];
  currentStep: number;
}

export function StepperForm({ steps, currentStep }: StepperProps) {
  return (
    <div className="w-full mb-8">
      <div className="flex items-center justify-between">
        {steps.map((step, idx) => {
          const isCompleted = currentStep > step.id;
          const isCurrent = currentStep === step.id;

          return (
            <React.Fragment key={step.id}>
              {/* Step indicator */}
              <div className="flex items-center gap-3">
                <div
                  className={cn(
                    'w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm transition-all duration-200 shrink-0',
                    isCompleted
                      ? 'bg-emerald-600 text-white shadow-sm'
                      : isCurrent
                      ? 'bg-[#1e3a8a] text-white ring-4 ring-blue-100 shadow-md'
                      : 'bg-slate-200 text-slate-500'
                  )}
                >
                  {isCompleted ? <Check className="w-5 h-5" /> : step.id}
                </div>
                <div className="hidden sm:block text-right">
                  <p
                    className={cn(
                      'text-sm font-bold',
                      isCurrent ? 'text-slate-900' : 'text-slate-500'
                    )}
                  >
                    {step.title}
                  </p>
                  <p className="text-xs text-slate-400">{step.description}</p>
                </div>
              </div>

              {/* Connecting line */}
              {idx < steps.length - 1 && (
                <div
                  className={cn(
                    'flex-1 h-0.5 mx-4 transition-all duration-200',
                    currentStep > step.id ? 'bg-emerald-600' : 'bg-slate-200'
                  )}
                />
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
