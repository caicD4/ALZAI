import React, { useState } from 'react';
import type { KeyboardEvent } from 'react';
import {
  Sparkles,
  Layers,
  FileText,
  Video,
  Mail,
  Film,
  BookOpen,
  Send,
  HelpCircle,
  Share2,
} from 'lucide-react';
import type { ContentFormatSpec } from '../types/alzai';

interface ComposerProps {
  formats: ContentFormatSpec[];
  onSubmit: (prompt: string, format: string, includeTrace?: boolean) => void;
  isSubmitting: boolean;
}

const FORMAT_OPTIONS = [
  { id: 'all', label: 'All 7 Formats', icon: Layers, desc: 'Generate complete multi-format bundle' },
  { id: 'linkedin', label: 'LinkedIn Post', icon: Share2, desc: 'Professional, punchy hook & insights' },
  { id: 'x_thread', label: 'X/Twitter Thread', icon: Share2, desc: 'Numbered posts with strong pacing' },
  { id: 'article', label: 'Long-Form Article', icon: BookOpen, desc: 'Deep-dive structured article' },
  { id: 'newsletter', label: 'Newsletter', icon: Mail, desc: 'Personal conversational tone' },
  { id: 'youtube_script', label: 'YouTube Script', icon: Video, desc: 'Visual cues & spoken dialogue' },
  { id: 'short_video', label: 'Shorts/TikTok', icon: Film, desc: 'Fast-hook vertical script' },
  { id: 'carousel', label: 'Carousel Deck', icon: FileText, desc: 'Slide-by-slide visual layout' },
];

const PRESETS = [
  'How adult IQ can be increased through neuroplasticity, RFT, and adaptive cognitive training',
  'Why modern AI agent architectures are shifting from single prompts to multi-agent orchestration',
  'The impact of remote-first engineering culture on software developer velocity and mental health',
];

export default function Composer({ onSubmit, isSubmitting }: ComposerProps) {
  const [prompt, setPrompt] = useState('');
  const [selectedFormat, setSelectedFormat] = useState('linkedin');
  const [includeTrace, setIncludeTrace] = useState(false);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!prompt.trim() || isSubmitting) return;
    onSubmit(prompt.trim(), selectedFormat, includeTrace);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="bg-[#14161E] border border-gray-800/80 rounded-xl p-5 shadow-2xl space-y-4">
      {/* Top Header & Presets */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-purple-600/20 border border-purple-500/40 flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-purple-400" />
          </div>
          <h2 className="text-sm font-semibold text-gray-200">What would you like to create?</h2>
        </div>

        <span className="text-[11px] text-gray-500 flex items-center gap-1">
          <HelpCircle className="w-3.5 h-3.5" /> Press <kbd className="bg-gray-800 px-1 py-0.5 rounded text-gray-300 font-mono">Ctrl + Enter</kbd> to submit
        </span>
      </div>

      {/* Main Prompt Textarea */}
      <div className="relative">
        <textarea
          rows={3}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Enter a topic, core premise, or research request (e.g. 'Write me a post on how IQ can actually be increased through neuroplasticity...')"
          className="w-full bg-[#0E0F14] border border-gray-800 rounded-lg p-3.5 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-purple-500/80 focus:ring-1 focus:ring-purple-500/50 resize-none transition"
        />
      </div>

      {/* Preset Suggestions */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
        <span className="text-xs text-gray-500 shrink-0 font-medium">Ideas:</span>
        {PRESETS.map((preset, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => setPrompt(preset)}
            className="text-xs bg-gray-900/80 hover:bg-gray-800 text-gray-300 px-2.5 py-1 rounded-md border border-gray-800/80 truncate max-w-[280px] shrink-0 transition"
          >
            {preset}
          </button>
        ))}
      </div>

      {/* Format Selector Grid & Action Button */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pt-2 border-t border-gray-800/60">
        {/* Format Selector Pills */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {FORMAT_OPTIONS.map((fmt) => {
            const Icon = fmt.icon;
            const isSelected = selectedFormat === fmt.id;
            return (
              <button
                key={fmt.id}
                type="button"
                onClick={() => setSelectedFormat(fmt.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition ${
                  isSelected
                    ? 'bg-purple-950/70 border-purple-600/80 text-purple-200 shadow-sm shadow-purple-900/30'
                    : 'bg-gray-900/50 border-gray-800 text-gray-400 hover:text-gray-200 hover:bg-gray-800/60'
                }`}
                title={fmt.desc}
              >
                <Icon className={`w-3.5 h-3.5 ${isSelected ? 'text-purple-400' : 'text-gray-400'}`} />
                <span>{fmt.label}</span>
              </button>
            );
          })}
        </div>

        {/* Generate Submit Button */}
        <button
          type="button"
          onClick={() => handleSubmit()}
          disabled={!prompt.trim() || isSubmitting}
          className="w-full sm:w-auto px-5 py-2 rounded-lg bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-medium text-xs flex items-center justify-center gap-2 shadow-lg shadow-purple-950/40 disabled:opacity-50 disabled:cursor-not-allowed transition shrink-0"
        >
          {isSubmitting ? (
            <>
              <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>Synthesizing...</span>
            </>
          ) : (
            <>
              <Send className="w-3.5 h-3.5" />
              <span>Generate Content</span>
            </>
          )}
        </button>
      </div>

      {/* Advanced options row */}
      <div className="flex items-center justify-between pt-1 -mt-1">
        <label className="flex items-center gap-2 cursor-pointer select-none group">
          <button
            type="button"
            role="switch"
            aria-checked={includeTrace}
            onClick={() => setIncludeTrace(!includeTrace)}
            className={`w-7 h-4 rounded-full transition relative ${
              includeTrace ? 'bg-purple-600/70' : 'bg-gray-800'
            }`}
          >
            <span
              className={`absolute top-0.5 w-3 h-3 rounded-full transition-all ${
                includeTrace ? 'left-3.5 bg-purple-200' : 'left-0.5 bg-gray-400'
              }`}
            />
          </button>
          <span className="text-[11px] text-gray-500 group-hover:text-gray-300 transition">
            Capture detailed LLM execution trace (for debugging)
          </span>
        </label>
      </div>
    </div>
  );
}
