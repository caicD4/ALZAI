import { Share2, BookOpen, Mail, Video, Film, FileText, CheckCircle2 } from 'lucide-react';
import type { ContentPiece } from '../types/alzai';

interface FormatTabsProps {
  pieces: Record<string, ContentPiece>;
  activeFormatKey: string;
  onSelectFormat: (formatKey: string) => void;
}

const FORMAT_META: Record<string, { label: string; icon: any }> = {
  linkedin: { label: 'LinkedIn Post', icon: Share2 },
  x_thread: { label: 'X/Twitter Thread', icon: Share2 },
  article: { label: 'Article', icon: BookOpen },
  newsletter: { label: 'Newsletter', icon: Mail },
  youtube_script: { label: 'YouTube Script', icon: Video },
  short_video: { label: 'Shorts/TikTok', icon: Film },
  carousel: { label: 'Carousel Deck', icon: FileText },
};

export default function FormatTabs({
  pieces,
  activeFormatKey,
  onSelectFormat,
}: FormatTabsProps) {
  const formatKeys = Object.keys(pieces);

  return (
    <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none border-b border-gray-800/80">
      {formatKeys.map((key) => {
        const piece = pieces[key];
        const meta = FORMAT_META[key] || { label: key, icon: FileText };
        const Icon = meta.icon;
        const isActive = activeFormatKey === key;

        return (
          <button
            key={key}
            onClick={() => onSelectFormat(key)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-t-xl text-xs font-semibold border-t border-x transition shrink-0 ${
              isActive
                ? 'bg-[#14161E] border-gray-800 text-purple-300 border-b-transparent -mb-px'
                : 'bg-transparent border-transparent text-gray-400 hover:text-gray-200 hover:bg-gray-900/40'
            }`}
          >
            <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-purple-400' : 'text-gray-500'}`} />
            <span>{piece.platform || meta.label}</span>
            <CheckCircle2 className="w-3 h-3 text-emerald-500/80 ml-0.5" />
          </button>
        );
      })}
    </div>
  );
}
