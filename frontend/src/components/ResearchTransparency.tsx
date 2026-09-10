import { useState } from 'react';
import {
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertTriangle,
  Lightbulb,
  Target,
  Sparkles,
  ShieldCheck,
  Compass,
  Cpu,
  Activity,
} from 'lucide-react';
import type { ContentQualityReport, ResearchBriefSummary } from '../types/alzai';

interface ResearchTransparencyProps {
  strategy?: any;
  briefSummary?: ResearchBriefSummary;
  qualityReport?: ContentQualityReport;
  generationMode?: 'gemini' | 'fallback' | 'none';
  revisionCount?: number;
}

const MODE_META: Record<string, { label: string; cls: string }> = {
  gemini: { label: 'Gemini', cls: 'text-emerald-300 bg-emerald-950/40 border-emerald-800/50' },
  fallback: { label: 'Fallback engine', cls: 'text-amber-300 bg-amber-950/40 border-amber-800/50' },
  none: { label: 'No LLM', cls: 'text-gray-400 bg-gray-900/40 border-gray-700/50' },
};

export default function ResearchTransparency({
  strategy,
  briefSummary,
  qualityReport,
  generationMode,
  revisionCount,
}: ResearchTransparencyProps) {
  const [isOpen, setIsOpen] = useState(false);

  const claimMap = strategy?.claim_map;
  const contentGaps = claimMap?.content_gaps || briefSummary?.content_gaps;
  const landscape = briefSummary?.content_landscape;
  const angles = briefSummary?.angles || [];
  const intent = briefSummary?.intent;
  const modeMeta = generationMode ? MODE_META[generationMode] : undefined;

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
              Research Intelligence & Execution Transparency
            </h4>
            <p className="text-xs text-gray-400">
              Landscape, angles, grounded evidence, claim map, and 4D quality scores
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {modeMeta && (
            <span className={`text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border ${modeMeta.cls}`}>
              {modeMeta.label}
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
          {/* Intent / Creative Direction */}
          {intent && (
            <div className="bg-[#14161E] border border-gray-800 p-4 rounded-lg space-y-1.5">
              <div className="flex items-center gap-2 font-semibold text-gray-200 text-xs">
                <Cpu className="w-4 h-4 text-purple-400" />
                <span>Request Understanding</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-gray-300">
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-gray-500">Subject</p>
                  <p className="font-medium text-gray-200">{intent.subject}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-gray-500">Intent</p>
                  <p className="font-medium text-gray-200">{intent.intent_type || '—'}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-gray-500">Stance</p>
                  <p className="font-medium text-gray-200">{intent.stance || '—'}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-gray-500">Content Type</p>
                  <p className="font-medium text-gray-200">{intent.desired_content_type || '—'}</p>
                </div>
              </div>
              {intent.research_goal && (
                <p className="text-gray-400 leading-relaxed">
                  <span className="text-gray-500">Research goal:</span>{' '}
                  {intent.research_goal}
                </p>
              )}
            </div>
          )}

          {/* Content Landscape */}
          {landscape && (
            <div className="bg-[#14161E] border border-gray-800 p-4 rounded-lg space-y-3">
              <div className="flex items-center gap-2 font-semibold text-gray-200 text-xs">
                <Compass className="w-4 h-4 text-indigo-400" />
                <span>Content Landscape</span>
                {landscape.total_references ? (
                  <span className="ml-auto text-[10px] font-mono text-gray-500">
                    {landscape.total_references} existing references analyzed
                  </span>
                ) : null}
              </div>

              {landscape.dominant_angles && landscape.dominant_angles.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-gray-500">Dominant angles:</span>
                  {landscape.dominant_angles.map((a, i) => (
                    <span key={i} className="px-2 py-0.5 rounded bg-gray-900 border border-gray-800 text-gray-300">
                      {a}
                    </span>
                  ))}
                </div>
              )}

              {landscape.saturated_angles && landscape.saturated_angles.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-gray-500">Saturated (avoid repeating):</span>
                  {landscape.saturated_angles.map((a, i) => (
                    <span key={i} className="px-2 py-0.5 rounded bg-amber-950/20 border border-amber-800/40 text-amber-300">
                      {a}
                    </span>
                  ))}
                </div>
              )}

              {landscape.recommended_differentiation && (
                <p className="text-gray-300 leading-relaxed">
                  <strong className="text-gray-200">Differentiation:</strong>{' '}
                  {landscape.recommended_differentiation}
                </p>
              )}

              {(landscape.content_gaps || []).length > 0 && (
                <ul className="space-y-1.5 text-gray-300 list-disc list-inside leading-relaxed">
                  {landscape.content_gaps!.map((gap, idx) => (
                    <li key={idx}>{gap}</li>
                  ))}
                </ul>
              )}

              {(landscape.possible_original_angles || []).length > 0 && (
                <div className="space-y-1">
                  <p className="text-gray-500">Possible original angles:</p>
                  {landscape.possible_original_angles!.map((a, i) => (
                    <p key={i} className="text-gray-300">
                      · {a}
                    </p>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Content Gaps / Differentiation */}
          {contentGaps && contentGaps.length > 0 && (
            <div className="bg-[#14161E] border border-gray-800 p-4 rounded-lg space-y-1.5">
              <div className="flex items-center gap-2 font-semibold text-gray-200 text-xs">
                <Lightbulb className="w-4 h-4 text-purple-400" />
                <span>Research Content Gaps — Owned by This Draft</span>
              </div>
              <ul className="space-y-1.5 text-gray-300 list-disc list-inside leading-relaxed">
                {contentGaps.map((gap: string, idx: number) => (
                  <li key={idx}>{gap}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Discovered Angles */}
          {angles.length > 0 && (
            <div className="bg-[#14161E] border border-gray-800 p-4 rounded-lg space-y-2">
              <div className="flex items-center gap-2 font-semibold text-gray-200 text-xs">
                <Sparkles className="w-4 h-4 text-purple-400" />
                <span>Discovered Angles</span>
              </div>
              <div className="space-y-1.5">
                {angles.map((angle, idx) => (
                  <div
                    key={idx}
                    className={`p-2 rounded-md border ${
                      angle.selected
                        ? 'bg-purple-950/30 border-purple-700/50'
                        : 'bg-gray-900/40 border-gray-800'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-gray-200 font-medium">{angle.title}</span>
                      {angle.selected && (
                        <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-purple-800/50 text-purple-200 border border-purple-700/50">
                          Selected
                        </span>
                      )}
                    </div>
                    {angle.thesis && <p className="text-gray-400 mt-0.5">{angle.thesis}</p>}
                  </div>
                ))}
              </div>
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

          {/* Execution honesty */}
          {(generationMode || typeof revisionCount === 'number') && (
            <div className="bg-[#14161E] border border-gray-800 p-4 rounded-lg space-y-1.5">
              <div className="flex items-center gap-2 font-semibold text-gray-200 text-xs">
                <Activity className="w-4 h-4 text-emerald-400" />
                <span>Execution Honesty</span>
              </div>
              <div className="flex flex-wrap gap-4 text-gray-300">
                <span>
                  Generation mode:{' '}
                  <strong className={modeMeta ? modeMeta.cls.split(' ')[0] : 'text-gray-200'}>
                    {generationMode || '—'}
                  </strong>
                </span>
                <span>
                  Targeted revisions applied:{' '}
                  <strong className="text-gray-200">{typeof revisionCount === 'number' ? revisionCount : '—'}</strong>
                </span>
                <span className="text-gray-500">
                  Fallback engine output is reported honestly — never presented as LLM-generated.
                </span>
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
                      <li key={idx} className="truncate" title={`${c.claim_text || c} — ${c.required_attribution_or_caveat || ''}`}>
                        {c.claim_text || c}
                      </li>
                    ))}
                  </ul>
                  <p className="text-[10px] text-amber-300/80">
                    Must be stated with attribution — never as bare fact.
                  </p>
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