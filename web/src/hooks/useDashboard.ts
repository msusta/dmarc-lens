import { useQuery } from '@tanstack/react-query';
import { getDashboardSummary } from '../services/api';
import { DashboardSummary } from '../types';

// Mock data for development
const mockDashboardData: DashboardSummary = {
  total_reports: 156,
  total_messages: 45230,
  overall_success_rate: 87.3,
  domains_monitored: 12,
  security_issues: 3,
  recent_activity: [
    { date: '2024-01-01', success_rate: 85.2, message_count: 1250 },
    { date: '2024-01-02', success_rate: 88.1, message_count: 1340 },
    { date: '2024-01-03', success_rate: 86.7, message_count: 1180 },
    { date: '2024-01-04', success_rate: 89.3, message_count: 1420 },
    { date: '2024-01-05', success_rate: 87.8, message_count: 1380 },
    { date: '2024-01-06', success_rate: 90.1, message_count: 1560 },
    { date: '2024-01-07', success_rate: 88.9, message_count: 1490 },
  ],
};

export const useDashboard = (days?: number) => {
  return useQuery({
    queryKey: ['dashboard', days],
    queryFn: async () => {
      try {
        return await getDashboardSummary(days);
      } catch (error) {
        console.warn('API not available, using mock data:', error);
        return mockDashboardData;
      }
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchInterval: 30 * 1000, // 30 seconds
  });
};
