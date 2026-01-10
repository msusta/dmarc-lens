import React from 'react';
import {
  Box,
  Typography,
  Paper,
  Button,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Divider,
  CircularProgress,
  Alert,
} from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowBack, Download } from '@mui/icons-material';
import { useReport } from '../hooks/useReports';
import { exportReportData } from '../services/api';

const ReportDetail: React.FC = () => {
  const { reportId } = useParams<{ reportId: string }>();
  const navigate = useNavigate();
  const { data: report, isLoading, error } = useReport(reportId || '');

  const handleExport = async (format: 'json' | 'csv' = 'json') => {
    if (!reportId) return;
    
    try {
      const blob = await exportReportData(reportId, format);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = `dmarc-report-${reportId}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Export failed:', error);
      // Mock export for demo
      const mockData = format === 'json' 
        ? JSON.stringify(report, null, 2)
        : 'Report ID,Domain,Source IP,Count,DKIM,SPF,Disposition\n' +
          report?.records.map(r => 
            `${reportId},${report.policy_published.domain},${r.source_ip},${r.count},${r.policy_evaluated.dkim},${r.policy_evaluated.spf},${r.policy_evaluated.disposition}`
          ).join('\n');
      
      const blob = new Blob([mockData], { type: format === 'json' ? 'application/json' : 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `dmarc-report-${reportId}.${format}`;
      a.click();
      window.URL.revokeObjectURL(url);
    }
  };

  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getDispositionColor = (disposition: string) => {
    switch (disposition) {
      case 'none':
        return 'success';
      case 'quarantine':
        return 'warning';
      case 'reject':
        return 'error';
      default:
        return 'default';
    }
  };

  const getResultColor = (result: string) => {
    return result === 'pass' ? 'success' : 'error';
  };

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error || !report) {
    return (
      <Box>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Button
            startIcon={<ArrowBack />}
            onClick={() => navigate('/reports')}
            sx={{ mr: 2 }}
          >
            Back to Reports
          </Button>
        </Box>
        <Alert severity="error">
          Report not found or failed to load.
        </Alert>
      </Box>
    );
  }

  const totalMessages = report.records.reduce((sum, record) => sum + record.count, 0);
  const passedMessages = report.records
    .filter(r => r.policy_evaluated.dkim === 'pass' && r.policy_evaluated.spf === 'pass')
    .reduce((sum, record) => sum + record.count, 0);
  const successRate = totalMessages > 0 ? (passedMessages / totalMessages) * 100 : 0;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <Button
            startIcon={<ArrowBack />}
            onClick={() => navigate('/reports')}
            sx={{ mr: 2 }}
          >
            Back to Reports
          </Button>
          <Typography variant="h4" component="h1">
            DMARC Report Details
          </Typography>
        </Box>
        
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<Download />}
            onClick={() => handleExport('json')}
            size="small"
          >
            Export JSON
          </Button>
          <Button
            variant="outlined"
            startIcon={<Download />}
            onClick={() => handleExport('csv')}
            size="small"
          >
            Export CSV
          </Button>
        </Box>
      </Box>

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
        {/* Report Metadata */}
        <Box sx={{ flex: '1 1 400px', minWidth: 400 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Report Metadata
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <Box>
                  <Typography variant="body2" color="textSecondary">Report ID</Typography>
                  <Typography variant="body1" fontFamily="monospace">
                    {report.metadata.report_id}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="body2" color="textSecondary">Organization</Typography>
                  <Typography variant="body1">{report.metadata.org_name}</Typography>
                </Box>
                <Box>
                  <Typography variant="body2" color="textSecondary">Contact Email</Typography>
                  <Typography variant="body1">{report.metadata.email}</Typography>
                </Box>
                <Box>
                  <Typography variant="body2" color="textSecondary">Report Period</Typography>
                  <Typography variant="body1">
                    {formatDate(report.metadata.date_range_begin)} - {formatDate(report.metadata.date_range_end)}
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Box>

        {/* Policy Information */}
        <Box sx={{ flex: '1 1 400px', minWidth: 400 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Published Policy
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <Box>
                  <Typography variant="body2" color="textSecondary">Domain</Typography>
                  <Typography variant="body1" fontWeight="medium">
                    {report.policy_published.domain}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="body2" color="textSecondary">Policy</Typography>
                  <Chip
                    label={report.policy_published.p}
                    size="small"
                    color={getDispositionColor(report.policy_published.p) as any}
                  />
                </Box>
                <Box>
                  <Typography variant="body2" color="textSecondary">Subdomain Policy</Typography>
                  <Typography variant="body1">
                    {report.policy_published.sp || 'Same as domain policy'}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="body2" color="textSecondary">Percentage</Typography>
                  <Typography variant="body1">{report.policy_published.pct}%</Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Box>
      </Box>

      {/* Summary Statistics */}
      <Box sx={{ mt: 3 }}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Summary Statistics
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3, justifyContent: 'space-around' }}>
              <Box sx={{ textAlign: 'center', minWidth: 120 }}>
                <Typography variant="h4" color="primary">
                  {totalMessages.toLocaleString()}
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  Total Messages
                </Typography>
              </Box>
              <Box sx={{ textAlign: 'center', minWidth: 120 }}>
                <Typography variant="h4" color="success.main">
                  {passedMessages.toLocaleString()}
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  Passed Authentication
                </Typography>
              </Box>
              <Box sx={{ textAlign: 'center', minWidth: 120 }}>
                <Typography 
                  variant="h4" 
                  color={successRate > 85 ? 'success.main' : successRate > 70 ? 'warning.main' : 'error.main'}
                >
                  {successRate.toFixed(1)}%
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  Success Rate
                </Typography>
              </Box>
              <Box sx={{ textAlign: 'center', minWidth: 120 }}>
                <Typography variant="h4" color="info.main">
                  {report.records.length}
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  Source IPs
                </Typography>
              </Box>
            </Box>
          </CardContent>
        </Card>
      </Box>

      {/* Detailed Records */}
      <Box sx={{ mt: 3 }}>
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            Detailed Records
          </Typography>
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Source IP</TableCell>
                  <TableCell>Messages</TableCell>
                  <TableCell>DKIM</TableCell>
                  <TableCell>SPF</TableCell>
                  <TableCell>Disposition</TableCell>
                  <TableCell>Header From</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {report.records.map((record, index) => (
                  <TableRow key={index}>
                    <TableCell>
                      <Typography variant="body2" fontFamily="monospace">
                        {record.source_ip}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {record.count.toLocaleString()}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={record.policy_evaluated.dkim}
                        size="small"
                        color={getResultColor(record.policy_evaluated.dkim) as any}
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={record.policy_evaluated.spf}
                        size="small"
                        color={getResultColor(record.policy_evaluated.spf) as any}
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={record.policy_evaluated.disposition}
                        size="small"
                        color={getDispositionColor(record.policy_evaluated.disposition) as any}
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {record.header_from}
                      </Typography>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      </Box>

      {/* Authentication Results Details */}
      <Box sx={{ mt: 3 }}>
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            Authentication Results Details
          </Typography>
          {report.records.map((record, recordIndex) => (
            <Box key={recordIndex} sx={{ mb: 3 }}>
              <Typography variant="subtitle1" gutterBottom>
                Source IP: {record.source_ip} ({record.count} messages)
              </Typography>
              
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                <Box sx={{ flex: '1 1 300px', minWidth: 300 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    DKIM Results
                  </Typography>
                  {record.dkim_results.map((dkim, dkimIndex) => (
                    <Box key={dkimIndex} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                      <Typography variant="body2">{dkim.domain}:</Typography>
                      <Chip
                        label={dkim.result}
                        size="small"
                        color={getResultColor(dkim.result) as any}
                        variant="outlined"
                      />
                    </Box>
                  ))}
                </Box>
                
                <Box sx={{ flex: '1 1 300px', minWidth: 300 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    SPF Results
                  </Typography>
                  {record.spf_results.map((spf, spfIndex) => (
                    <Box key={spfIndex} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                      <Typography variant="body2">{spf.domain}:</Typography>
                      <Chip
                        label={spf.result}
                        size="small"
                        color={getResultColor(spf.result) as any}
                        variant="outlined"
                      />
                    </Box>
                  ))}
                </Box>
              </Box>
              
              {recordIndex < report.records.length - 1 && <Divider sx={{ mt: 2 }} />}
            </Box>
          ))}
        </Paper>
      </Box>
    </Box>
  );
};

export default ReportDetail;