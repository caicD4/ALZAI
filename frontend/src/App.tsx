import React, { useEffect, useRef, useState } from 'react';
import { Sidebar } from './components/Sidebar';
import Composer from './components/Composer';
import ProgressTracker from './components/ProgressTracker';
import FormatTabs from './components/FormatTabs';
import ContentRenderer from './components/ContentRenderer';
import ResearchTransparency from './components/ResearchTransparency';
import type { ContentFormatSpec, ContentPiece, GenerationJob, ProgressStep } from './types/alzai';
import { fetchFormats, fetchJobStatus, submitGenerateRequest, subscribeJobProgress } from './lib/api';
import { AlertCircle } from 'lucide-react';

export default function App() {
  const [formats, setFormats] = useState<ContentFormatSpec[]>([]);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [jobState, setJobState] = useState<GenerationJob | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeFormatKey, setActiveFormatKey] = useState<string>('linkedin');
  const [recentTopics, setRecentTopics] = useState<string[]>([]);
  const [editedPieces, setEditedPieces] = useState<Record<string, string>>({});

  // Use ref to track current active job ID in async callbacks
  const activeJobIdRef = useRef<string | null>(null);
  activeJobIdRef.current = activeJobId;

  useEffect(() => {
    fetchFormats()
      .then((data) => setFormats(data))
      .catch((err) => console.error('Failed to load format catalog:', err));
  }, []);

  const handleGenerate = async (prompt: string, format: string) => {
    // 1. Immediately clear old result & state
    setIsSubmitting(true);
    setError(null);
    setJobState(null);
    setActiveJobId(null);
    activeJobIdRef.current = null;
    setEditedPieces({});

    try {
      // 2. Submit new job request
      const jobId = await submitGenerateRequest(prompt, format);
      setActiveJobId(jobId);
      activeJobIdRef.current = jobId;
      setActiveFormatKey(format === 'all' ? 'linkedin' : format);

      if (!recentTopics.includes(prompt)) {
        setRecentTopics((prev) => [prompt, ...prev.slice(0, 9)]);
      }

      // Initial job status fetch
      const initialJob = await fetchJobStatus(jobId);
      if (initialJob.job_id === activeJobIdRef.current) {
        setJobState(initialJob);
      }

      // 3. Subscribe to real-time SSE progress events with strict job ID matching
      subscribeJobProgress(
        jobId,
        (evt) => {
          // Stale job response protection
          if (evt.job_id && evt.job_id !== activeJobIdRef.current) {
            return;
          }

          setJobState((prev) => {
            if (prev && prev.job_id !== evt.job_id) return prev;
            const updatedSteps: ProgressStep[] = evt.steps || prev?.progress_steps || [];
            return {
              job_id: evt.job_id,
              prompt: prev?.prompt || prompt,
              format_id: prev?.format_id || format,
              status: evt.status,
              progress_steps: updatedSteps,
              bundle: prev?.bundle,
              brief_summary: prev?.brief_summary,
              error_message: evt.error_message || prev?.error_message,
              created_at: prev?.created_at || new Date().toISOString(),
            };
          });

          if (evt.status === 'completed' || evt.status === 'failed') {
            setIsSubmitting(false);
            fetchJobStatus(jobId).then((finalJob) => {
              // Confirm job ID matches active request before updating state
              if (finalJob.job_id === activeJobIdRef.current) {
                setJobState(finalJob);
              }
            });
          }
        },
        () => {
          if (jobId === activeJobIdRef.current) {
            setIsSubmitting(false);
          }
        }
      );
    } catch (err: any) {
      setError(err.message || 'Failed to submit generation request.');
      setIsSubmitting(false);
    }
  };

  const handleNewContent = () => {
    setActiveJobId(null);
    activeJobIdRef.current = null;
    setJobState(null);
    setError(null);
    setIsSubmitting(false);
  };

  const handleSelectRecent = (topic: string) => {
    handleGenerate(topic, 'linkedin');
  };

  const handleEditSave = (formatId: string, newBody: string) => {
    setEditedPieces((prev) => ({
      ...prev,
      [formatId]: newBody,
    }));
  };

  // Determine current piece to display with strict job identity verification
  const currentPiece: ContentPiece | null = React.useMemo(() => {
    if (!jobState || jobState.job_id !== activeJobId) return null;
    if (!jobState.bundle?.pieces) return null;

    const originalPiece = jobState.bundle.pieces[activeFormatKey] || Object.values(jobState.bundle.pieces)[0];
    if (!originalPiece) return null;

    if (editedPieces[activeFormatKey]) {
      return {
        ...originalPiece,
        body_text: editedPieces[activeFormatKey],
      };
    }
    return originalPiece;
  }, [jobState, activeJobId, activeFormatKey, editedPieces]);

  return (
    <div className="flex h-screen bg-[#0E0F12] text-gray-100 antialiased font-sans overflow-hidden">
      {/* Collapsible Left Sidebar */}
      <Sidebar
        recentTopics={recentTopics}
        onNewContent={handleNewContent}
        onSelectRecent={handleSelectRecent}
      />

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col h-full overflow-hidden relative">
        {/* Top Header Bar */}
        <header className="h-14 border-b border-gray-800/60 bg-[#121318]/70 backdrop-blur px-6 flex items-center justify-between z-10 shrink-0">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-purple-400 bg-purple-950/60 px-2.5 py-1 rounded-full border border-purple-800/40">
              ALZAI Engine 3.6
            </span>
            <span className="text-xs text-gray-400">
              {jobState?.status === 'processing'
                ? 'Synthesizing research & writing...'
                : jobState?.status === 'completed'
                ? 'Generation Complete'
                : 'Ready'}
            </span>
          </div>

          {jobState?.bundle && jobState.job_id === activeJobId && (
            <div className="text-xs text-gray-400 flex items-center gap-4">
              <span>
                Topic: <strong className="text-gray-200">{jobState.bundle.topic}</strong>
              </span>
              <span>
                Job ID: <strong className="text-purple-400 font-mono">{jobState.job_id.slice(0, 8)}</strong>
              </span>
            </div>
          )}
        </header>

        {/* Workspace Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Composer Input Area */}
          <Composer formats={formats} onSubmit={handleGenerate} isSubmitting={isSubmitting} />

          {/* Error Banner */}
          {error && (
            <div className="bg-red-950/40 border border-red-800/60 text-red-200 px-4 py-3 rounded-lg flex items-center gap-3 text-sm animate-fadeIn">
              <AlertCircle className="w-5 h-5 text-red-400 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Progress Tracker when running */}
          {jobState && jobState.job_id === activeJobId && (jobState.status === 'processing' || jobState.status === 'queued') && (
            <ProgressTracker steps={jobState.progress_steps} />
          )}

          {/* Failed State display */}
          {jobState && jobState.job_id === activeJobId && jobState.status === 'failed' && (
            <div className="bg-red-950/30 border border-red-900/60 p-6 rounded-xl text-center space-y-2">
              <AlertCircle className="w-8 h-8 text-red-400 mx-auto" />
              <h3 className="text-base font-semibold text-red-200">Generation Failed</h3>
              <p className="text-xs text-red-300">{jobState.error_message || 'An unexpected error occurred during execution.'}</p>
            </div>
          )}

          {/* Completed Content Results Area */}
          {jobState && jobState.job_id === activeJobId && jobState.status === 'completed' && jobState.bundle && (
            <div className="space-y-6 animate-fadeIn">
              {/* Multi-Format Selector Tabs */}
              <FormatTabs
                pieces={jobState.bundle.pieces}
                activeFormatKey={activeFormatKey}
                onSelectFormat={setActiveFormatKey}
              />

              {/* Active Format Content Card */}
              {currentPiece ? (
                <ContentRenderer
                  piece={currentPiece}
                  onSaveEdit={(newBody) => handleEditSave(activeFormatKey, newBody)}
                  onRegenerate={() => handleGenerate(jobState.prompt, activeFormatKey)}
                />
              ) : (
                <div className="p-8 text-center text-gray-400">No content piece available for this format.</div>
              )}

              {/* Expandable Research & Quality Audit Transparency */}
              <ResearchTransparency
                strategy={jobState.bundle.source_strategy}
                briefSummary={jobState.brief_summary}
                qualityReport={currentPiece?.quality_report}
              />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
