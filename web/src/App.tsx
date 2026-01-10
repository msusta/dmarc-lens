import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Amplify } from 'aws-amplify';
import { Authenticator } from '@aws-amplify/ui-react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import awsconfig from './aws-exports';
import Dashboard from './components/Dashboard';
import Reports from './components/Reports';
import ReportDetail from './components/ReportDetail';
import Layout from './components/Layout';
import '@aws-amplify/ui-react/styles.css';
import './App.css';

// Configure Amplify
Amplify.configure(awsconfig);

// Create Material-UI theme
const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
  },
});

// Create React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <QueryClientProvider client={queryClient}>
        <Authenticator>
          {({ signOut, user }) => (
            <Router>
              <Layout user={user} signOut={signOut}>
                <Routes>
                  <Route path="/" element={<Navigate to="/dashboard" replace />} />
                  <Route path="/dashboard" element={<Dashboard />} />
                  <Route path="/reports" element={<Reports />} />
                  <Route path="/reports/:reportId" element={<ReportDetail />} />
                </Routes>
              </Layout>
            </Router>
          )}
        </Authenticator>
      </QueryClientProvider>
    </ThemeProvider>
  );
}

export default App;
