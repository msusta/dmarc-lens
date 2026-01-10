import { get } from 'aws-amplify/api';
import {
  DMARCReport,
  DomainAnalysis,
  DashboardSummary,
  PaginatedResponse,
} from '../types';

const API_NAME = 'dmarcApi';

// Dashboard API
export const getDashboardSummary = async (): Promise<DashboardSummary> => {
  const response = await get({
    apiName: API_NAME,
    path: '/dashboard',
  }).response;
  const data = await response.body.json() as any;
  return data as DashboardSummary;
};

// Reports API
export const getReports = async (params?: {
  page?: number;
  limit?: number;
  domain?: string;
  start_date?: string;
  end_date?: string;
}): Promise<PaginatedResponse<DMARCReport>> => {
  const queryParams = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        queryParams.append(key, value.toString());
      }
    });
  }
  
  const response = await get({
    apiName: API_NAME,
    path: `/reports?${queryParams.toString()}`,
  }).response;
  const data = await response.body.json() as any;
  return data as PaginatedResponse<DMARCReport>;
};

export const getReportById = async (reportId: string): Promise<DMARCReport> => {
  const response = await get({
    apiName: API_NAME,
    path: `/reports/${reportId}`,
  }).response;
  const data = await response.body.json() as any;
  return data as DMARCReport;
};

// Analysis API
export const getDomainAnalysis = async (
  domain: string,
  params?: {
    start_date?: string;
    end_date?: string;
  }
): Promise<DomainAnalysis> => {
  const queryParams = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        queryParams.append(key, value.toString());
      }
    });
  }
  
  const response = await get({
    apiName: API_NAME,
    path: `/analysis/${domain}?${queryParams.toString()}`,
  }).response;
  const data = await response.body.json() as any;
  return data as DomainAnalysis;
};

// Export functionality
export const exportReportData = async (
  reportId: string,
  format: 'json' | 'csv' = 'json'
): Promise<Blob> => {
  const response = await get({
    apiName: API_NAME,
    path: `/reports/${reportId}/export?format=${format}`,
  }).response;
  const blob = await response.body.blob();
  return blob;
};

// Error handling utility
export const handleApiError = (error: any): string => {
  if (error.response?.data?.message) {
    return error.response.data.message;
  }
  if (error.message) {
    return error.message;
  }
  return 'An unexpected error occurred';
};