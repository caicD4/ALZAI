import { useState } from 'react';
import { ChevronDown, ChevronUp, ShieldCheck, CheckCircle2, AlertTriangle, Scale, Target, Sparkles } from 'lucide-react';
import type { ContentQualityReport, ResearchBriefSummary } from '../types/alzai';

interface ResearchTransparencyProps {
  strategy?: any;
  briefSummary?: ResearchBriefSummary;
  qualityReport?: ContentQualityReport;
}

export default function ResearchTransparency({
  strategy,
  briefSummary,
  qualityReport,
}: ResearchTransparencyProps) {
  const [isOpen, setIsOpen] = useState(false);

  const claimMap = strategy?.claim_map;
  const verdict = claimMap?.user_premise_verdict || briefSummary?.user_premise_verdict;
  const verdictReasoning = claimMap?.user_premise_explanation || briefSummary?.user_premise_explanation;

  return (
    <div className="bg-[#14161E] border border-gray-800 rounded-xl overflow-hidden shadow-lg transition">
      {/* Header Button Toggle */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full bg-[#101117] hover:bg-gray-900/60 px-6 py-4 flex items-center justify-between transition text-left"
      >
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-blue-950/60 border border-blue-800/40 flex items-center justify-center">
            <ShieldCheck className="w-4 h-4 text-blue-400" />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-gray-200">
              Research Synthesis & Quality Audit Transparency
            </h4>
            <p className="text-xs text-gray-400">
              Inspect grounded evidence, claim classifications, and 4D quality scores
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {verdict && (
            <span
              className={`text-xs px-2.5 py-1 rounded-full font-semibold border ${
                verdict === 'supported'
                  ? 'bg-emerald-950/60 border-emerald-800/60 text-emerald-300'
                  : verdict === 'qualified'
                  ? 'bg-amber-950/60 border-amber-800/60 text-amber-300'
                  : 'bg-red-950/60 border-red-800/60 text-red-300'
              }`}
            >
              Premise: {verdict.toUpperCase()}
            </span>
          )}
          {isOpen ? (
            <ChevronUp className="w-4 h-4 text-gray-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-gray-400" />
          )}
        </div>
      </button>

      {/* Expanded Details Body */}
      {isOpen && (
        <div className="p-6 space-y-6 border-t border-gray-800/80 bg-[#0E0F14] text-xs">
          {/* User Premise Verdict */}
          {verdict && (
            <div className="bg-[#14161E] border border-gray-800 p-4 rounded-lg space-y-1.5">
              <div className="flex items-center gap-2 font-semibold text-gray-200 text-xs">
                <Scale className="w-4 h-4 text-purple-400" />
                <span>Epistemic Premise Verdict</span>
              </div>
              <p className="text-gray-300 leading-relaxed">{verdictReasoning}</p>
            </div>
          )}

          {/* 4-Dimension Quality Scores */}
          {qualityReport && (
            <div className="space-y-3">
              <h5 className="font-semibold text-gray-300 flex items-center gap-1.5 uppercase text-[11px] tracking-wider text-purple-400">
                <Target className="w-3.5 h-3.5" /> Content Quality Engine 4D Evaluation
              </h5>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="bg-[#14161E] border border-gray-800 p-3 rounded-lg text-center space-y-1">
                  <p className="text-[10px] text-gray-400 uppercase font-medium">Research Fidelity</p>
                  <p className="text-base font-bold text-emerald-400">
                    {Math.round((qualityReport.research_fidelity_score || 0) * 100)}%
                  </p>
                </div>
                <div className="bg-[#14161E] border border-gray-800 p-3 rounded-lg text-center space-y-1">
                  <p className="text-[10px] text-gray-400 uppercase font-medium">Content Quality</p>
                  <p className="text-base font-bold text-purple-400">
                    {Math.round((qualityReport.content_quality_score || 0) * 100)}%
                  </p>
                </div>
                <div className="bg-[#14161E] border border-gray-800 p-3 rounded-lg text-center space-y-1">
                  <p className="text-[10px] text-gray-400 uppercase font-medium">Voice Alignment</p>
                  <p className="text-base font-bold text-indigo-400">
                    {Math.round((qualityReport.voice_alignment_score || 0) * 100)}%
                  </p>
                </div>
                <div className="bg-[#14161E] border border-gray-800 p-3 rounded-lg text-center space-y-1">
                  <p className="text-[10px] text-gray-400 uppercase font-medium">Platform Fit</p>
                  <p className="text-base font-bold text-blue-400">
                    {Math.round((qualityReport.platform_fit_score || 0) * 100)}%
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Claim Map Classifications */}
          {claimMap && (
            <div className="space-y-3">
              <h5 className="font-semibold text-gray-300 flex items-center gap-1.5 uppercase text-[11px] tracking-wider text-purple-400">
                <Sparkles className="w-3.5 h-3.5" /> Structured Claim Map
              </h5>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {/* Safe Claims */}
                <div className="bg-[#14161E] border border-emerald-900/30 p-3.5 rounded-lg space-y-2">
                  <span className="text-emerald-400 font-semibold flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Safe Claims ({claimMap.safe_claims?.length || 0})
                  </span>
                  <ul className="space-y-1 text-gray-300 list-disc list-inside">
                    {claimMap.safe_claims?.map((c: any, idx: number) => (
                      <li key={idx} className="truncate" title={c.claim_text || c}>
                        {c.claim_text || c}
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Qualified Claims */}
                <div className="bg-[#14161E] border border-amber-900/30 p-3.5 rounded-lg space-y-2">
                  <span className="text-amber-400 font-semibold flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5" /> Qualified Claims ({claimMap.qualified_claims?.length || 0})
                  </span>
                  <ul className="space-y-1 text-gray-300 list-disc list-inside">
                    {claimMap.qualified_claims?.map((c: any, idx: number) => (
                      <li key={idx} className="truncate" title={c.claim_text || c}>
                        {c.claim_text || c}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* Strategy Outline / Key Points */}
          {strategy && (
            <div className="space-y-2 pt-2 border-t border-gray-800/60">
              <h5 className="font-semibold text-gray-300 text-[11px] uppercase tracking-wider text-purple-400">
                Content Strategy Hook & Thesis
              </h5>
              <p className="text-gray-300">
                <strong className="text-gray-200">Thesis:</strong> {strategy.thesis}
              </p>
              {strategy.hook_direction && (
                <p className="text-gray-300">
                  <strong className="text-gray-200">Hook Concept:</strong> {strategy.hook_direction}
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
