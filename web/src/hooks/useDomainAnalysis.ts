import { useQuery } from '@tanstack/react-query';
import { getDomainAnalysis } from '../services/api';
import { DomainAnalysis } from '../types';

// Mock data for development
const mockDomainData: DomainAnalysis[] = [
  {
    domain: 'example.com',
    analysis_date: '2024-01-07',
    total_messages: 15420,
    auth_success_rate: 92.1,
    top_sources: ['192.168.1.100', '10.0.0.50', '203.0.113.25'],
    failure_reasons: {
      'DKIM Failure': 45,
      'SPF Failure': 32,
      'DMARC Policy': 18,
      'Alignment Issues': 12,
    },
    recommendations: [
      'Review DKIM configuration for mail servers',
      'Update SPF record to include all sending sources',
      'Consider stricter DMARC policy',
    ],
    trend_data: {
      '2024-01-01': 89.2,
      '2024-01-02': 90.1,
      '2024-01-03': 88.7,
      '2024-01-04': 91.3,
      '2024-01-05': 89.8,
      '2024-01-06': 93.1,
      '2024-01-07': 92.1,
    },
  },
  {
    domain: 'test.org',
    analysis_date: '2024-01-07',
    total_messages: 8930,
    auth_success_rate: 78.4,
    top_sources: ['198.51.100.10', '203.0.113.50'],
    failure_reasons: {
      'DKIM Failure': 78,
      'SPF Failure': 65,
      'DMARC Policy': 34,
      'Alignment Issues': 28,
    },
    recommendations: [
      'Urgent: Fix DKIM signing issues',
      'Update SPF record',
      'Implement DMARC monitoring',
    ],
    trend_data: {
      '2024-01-01': 75.2,
      '2024-01-02': 76.1,
      '2024-01-03': 74.7,
      '2024-01-04': 79.3,
      '2024-01-05': 77.8,
      '2024-01-06': 80.1,
      '2024-01-07': 78.4,
    },
  },
];

export const useDomainAnalysis = (domain?: string) => {
  return useQuery({
    queryKey: ['domainAnalysis', domain],
    queryFn: async () => {
      try {
        if (domain) {
          return await getDomainAnalysis(domain);
        } else {
          // Return all domains for overview
          return mockDomainData;
        }
      } catch (error) {
        console.warn('API not available, using mock data:', error);
        return domain 
          ? mockDomainData.find(d => d.domain === domain) || mockDomainData[0]
          : mockDomainData;
      }
    },
    enabled: true,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};