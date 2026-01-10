import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { Box, Typography } from '@mui/material';

interface AuthenticationTrendChartProps {
  data: Array<{
    date: string;
    success_rate: number;
    message_count: number;
  }>;
}

const AuthenticationTrendChart: React.FC<AuthenticationTrendChartProps> = ({ data }) => {
  // Format data for the chart
  const chartData = data.map(item => ({
    date: new Date(item.date).toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric' 
    }),
    'Success Rate (%)': item.success_rate,
    'Messages (K)': Math.round(item.message_count / 1000 * 10) / 10, // Convert to thousands
  }));

  return (
    <Box sx={{ width: '100%', height: 350 }}>
      <Typography variant="h6" gutterBottom>
        Authentication Trends (Last 7 Days)
      </Typography>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis 
            dataKey="date" 
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
            labelFormatter={(label) => `Date: ${label}`}
          />
          <Legend />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="Success Rate (%)"
            stroke="#1976d2"
            strokeWidth={2}
            dot={{ fill: '#1976d2', strokeWidth: 2, r: 4 }}
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="Messages (K)"
            stroke="#dc004e"
            strokeWidth={2}
            dot={{ fill: '#dc004e', strokeWidth: 2, r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </Box>
  );
};

export default AuthenticationTrendChart;