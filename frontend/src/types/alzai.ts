export interface ContentFormatSpec {
  format_id: string;
  platform: string;
  format_name: string;
  target_length: string;
  structure: string[];
  hook_style: string;
  pacing: string;
  paragraph_style: string;
  formatting_rules: string[];
  audience_expectation: string;
  cta_style: string;
  minimum_length: number;
  maximum_length: number;
}

export interface ContentQualityIssue {
  issue_id: string;
  category: 'prose_quality' | 'research_fidelity' | 'voice_alignment' | 'platform_fit';
  severity: 'low' | 'medium' | 'high';
  description: string;
  suggested_fix?: string;
}

export interface ContentQualityReport {
  report_id: string;
  draft_id: string;
  overall_status: 'passed' | 'needs_revision' | 'failed';
  overall_score: number;
  research_fidelity_score: number;
  content_quality_score: number;
  voice_alignment_score: number;
  platform_fit_score: number;
  issues: ContentQualityIssue[];
  summary?: string;
}

export interface ContentPiece {
  content_id: string;
  format_id: string;
  platform: string;
  title?: string;
  body_text: string;
  sections?: string[];
  word_count: number;
  estimated_duration?: string;
  brief_id?: string;
  version: number;
  quality_report?: ContentQualityReport;
  generation_mode?: 'gemini' | 'fallback' | 'none';
  revision_count?: number;
}

export interface ContentBundle {
  bundle_id: string;
  brief_id: string;
  topic: string;
  source_strategy?: any;
  pieces: Record<string, ContentPiece>;
  created_at: string;
}

export interface QualifiedClaimSummary {
  claim: string;
  caveat?: string;
}

export interface ContentLandscapeSummary {
  topic: string;
  total_references?: number;
  dominant_angles?: string[];
  saturated_angles?: string[];
  repeated_arguments?: string[];
  common_hooks?: string[];
  common_framing?: string[];
  audience_questions?: string[];
  disagreements?: string[];
  underexplored_perspectives?: string[];
  content_gaps?: string[];
  possible_original_angles?: string[];
  recommended_differentiation?: string;
}

export interface AngleSummary {
  title: string;
  thesis: string;
  selected?: boolean;
  distinctive_angle?: string;
}

export interface RequestIntentSummary {
  subject: string;
  intent_type?: string;
  stance?: string;
  desired_content_type?: string;
  proposition?: string;
  research_goal?: string;
}

export interface ResearchBriefSummary {
  brief_id: string;
  topic: string;
  findings_count: number;
  safe_claims: string[];
  qualified_claims: QualifiedClaimSummary[];
  unsupported_claims: string[];
  content_gaps: string[];
  key_mechanisms: string[];
  retained_insights_count: number;
  intent?: RequestIntentSummary;
  content_landscape?: ContentLandscapeSummary;
  angles?: AngleSummary[];
  selected_angle?: AngleSummary;
}

export interface ProgressStep {
  step_id: string;
  label: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  details?: string;
}

export interface GenerationJob {
  job_id: string;
  prompt: string;
  format_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  generation_mode?: 'gemini' | 'fallback' | 'none';
  progress_steps: ProgressStep[];
  bundle?: ContentBundle;
  brief_summary?: ResearchBriefSummary;
  error_message?: string;
  include_trace?: boolean;
  trace_snapshot?: any;
  created_at: string;
  updated_at?: string;
}

export interface HistoryEntry {
  job_id: string;
  prompt: string;
  format_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  generation_mode?: string;
  error_message?: string;
  created_at: string;
  updated_at?: string;
  has_result: boolean;
}

export interface GenerationProgressEvent {
  job_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  current_step?: string;
  step_status?: string;
  details?: string;
  steps: ProgressStep[];
  error_message?: string;
}
