import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { Box, Typography } from '@mui/material';
import { DomainAnalysis } from '../../types';

interface DomainComparisonChartProps {
  data: DomainAnalysis[];
}

const DomainComparisonChart: React.FC<DomainComparisonChartProps> = ({ data }) => {
  // Format data for the chart
  const chartData = data.map(domain => ({
    domain: domain.domain,
    'Success Rate (%)': domain.auth_success_rate,
    'Messages (K)': Math.round(domain.total_messages / 1000 * 10) / 10,
  }));

  return (
    <Box sx={{ width: '100%', height: 350 }}>
      <Typography variant="h6" gutterBottom>
        Domain Performance Comparison
      </Typography>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis 
            dataKey="domain" 
            tick={{ fontSize: 12 }}
          />
          <YAxis 
            yAxisId="left"
            tick={{ fontSize: 12 }}
            label={{ value: 'Success Rate (%)', angle: -90, position: 'insideLeft' }}
          />
          <YAxis 
            yAxisId="right" 
            orientation="right"
            tick={{ fontSize: 12 }}
            label={{ value: 'Messages (K)', angle: 90, position: 'insideRight' }}
          />
          <Tooltip 
            formatter={(value, name) => [
              typeof value === 'number' ? value.toFixed(1) : value, 
              name
            ]}
          />
          <Legend />
          <Bar
            yAxisId="left"
            dataKey="Success Rate (%)"
            fill="#1976d2"
            name="Success Rate (%)"
          />
          <Bar
            yAxisId="right"
            dataKey="Messages (K)"
            fill="#dc004e"
            name="Messages (K)"
          />
        </BarChart>
      </ResponsiveContainer>
    </Box>
  );
};

export default DomainComparisonChart;