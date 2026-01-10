// DMARC Report Types
export interface ReportMetadata {
  org_name: string;
  email: string;
  report_id: string;
  date_range_begin: number;
  date_range_end: number;
}

export interface PolicyPublished {
  domain: string;
  p: 'none' | 'quarantine' | 'reject';
  sp?: string;
  pct: number;
}

export interface PolicyEvaluated {
  disposition: 'none' | 'quarantine' | 'reject';
  dkim: 'pass' | 'fail';
  spf: 'pass' | 'fail';
}

export interface AuthResult {
  domain: string;
  result: 'pass' | 'fail';
}

export interface DMARCRecord {
  source_ip: string;
  count: number;
  policy_evaluated: PolicyEvaluated;
  header_from: string;
  dkim_results: AuthResult[];
  spf_results: AuthResult[];
}

export interface DMARCReport {
  metadata: ReportMetadata;
  policy_published: PolicyPublished;
  records: DMARCRecord[];
}

// Analysis Types
export interface DomainAnalysis {
  domain: string;
  analysis_date: string;
  total_messages: number;
  auth_success_rate: number;
  top_sources: string[];
  failure_reasons: Record<string, number>;
  recommendations: string[];
  trend_data: Record<string, number>;
}

// Dashboard Types
export interface DashboardSummary {
  total_reports: number;
  total_messages: number;
  overall_success_rate: number;
  domains_monitored: number;
  security_issues: number;
  recent_activity: Array<{
    date: string;
    success_rate: number;
    message_count: number;
  }>;
}

// API Response Types
export interface ApiResponse<T> {
  data: T;
  success: boolean;
  message?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
  has_next: boolean;
}

// User Types
export interface User {
  username: string;
  email: string;
  attributes: Record<string, any>;
}