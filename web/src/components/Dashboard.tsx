import React, { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Card,
  CardContent,
  CircularProgress,
  Alert,
  Tabs,
  Tab,
} from '@mui/material';
import { useDashboard } from '../hooks/useDashboard';
import { useDomainAnalysis } from '../hooks/useDomainAnalysis';
import { DomainAnalysis } from '../types';
import AuthenticationTrendChart from './charts/AuthenticationTrendChart';
import FailureSourcesChart from './charts/FailureSourcesChart';
import DomainComparisonChart from './charts/DomainComparisonChart';
import TimePeriodFilter, { TimePeriod } from './TimePeriodFilter';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`dashboard-tabpanel-${index}`}
      aria-labelledby={`dashboard-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
}

const Dashboard: React.FC = () => {
  const [tabValue, setTabValue] = useState(0);
  const [timePeriod, setTimePeriod] = useState<TimePeriod>({
    preset: 'last7days',
    startDate: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000),
    endDate: new Date(),
  });

  // Calculate days from timePeriod
  const days = timePeriod.startDate && timePeriod.endDate
    ? Math.max(1, Math.round(
        (timePeriod.endDate.getTime() - timePeriod.startDate.getTime()) / (24 * 60 * 60 * 1000)
      ))
    : 7;

  const { data: dashboardData, isLoading: dashboardLoading, error: dashboardError, refetch: refetchDashboard } = useDashboard(days);
  const { data: domainData, isLoading: domainLoading, error: domainError } = useDomainAnalysis();

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const handleRefresh = () => {
    refetchDashboard();
  };

  if (dashboardLoading || domainLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (dashboardError || domainError) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        Error loading dashboard data. Using mock data for demonstration.
      </Alert>
    );
  }

  const domains = Array.isArray(domainData) ? domainData : [domainData].filter((d): d is DomainAnalysis => d !== undefined);
  const aggregatedFailures = domains.reduce((acc, domain) => {
    if (domain?.failure_reasons) {
      Object.entries(domain.failure_reasons).forEach(([reason, count]) => {
        acc[reason] = (acc[reason] || 0) + count;
      });
    }
    return acc;
  }, {} as Record<string, number>);

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          DMARC Dashboard
        </Typography>
      </Box>

      <TimePeriodFilter
        value={timePeriod}
        onChange={setTimePeriod}
        onRefresh={handleRefresh}
      />
      
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3, mb: 3 }}>
        {/* Summary Cards */}
        <Box sx={{ minWidth: 200, flex: '1 1 200px' }}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Total Reports
              </Typography>
              <Typography variant="h5" component="div">
                {dashboardData?.total_reports?.toLocaleString() || '--'}
              </Typography>
            </CardContent>
          </Card>
        </Box>
        
        <Box sx={{ minWidth: 200, flex: '1 1 200px' }}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Auth Success Rate
              </Typography>
              <Typography 
                variant="h5" 
                component="div"
                color={dashboardData && dashboardData.overall_success_rate > 85 ? 'success.main' : 'warning.main'}
              >
                {dashboardData?.overall_success_rate?.toFixed(1)}%
              </Typography>
            </CardContent>
          </Card>
        </Box>
        
        <Box sx={{ minWidth: 200, flex: '1 1 200px' }}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Domains Monitored
              </Typography>
              <Typography variant="h5" component="div">
                {dashboardData?.domains_monitored || '--'}
              </Typography>
            </CardContent>
          </Card>
        </Box>
        
        <Box sx={{ minWidth: 200, flex: '1 1 200px' }}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom>
                Security Issues
              </Typography>
              <Typography 
                variant="h5" 
                component="div"
                color={dashboardData && dashboardData.security_issues > 0 ? 'error.main' : 'success.main'}
              >
                {dashboardData?.security_issues || '--'}
              </Typography>
            </CardContent>
          </Card>
        </Box>
      </Box>

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs value={tabValue} onChange={handleTabChange}>
          <Tab label="Overview" />
          <Tab label="Domain Analysis" />
        </Tabs>
      </Box>

      <TabPanel value={tabValue} index={0}>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
          {/* Authentication Trends Chart */}
          <Box sx={{ flex: '2 1 400px', minWidth: 400 }}>
            <Paper sx={{ p: 2 }}>
              {dashboardData?.recent_activity ? (
                <AuthenticationTrendChart data={dashboardData.recent_activity} />
              ) : (
                <Box sx={{ height: 350, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Typography color="textSecondary">No trend data available</Typography>
                </Box>
              )}
            </Paper>
          </Box>

          {/* Failure Sources Chart */}
          <Box sx={{ flex: '1 1 300px', minWidth: 300 }}>
            <Paper sx={{ p: 2 }}>
              {Object.keys(aggregatedFailures).length > 0 ? (
                <FailureSourcesChart data={aggregatedFailures} />
              ) : (
                <Box sx={{ height: 350, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Typography color="textSecondary">No failure data available</Typography>
                </Box>
              )}
            </Paper>
          </Box>
        </Box>
      </TabPanel>

      <TabPanel value={tabValue} index={1}>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
          {/* Domain Comparison Chart */}
          <Box sx={{ flex: '1 1 600px', minWidth: 600 }}>
            <Paper sx={{ p: 2 }}>
              {domains.length > 0 ? (
                <DomainComparisonChart data={domains} />
              ) : (
                <Box sx={{ height: 350, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Typography color="textSecondary">No domain data available</Typography>
                </Box>
              )}
            </Paper>
          </Box>

          {/* Domain Details */}
          <Box sx={{ flex: '1 1 300px', minWidth: 300 }}>
            <Paper sx={{ p: 2, height: 400, overflow: 'auto' }}>
              <Typography variant="h6" gutterBottom>
                Domain Details
              </Typography>
              {domains.map((domain, index) => (
                <Box key={index} sx={{ mb: 2, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
                  <Typography variant="subtitle1" fontWeight="bold">
                    {domain.domain}
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    Success Rate: {domain.auth_success_rate.toFixed(1)}%
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    Messages: {domain.total_messages.toLocaleString()}
                  </Typography>
                  {domain.recommendations && domain.recommendations.length > 0 && (
                    <Box sx={{ mt: 1 }}>
                      <Typography variant="caption" color="warning.main">
                        Recommendations:
                      </Typography>
                      <ul style={{ margin: 0, paddingLeft: 16 }}>
                        {domain.recommendations.slice(0, 2).map((rec, i) => (
                          <li key={i}>
                            <Typography variant="caption">{rec}</Typography>
                          </li>
                        ))}
                      </ul>
                    </Box>
                  )}
                </Box>
              ))}
            </Paper>
          </Box>
        </Box>
      </TabPanel>
    </Box>
  );
};

export default Dashboard;