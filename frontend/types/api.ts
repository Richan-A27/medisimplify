// Mirrors backend/app/schemas. Keep in sync when the API changes.

export interface ApiErrorBody {
  code: string;
  message: string;
}

export interface LLMStatus {
  provider: "gemini";
  model: string;
  api_key_configured: boolean;
}

export interface HealthResponse {
  status: "ok";
  service: string;
  version: string;
  environment: string;
  llm: LLMStatus;
  limits: {
    max_upload_mb: number;
    max_pdf_pages: number;
  };
  knowledge_base: KnowledgeBaseStatus;
}

export type FlagMeaning = "high" | "low" | "critical" | "abnormal";
export type RangeComparison = "above_range" | "below_range" | "within_range" | "not_compared";
export type SourceStatus = "complete" | "incomplete" | "ambiguous";
export type MeasurementIssue =
  | "missing_unit"
  | "missing_reference_range"
  | "value_is_bound"
  | "multiple_ranges_found"
  | "flag_conflicts_with_range"
  | "duplicate_test_conflicting_values"
  | "unrecognized_text"
  | "stratified_reference_range";

export interface Measurement {
  test_name: string;
  value: string;
  value_numeric: number | null;
  unit: string | null;
  reference_range: string | null;
  reported_flag: string | null;
  flag_meaning: FlagMeaning | null;
  range_comparison: RangeComparison;
  source_status: SourceStatus;
  issues: MeasurementIssue[];
  page_number: number;
  source_line: string;
}

export interface PageText {
  page_number: number;
  text: string;
  has_text: boolean;
}

export interface DocumentWarning {
  code: string;
  message: string;
  page_number: number | null;
}

export interface ExtractionResponse {
  page_count: number;
  extraction_method: string;
  character_count: number;
  pages: PageText[];
  measurements: Measurement[];
  warnings: DocumentWarning[];
}

export interface KnowledgeBaseStatus {
  index_ready: boolean;
  chunk_count: number;
  source_count: number;
  embedding_model: string;
  built_at: string | null;
}

export interface EvidencePassage {
  citation_id: string;
  chunk_id: string;
  source_id: string;
  title: string;
  section: string;
  url: string;
  publisher: string;
  attribution: string;
  text: string;
  similarity: number;
}

export interface TestEvidence {
  test_name: string;
  query: string;
  citation_ids: string[];
}

export interface EvidenceResponse {
  passages: EvidencePassage[];
  tests: TestEvidence[];
  unmatched_tests: string[];
  embedding_model: string;
  min_similarity: number;
}

export type Strategy = "zero_shot" | "few_shot" | "rag";

export interface TestExplanation {
  test_name: string;
  reported_value: string;
  unit: string | null;
  reference_range: string | null;
  explanation: string;
  citation_ids: string[];
}

export interface SummaryOutput {
  summary: string;
  test_explanations: TestExplanation[];
  reported_abnormalities: { test_name: string; basis: "report_flag" | "range_comparison"; description: string }[];
  evidence_citations: { citation_id: string; supports: string }[];
  uncertainties: string[];
  questions_for_doctor: string[];
  safety_notice: string;
}

export interface ValidationIssue {
  code: string;
  severity: "error" | "warning";
  message: string;
  location: string | null;
}

export interface ValidationReport {
  status: "passed" | "passed_with_warnings" | "failed";
  issues: ValidationIssue[];
  checks_run: string[];
  note: string;
}

export interface SummaryResponse {
  strategy: Strategy;
  model: string;
  prompt_version: string;
  prompt_sha256: string;
  output: SummaryOutput;
  validation: ValidationReport;
  measurements: Measurement[];
  document_warnings: DocumentWarning[];
  evidence: EvidencePassage[];
  unmatched_tests: string[];
  usage: { prompt_tokens: number | null; output_tokens: number | null; total_tokens: number | null };
  latency_ms: number;
  disclaimer: string;
}

export interface SampleInfo {
  id: string;
  title: string;
  description: string;
}
