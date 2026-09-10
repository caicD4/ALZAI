import { useState } from 'react';
import type { ContentPiece } from '../types/alzai';
import { InlineEditor } from './InlineEditor';
import { CopyButton } from './CopyButton';
import {
  Share2,
  BookOpen,
  Mail,
  Video,
  Film,
  FileText,
  Clock,
  CheckCircle2,
  ShieldAlert,
  RotateCw,
} from 'lucide-react';

interface ContentRendererProps {
  piece: ContentPiece;
  onSaveEdit?: (newBody: string) => void;
  onRegenerate?: () => void;
}

const FORMAT_ICONS: Record<string, any> = {
  linkedin: Share2,
  x_thread: Share2,
  article: BookOpen,
  newsletter: Mail,
  youtube_script: Video,
  short_video: Film,
  carousel: FileText,
};

export default function ContentRenderer({ piece, onSaveEdit, onRegenerate }: ContentRendererProps) {
  const [isEditing, setIsEditing] = useState(false);
  const Icon = FORMAT_ICONS[piece.format_id] || FileText;

  const qualityScore = piece.quality_report?.overall_score
    ? Math.round(piece.quality_report.overall_score * 100)
    : null;

  return (
    <div className="bg-[#14161E] border border-gray-800 rounded-xl overflow-hidden shadow-xl">
      {/* Format Output Header Bar */}
      <div className="bg-[#101117] border-b border-gray-800/80 px-6 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-purple-950/60 border border-purple-800/50 flex items-center justify-center">
            <Icon className="w-4 h-4 text-purple-400" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-200">{piece.platform} Output</h3>
            <div className="flex items-center gap-3 text-[11px] text-gray-400 mt-0.5">
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3 text-gray-500" />
                {piece.word_count} words
              </span>
              {piece.estimated_duration && (
                <span>Reading time: {piece.estimated_duration}</span>
              )}
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          {qualityScore !== null && (
            <div
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-semibold ${
                qualityScore >= 80
                  ? 'bg-emerald-950/50 border-emerald-800/60 text-emerald-300'
                  : 'bg-amber-950/50 border-amber-800/60 text-amber-300'
              }`}
              title="Content Quality Engine Audit Score"
            >
              {qualityScore >= 80 ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              ) : (
                <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
              )}
              <span>Quality: {qualityScore}%</span>
            </div>
          )}

          {!isEditing && (
            <button
              onClick={() => setIsEditing(true)}
              className="text-xs bg-gray-900 hover:bg-gray-800 text-gray-300 px-3 py-1.5 rounded-lg border border-gray-800 transition"
            >
              Edit Prose
            </button>
          )}

          {onRegenerate && (
            <button
              onClick={onRegenerate}
              className="text-xs bg-gray-900 hover:bg-gray-800 text-gray-300 px-2.5 py-1.5 rounded-lg border border-gray-800 transition flex items-center gap-1"
              title="Regenerate format"
            >
              <RotateCw className="w-3.5 h-3.5 text-gray-400" />
            </button>
          )}

          <CopyButton textToCopy={piece.body_text} label="Copy Output" />
        </div>
      </div>

      {/* Main Prose Content Container */}
      <div className="p-6">
        {piece.title && (
          <h2 className="text-lg font-bold text-gray-100 mb-4 pb-2 border-b border-gray-800/60">
            {piece.title}
          </h2>
        )}

        {isEditing ? (
          <InlineEditor
            initialText={piece.body_text}
            onSave={(newText: string) => {
              if (onSaveEdit) onSaveEdit(newText);
              setIsEditing(false);
            }}
            onCancel={() => setIsEditing(false)}
          />
        ) : (
          <div className="prose prose-invert max-w-none text-sm leading-relaxed text-gray-200 space-y-4 whitespace-pre-wrap font-sans">
            {piece.body_text}
          </div>
        )}
      </div>

      {/* Structured Sections (Thread / Slides / Script) if present */}
      {piece.sections && piece.sections.length > 1 && !isEditing && (
        <div className="bg-[#0E0F14] border-t border-gray-800/60 p-6 space-y-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-purple-400">
            Format Breakout ({piece.sections.length} Components)
          </h4>
          <div className="space-y-3">
            {piece.sections.map((section, idx) => (
              <div
                key={idx}
                className="bg-[#14161E] border border-gray-800/80 p-3.5 rounded-lg text-xs text-gray-300 relative"
              >
                <span className="absolute top-2 right-2 text-[10px] font-mono text-purple-400/80 bg-purple-950/40 px-2 py-0.5 rounded border border-purple-800/30">
                  #{idx + 1}
                </span>
                <div className="pr-8 whitespace-pre-wrap">{section}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
