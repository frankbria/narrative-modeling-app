'use client';

import React from 'react';
import { Zap, Target, Sparkles } from 'lucide-react';
import type { TrainingMode } from '@/lib/services/model';

interface ModeOption {
  mode: TrainingMode;
  title: string;
  icon: React.ReactNode;
  blurb: string;
  algorithms: string;
  time: string;
  tuning: string;
  bestFor: string;
}

// Trade-off copy mirrors the backend presets in
// app/services/model_training/training_mode.py (issue #101).
const MODE_OPTIONS: ModeOption[] = [
  {
    mode: 'quick',
    title: 'Quick',
    icon: <Zap className="w-5 h-5 text-amber-500" />,
    blurb: 'Fast results from a few strong algorithms with default settings.',
    algorithms: '~3 algorithms',
    time: '~5 min cap',
    tuning: 'Default hyperparameters',
    bestFor: 'Rapid prototyping & first look',
  },
  {
    mode: 'comprehensive',
    title: 'Comprehensive',
    icon: <Target className="w-5 h-5 text-indigo-500" />,
    blurb: 'Thorough search across 10+ algorithms with full hyperparameter tuning.',
    algorithms: '10+ algorithms',
    time: 'Up to 30 min',
    tuning: 'Full tuning',
    bestFor: 'Best accuracy & production models',
  },
];

interface TrainingModeSelectorProps {
  value: TrainingMode;
  onChange: (mode: TrainingMode) => void;
  recommendedMode?: TrainingMode;
  reason?: string;
  disabled?: boolean;
}

/**
 * Quick vs Comprehensive training mode selector (issue #101).
 *
 * Two cards with trade-off explanations and an optional dataset-based
 * recommendation banner. Stateless: the parent owns the selected mode.
 */
export function TrainingModeSelector({
  value,
  onChange,
  recommendedMode,
  reason,
  disabled = false,
}: TrainingModeSelectorProps) {
  return (
    <div className="space-y-3" data-testid="training-mode-selector">
      <label className="block text-sm font-medium">Training Mode</label>

      {recommendedMode && reason && (
        <div
          className="p-3 bg-emerald-50 rounded-lg border border-emerald-200 flex items-start gap-2"
          data-testid="mode-recommendation"
        >
          <Sparkles className="w-5 h-5 text-emerald-600 mt-0.5" />
          <div className="text-sm text-emerald-900">
            <p className="font-semibold">
              Recommended: {recommendedMode === 'quick' ? 'Quick' : 'Comprehensive'}
            </p>
            <p className="mt-0.5 text-emerald-800">{reason}</p>
          </div>
        </div>
      )}

      <div
        role="radiogroup"
        aria-label="Training Mode"
        className="grid grid-cols-1 sm:grid-cols-2 gap-3"
      >
        {MODE_OPTIONS.map((option) => {
          const selected = value === option.mode;
          return (
            <button
              key={option.mode}
              type="button"
              role="radio"
              aria-checked={selected}
              disabled={disabled}
              onClick={() => onChange(option.mode)}
              data-testid={`mode-option-${option.mode}`}
              className={`text-left p-4 rounded-lg border transition-all ${
                selected
                  ? 'border-blue-500 ring-2 ring-blue-200 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300'
              } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <div className="flex items-center gap-2 font-semibold">
                {option.icon}
                {option.title}
                {recommendedMode === option.mode && (
                  <span className="ml-auto text-xs font-medium text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full">
                    Recommended
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-600 mt-1">{option.blurb}</p>
              <dl className="mt-2 text-xs text-gray-500 space-y-0.5">
                <div className="flex justify-between">
                  <dt>Algorithms</dt>
                  <dd className="font-medium text-gray-700">{option.algorithms}</dd>
                </div>
                <div className="flex justify-between">
                  <dt>Time</dt>
                  <dd className="font-medium text-gray-700">{option.time}</dd>
                </div>
                <div className="flex justify-between">
                  <dt>Tuning</dt>
                  <dd className="font-medium text-gray-700">{option.tuning}</dd>
                </div>
                <div className="flex justify-between">
                  <dt>Best for</dt>
                  <dd className="font-medium text-gray-700">{option.bestFor}</dd>
                </div>
              </dl>
            </button>
          );
        })}
      </div>
    </div>
  );
}
