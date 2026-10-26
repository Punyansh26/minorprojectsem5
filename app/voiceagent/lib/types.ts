export type ProviderType = "ollama" | "groq";
export type VoiceType = "Female" | "Male";
export type InputLanguageType =
  | "Hindi"
  | "English"
  | "Hinglish"
  | "Chhattisgarhi (experimental)";
export type AdmissionCategoryType = "general" | "CG";

export interface StudentProfile {
  student_id: string;
  student_email: string;
  student_category: AdmissionCategoryType;
}

export interface SessionConfig {
  provider: ProviderType;
  language: InputLanguageType;
  voice: VoiceType;
  speed: number;
  spoken: boolean;
  online: boolean;
  autoplay: boolean;
  profile: StudentProfile;
}

export interface TurnSource {
  source_file: string;
  source_name: string;
  page_number?: number | string;
  source_url?: string;
  period?: string;
  audience?: string;
  conflict_note?: string;
  scope_note?: string;
  quote?: string;
}

export interface TurnAudio {
  available: boolean;
  mime: string;
  extension: string;
  spoken_text: string;
  provider: string;
  size_bytes: number;
  url: string;
}

export interface RagMetrics {
  provider?: string;
  model?: string;
  model_calls?: number;
  retrieval_cache?: string;
  draft_cache?: string;
  history_pairs?: number;
  router_path?: string;
  router_fallback?: string;
}

export interface TurnTimings {
  queue_seconds?: number;
  stt_seconds?: number;
  reviewed_text_seconds?: number;
  audio_ready_seconds?: number;
  stage_ms?: Record<string, number>;
}

export interface TurnSnapshot {
  id: string;
  question: string;
  stage: string;
  stage_label: string;
  is_terminal: boolean;
  answer_text?: string;
  response_status?: string;
  language?: string;
  sources?: TurnSource[];
  ticket_id?: number | string | null;
  reminder_id?: number | string | null;
  llm_provider?: string;
  llm_error?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  audio?: TurnAudio | null;
  audio_error?: string | null;
  agent_seconds?: number;
  speech_seconds?: number;
  timings?: TurnTimings;
  rag_metrics?: RagMetrics;
  provider_attempts?: string[];
  can_retry_transcription?: boolean;
  can_retry_question?: boolean;
}

export interface StaffTicket {
  id: number;
  timestamp: string;
  student_id: string;
  student_category: string;
  detected_category: string;
  question: string;
  recipient_email: string;
  email_subject: string;
  email_body: string;
  status: string;
  turn_id: string;
}

export interface RuntimeHealth {
  provider: string;
  model: string;
  jev_mode: string;
  jev_artifact: string;
  jev_activation: string;
  jev_backend?: string;
  release: string | null;
  release_ok: boolean;
  engine?: string;
  release_integrity?: string;
  chunks?: number;
  cutoff_records?: number;
  evidence_blocks?: number;
  structured_records?: number;
  parents_by_status?: Record<string, number>;
  pending_critical_reviews?: number;
  sources_unassigned?: number;
  sources_review_overdue?: number;
  voices: Record<string, boolean>;
  environment: {
    python_version: string;
    platform: string;
    torch_version: string;
    ollama_model: string;
    ollama_url: string;
    stt_device: string;
    tts_device: string;
    speech_threads: number;
    whisper_model: string;
    data_root: string;
  };
  dependencies: Record<string, string>;
  job_stats: Record<string, number>;
  queue: {
    active_jobs: number;
    queued_jobs: number;
    capacity: number;
    max_concurrent_reasoning: number;
    total_tracked_jobs: number;
    queue_timeout_seconds: number;
    turn_timeout_seconds: number;
    retention_hours: number;
  };
  storage: Record<
    string,
    {
      bytes?: number;
      integrity?: string;
      rows?: Record<string, number>;
      error?: string;
    }
  >;
  cache_telemetry?: {
    hit: number;
    miss: number;
    bypass: number;
    put: number;
    evict: number;
    error: number;
    hit_rate: number;
  } | null;
  config?: {
    input_languages: string[];
    voices: string[];
    max_audio_seconds: number;
    min_audio_seconds: number;
    max_audio_bytes: number;
    max_text_chars: number;
    max_history_turns: number;
    verbalization_version: string;
  };
}

export interface CutoffRecord {
  id: string;
  year: number;
  authority: string;
  round: string;
  programme: string;
  quota: string;
  seat_category: string;
  gender_pool: string;
  rank_basis: string;
  opening_rank: string;
  closing_rank: string;
  source_file?: string;
  page_number?: number;
  quote?: string;
}

export interface CutoffsResponse {
  total: number;
  facets: {
    year: number[];
    authority: string[];
    programme: string[];
    quota: string[];
    seat_category: string[];
    gender_pool: string[];
    round: string[];
  };
  records: CutoffRecord[];
}

export interface StructuredRecordItem {
  id: string;
  kind: string;
  label: string;
  evidence_block_id: string;
  review_status: string;
  payload: Record<string, unknown>;
}

export interface KbOverviewResponse {
  release: string;
  created_at: string;
  engine: string;
  pipeline_version: string;
  embedding_model: string;
  chunks: number;
  documents: number;
  evidence_blocks: number;
  structured_records: number;
  cutoff_records: number;
  records_by_status: Record<string, Record<string, number>>;
  parents_by_status: Record<string, number>;
  validation: {
    by_topic?: Record<string, { passed: number; total: number }>;
    pass_rate?: number;
    passed?: number;
    scored?: number;
    review_cases?: number;
  };
  sources: Array<{
    id: string;
    title: string;
    source_file: string;
    source_owner: string;
    source_status: string;
    review_by: string;
    sha256: string;
  }>;
}
