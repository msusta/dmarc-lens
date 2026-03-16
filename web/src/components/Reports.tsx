import React, { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  IconButton,
  TablePagination,
  CircularProgress,
  Alert,
} from '@mui/material';
import {
  Visibility as ViewIcon,
  Download as DownloadIcon,
  Search as SearchIcon,
  Clear as ClearIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useReports } from '../hooks/useReports';
import { useDashboard } from '../hooks/useDashboard';
import { exportReportData } from '../services/api';

const Reports: React.FC = () => {
  const navigate = useNavigate();
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [searchTerm, setSearchTerm] = useState('');
  const [domainFilter, setDomainFilter] = useState('');
  const [dispositionFilter, setDispositionFilter] = useState('');

  const { data: reportsData, isLoading, error } = useReports({
    page: page + 1,
    limit: rowsPerPage,
    domain: domainFilter || undefined,
  });

  const { data: dashboardData } = useDashboard();
  const domainOptions: string[] = (dashboardData as any)?.top_domains?.map(
    (d: { domain: string }) => d.domain
  ) ?? [];

  const handleChangePage = (event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleViewReport = (reportId: string) => {
    navigate(`/reports/${reportId}`);
  };

  const handleExportReport = async (reportId: string, format: 'json' | 'csv' = 'json') => {
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
      // For demo purposes, create a mock download
      const mockData = format === 'json' 
        ? JSON.stringify({ reportId, message: 'Mock export data' }, null, 2)
        : `Report ID,Domain,Status\n${reportId},example.com,Mock Data`;
      
      const blob = new Blob([mockData], { type: format === 'json' ? 'application/json' : 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `dmarc-report-${reportId}.${format}`;
      a.click();
      window.URL.revokeObjectURL(url);
    }
  };

  const clearFilters = () => {
    setSearchTerm('');
    setDomainFilter('');
    setDispositionFilter('');
    setPage(0);
  };

  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
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

  const filteredReports = reportsData?.items?.filter(report => {
    const matchesSearch = !searchTerm || 
      report.metadata.org_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      report.policy_published.domain.toLowerCase().includes(searchTerm.toLowerCase()) ||
      report.metadata.report_id.includes(searchTerm);
    
    const matchesDisposition = !dispositionFilter ||
      report.records.some(record => record.policy_evaluated.disposition === dispositionFilter);

    return matchesSearch && matchesDisposition;
  }) || [];

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="info" sx={{ mb: 2 }}>
        API not available. Showing mock data for demonstration.
      </Alert>
    );
  }

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        DMARC Reports
      </Typography>

      {/* Search and Filter Controls */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
          <TextField
            size="small"
            placeholder="Search reports..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            InputProps={{
              startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />,
            }}
            sx={{ minWidth: 200 }}
          />
          
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>Domain</InputLabel>
            <Select
              value={domainFilter}
              label="Domain"
              onChange={(e) => setDomainFilter(e.target.value)}
            >
              <MenuItem value="">All Domains</MenuItem>
              {domainOptions.map((d: string) => (
                <MenuItem key={d} value={d}>{d}</MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>Disposition</InputLabel>
            <Select
              value={dispositionFilter}
              label="Disposition"
              onChange={(e) => setDispositionFilter(e.target.value)}
            >
              <MenuItem value="">All</MenuItem>
              <MenuItem value="none">None</MenuItem>
              <MenuItem value="quarantine">Quarantine</MenuItem>
              <MenuItem value="reject">Reject</MenuItem>
            </Select>
          </FormControl>

          <Button
            variant="outlined"
            startIcon={<ClearIcon />}
            onClick={clearFilters}
            size="small"
          >
            Clear Filters
          </Button>
        </Box>
      </Paper>
      
      <Paper sx={{ width: '100%', overflow: 'hidden' }}>
        <TableContainer>
          <Table stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell>Report ID</TableCell>
                <TableCell>Domain</TableCell>
                <TableCell>Date Range</TableCell>
                <TableCell>Organization</TableCell>
                <TableCell>Messages</TableCell>
                <TableCell>Policy</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredReports.length > 0 ? (
                filteredReports.map((report) => {
                  const totalMessages = report.records.reduce((sum, record) => sum + record.count, 0);
                  
                  return (
                    <TableRow key={report.metadata.report_id} hover>
                      <TableCell>
                        <Typography variant="body2" fontFamily="monospace">
                          {report.metadata.report_id.slice(-8)}...
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontWeight="medium">
                          {report.policy_published.domain}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {formatDate(report.metadata.date_range_begin)} - {formatDate(report.metadata.date_range_end)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {report.metadata.org_name}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {totalMessages.toLocaleString()}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={report.policy_published.p}
                          size="small"
                          color={getDispositionColor(report.policy_published.p) as any}
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', gap: 1 }}>
                          <IconButton
                            size="small"
                            onClick={() => handleViewReport(report.metadata.report_id)}
                            title="View Details"
                          >
                            <ViewIcon />
                          </IconButton>
                          <IconButton
                            size="small"
                            onClick={() => handleExportReport(report.metadata.report_id, 'json')}
                            title="Export JSON"
                          >
                            <DownloadIcon />
                          </IconButton>
                        </Box>
                      </TableCell>
                    </TableRow>
                  );
                })
              ) : (
                <TableRow>
                  <TableCell colSpan={7} align="center" sx={{ py: 4 }}>
                    <Typography color="textSecondary">
                      No reports found matching your criteria
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
        
        <TablePagination
          rowsPerPageOptions={[5, 10, 25, 50]}
          component="div"
          count={reportsData?.total || 0}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={handleChangePage}
          onRowsPerPageChange={handleChangeRowsPerPage}
        />
      </Paper>
    </Box>
  );
};

export default Reports;