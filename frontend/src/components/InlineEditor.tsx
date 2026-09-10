import React, { useState } from 'react';
import { Check, X } from 'lucide-react';

interface InlineEditorProps {
  initialText: string;
  onSave: (newText: string) => void;
  onCancel: () => void;
}

export const InlineEditor: React.FC<InlineEditorProps> = ({ initialText, onSave, onCancel }) => {
  const [text, setText] = useState<string>(initialText);

  return (
    <div className="w-full flex flex-col gap-3">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        className="w-full h-80 bg-[#0D0D0F] border border-indigo-500/50 rounded-xl p-4 text-zinc-100 text-sm font-sans leading-relaxed focus:outline-none focus:ring-1 focus:ring-indigo-500"
      />

      <div className="flex items-center justify-end gap-2">
        <button
          onClick={onCancel}
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-[#1A1A20] hover:bg-[#22222A] border border-[#272732] text-xs font-medium text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          <X className="w-3.5 h-3.5" />
          <span>Cancel</span>
        </button>

        <button
          onClick={() => onSave(text)}
          className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs font-medium text-white shadow-md shadow-indigo-600/20 transition-colors"
        >
          <Check className="w-3.5 h-3.5" />
          <span>Save Changes</span>
        </button>
      </div>
    </div>
  );
};
