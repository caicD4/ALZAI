import React, { useState } from 'react';
import { 
  Sparkles, 
  Plus, 
  History, 
  Layers, 
  Settings, 
  ChevronLeft, 
  ChevronRight,
  FileText,
  Clock
} from 'lucide-react';

interface SidebarProps {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onNewContent: () => void;
  recentTopics: string[];
  onSelectRecent?: (topic: string) => void;
  onSelectRecentTopic?: (topic: string) => void;
  activeView?: 'create' | 'history';
  onSelectView?: (view: 'create' | 'history') => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  collapsed: externalCollapsed,
  onToggleCollapse: externalOnToggle,
  onNewContent,
  recentTopics = [],
  onSelectRecent,
  onSelectRecentTopic,
  activeView = 'create',
  onSelectView,
}) => {
  const [internalCollapsed, setInternalCollapsed] = useState(false);

  const collapsed = externalCollapsed !== undefined ? externalCollapsed : internalCollapsed;

  const handleToggle = () => {
    if (externalOnToggle) {
      externalOnToggle();
    } else {
      setInternalCollapsed((prev) => !prev);
    }
  };

  const handleSelectTopic = (topic: string) => {
    if (onSelectRecent) onSelectRecent(topic);
    if (onSelectRecentTopic) onSelectRecentTopic(topic);
  };

  return (
    <aside
      className={`relative h-screen bg-[#0C0C0E] border-r border-[#1E1E24] z-30 transition-all duration-300 flex flex-col shrink-0 ${
        collapsed ? 'w-16' : 'w-64'
      }`}
    >
      {/* Brand Header */}
      <div className="h-16 px-4 flex items-center justify-between border-b border-[#1E1E24]">
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="w-8 h-8 rounded-lg bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center shrink-0">
            <Sparkles className="w-4 h-4 text-indigo-400" />
          </div>
          {!collapsed && (
            <div className="flex flex-col">
              <span className="font-semibold tracking-wide text-zinc-100 text-sm">ALZAI</span>
              <span className="text-[10px] text-zinc-500 font-mono tracking-tight font-semibold">RESEARCH ENGINE</span>
            </div>
          )}
        </div>
        <button
          onClick={handleToggle}
          className="p-1.5 rounded-md text-zinc-400 hover:text-zinc-200 hover:bg-[#18181C] transition-colors"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* New Content Action */}
      <div className="p-3">
        <button
          onClick={onNewContent}
          className={`w-full flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs transition-colors shadow-lg shadow-indigo-600/10 ${
            collapsed ? 'px-0' : ''
          }`}
          title="New Content"
        >
          <Plus className="w-4 h-4" />
          {!collapsed && <span>New Content</span>}
        </button>
      </div>

      {/* Main Nav Links */}
      <div className="px-3 py-2 space-y-1">
        <button
          onClick={() => onSelectView && onSelectView('create')}
          className={`w-full flex items-center gap-3 px-3 py-2 rounded-md text-xs font-medium transition-colors ${
            activeView === 'create'
              ? 'bg-[#18181C] text-indigo-400 border border-[#27272E]'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-[#141418]'
          }`}
          title="Create"
        >
          <Layers className="w-4 h-4 shrink-0" />
          {!collapsed && <span>Create</span>}
        </button>

        <button
          onClick={() => onSelectView && onSelectView('history')}
          className={`w-full flex items-center gap-3 px-3 py-2 rounded-md text-xs font-medium transition-colors ${
            activeView === 'history'
              ? 'bg-[#18181C] text-indigo-400 border border-[#27272E]'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-[#141418]'
          }`}
          title="History"
        >
          <History className="w-4 h-4 shrink-0" />
          {!collapsed && <span>History</span>}
        </button>
      </div>

      {/* Recent Generations Section */}
      {!collapsed && (
        <div className="flex-1 overflow-y-auto px-3 py-4 border-t border-[#1E1E24]/60">
          <div className="flex items-center gap-1.5 px-3 mb-2 text-[11px] font-medium text-zinc-500 uppercase tracking-wider">
            <Clock className="w-3 h-3" />
            <span>Recent</span>
          </div>
          {recentTopics.length === 0 ? (
            <div className="px-3 py-3 text-xs text-zinc-600 italic">No recent runs yet</div>
          ) : (
            <div className="space-y-0.5">
              {recentTopics.slice(0, 8).map((topic, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSelectTopic(topic)}
                  className="w-full text-left px-3 py-2 rounded-md text-xs text-zinc-400 hover:text-zinc-200 hover:bg-[#141418] transition-colors truncate flex items-center gap-2 group"
                  title={topic}
                >
                  <FileText className="w-3.5 h-3.5 text-zinc-600 group-hover:text-indigo-400 shrink-0" />
                  <span className="truncate">{topic}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Footer / Placeholder settings */}
      <div className="p-3 border-t border-[#1E1E24] mt-auto">
        <div className="flex items-center gap-3 px-3 py-2 text-xs text-zinc-500">
          <Settings className="w-4 h-4 shrink-0" />
          {!collapsed && <span>Settings (v1.0.0)</span>}
        </div>
      </div>
    </aside>
  );
};
