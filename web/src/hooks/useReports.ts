import { useQuery } from '@tanstack/react-query';
import { getReports, getReportById } from '../services/api';
import { DMARCReport, PaginatedResponse } from '../types';

// Mock data for development
const mockReports: DMARCReport[] = [
  {
    metadata: {
      org_name: 'Google Inc.',
      email: 'noreply-dmarc-support@google.com',
      report_id: '12345678901234567890',
      date_range_begin: new Date('2024-01-06T00:00:00Z').getTime() / 1000,
      date_range_end: new Date('2024-01-06T23:59:59Z').getTime() / 1000,
    },
    policy_published: {
      domain: 'example.com',
      p: 'quarantine',
      sp: 'none',
      pct: 100,
    },
    records: [
      {
        source_ip: '192.168.1.100',
        count: 25,
        policy_evaluated: {
          disposition: 'none',
          dkim: 'pass',
          spf: 'pass',
        },
        header_from: 'example.com',
        dkim_results: [
          { domain: 'example.com', result: 'pass' },
        ],
        spf_results: [
          { domain: 'example.com', result: 'pass' },
        ],
      },
      {
        source_ip: '203.0.113.25',
        count: 8,
        policy_evaluated: {
          disposition: 'quarantine',
          dkim: 'fail',
          spf: 'pass',
        },
        header_from: 'example.com',
        dkim_results: [
          { domain: 'example.com', result: 'fail' },
        ],
        spf_results: [
          { domain: 'example.com', result: 'pass' },
        ],
      },
    ],
  },
  {
    metadata: {
      org_name: 'Microsoft Corporation',
      email: 'dmarcreport@microsoft.com',
      report_id: '98765432109876543210',
      date_range_begin: new Date('2024-01-05T00:00:00Z').getTime() / 1000,
      date_range_end: new Date('2024-01-05T23:59:59Z').getTime() / 1000,
    },
    policy_published: {
      domain: 'test.org',
      p: 'reject',
      pct: 100,
    },
    records: [
      {
        source_ip: '198.51.100.10',
        count: 42,
        policy_evaluated: {
          disposition: 'reject',
          dkim: 'fail',
          spf: 'fail',
        },
        header_from: 'test.org',
        dkim_results: [
          { domain: 'test.org', result: 'fail' },
        ],
        spf_results: [
          { domain: 'test.org', result: 'fail' },
        ],
      },
    ],
  },
];

const mockPaginatedResponse: PaginatedResponse<DMARCReport> = {
  items: mockReports,
  total: mockReports.length,
  page: 1,
  limit: 10,
  has_next: false,
};

export const useReports = (params?: {
  page?: number;
  limit?: number;
  domain?: string;
  start_date?: string;
  end_date?: string;
}) => {
  return useQuery({
    queryKey: ['reports', params],
    queryFn: async () => {
      try {
        return await getReports(params);
      } catch (error) {
        console.warn('API not available, using mock data:', error);
        return mockPaginatedResponse;
      }
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

export const useReport = (reportId: string) => {
  return useQuery({
    queryKey: ['report', reportId],
    queryFn: async () => {
      try {
        return await getReportById(reportId);
      } catch (error) {
        console.warn('API not available, using mock data:', error);
        // Find mock report by ID or return first one
        return mockReports.find(r => r.metadata.report_id === reportId) || mockReports[0];
      }
    },
    enabled: !!reportId,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
};