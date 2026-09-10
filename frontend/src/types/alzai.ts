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

export interface ResearchBriefSummary {
  brief_id: string;
  topic: string;
  user_premise_verdict: 'supported' | 'qualified' | 'unsupported' | 'contested';
  user_premise_explanation: string;
  findings_count: number;
  safe_claims: string[];
  qualified_claims: QualifiedClaimSummary[];
  unsupported_claims: string[];
  key_mechanisms: string[];
  retained_insights_count: number;
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
  progress_steps: ProgressStep[];
  bundle?: ContentBundle;
  brief_summary?: ResearchBriefSummary;
  error_message?: string;
  created_at: string;
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
