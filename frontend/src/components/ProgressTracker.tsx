import { CheckCircle2, Loader2, Clock, AlertCircle } from 'lucide-react';
import type { ProgressStep } from '../types/alzai';

interface ProgressTrackerProps {
  steps: ProgressStep[];
}

export default function ProgressTracker({ steps }: ProgressTrackerProps) {
  const completedCount = steps.filter((s) => s.status === 'completed').length;
  const progressPercent = Math.round((completedCount / steps.length) * 100);

  return (
    <div className="bg-[#14161E] border border-purple-900/40 rounded-xl p-5 shadow-2xl space-y-4 animate-fadeIn">
      {/* Header & Progress Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-purple-500 animate-pulse" />
          <h3 className="text-sm font-semibold text-gray-200">ALZAI Execution Pipeline</h3>
        </div>
        <span className="text-xs font-mono text-purple-400 font-medium">
          {progressPercent}% Complete ({completedCount}/{steps.length} Steps)
        </span>
      </div>

      {/* Progress Track */}
      <div className="w-full bg-gray-900 rounded-full h-1.5 overflow-hidden">
        <div
          className="bg-gradient-to-r from-purple-600 to-indigo-500 h-full transition-all duration-500 ease-out"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      {/* Steps List */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-2">
        {steps.map((step, idx) => {
          const isDone = step.status === 'completed';
          const isRunning = step.status === 'running';
          const isFailed = step.status === 'failed';

          return (
            <div
              key={step.step_id || idx}
              className={`flex items-start gap-2.5 p-2.5 rounded-lg border text-xs transition ${
                isDone
                  ? 'bg-emerald-950/20 border-emerald-900/40 text-emerald-200'
                  : isRunning
                  ? 'bg-purple-950/40 border-purple-800/60 text-purple-200 ring-1 ring-purple-500/40'
                  : isFailed
                  ? 'bg-red-950/30 border-red-900/40 text-red-200'
                  : 'bg-gray-900/40 border-gray-800/60 text-gray-400'
              }`}
            >
              <div className="mt-0.5 shrink-0">
                {isDone ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                ) : isRunning ? (
                  <Loader2 className="w-4 h-4 text-purple-400 animate-spin" />
                ) : isFailed ? (
                  <AlertCircle className="w-4 h-4 text-red-400" />
                ) : (
                  <Clock className="w-4 h-4 text-gray-600" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium leading-snug">{step.label}</p>
                {step.details && (
                  <p className="text-[11px] text-gray-400 truncate mt-0.5">{step.details}</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
