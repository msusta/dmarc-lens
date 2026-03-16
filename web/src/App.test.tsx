import React from 'react';
import { render, screen } from '@testing-library/react';

// Mock all external dependencies
jest.mock('aws-amplify', () => ({
  Amplify: { configure: jest.fn() },
}));

jest.mock('@aws-amplify/ui-react', () => ({
  Authenticator: ({ children }: { children: (props: any) => React.ReactNode }) =>
    children({ signOut: jest.fn(), user: { username: 'testuser' } }),
}));

jest.mock('./aws-exports', () => ({}));

jest.mock('react-router-dom', () => ({
  BrowserRouter: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Routes: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Route: ({ element }: { element: React.ReactNode }) => <div>{element}</div>,
  Navigate: () => null,
  useNavigate: () => jest.fn(),
}));

jest.mock('@tanstack/react-query', () => ({
  QueryClient: jest.fn().mockImplementation(() => ({})),
  QueryClientProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  useQuery: () => ({ data: undefined, isLoading: false, error: null }),
}));

jest.mock('./services/api', () => ({
  getDashboardSummary: jest.fn(),
  getReports: jest.fn(),
  getReportById: jest.fn(),
  getDomainAnalysis: jest.fn(),
  exportReportData: jest.fn(),
}));

// Mock complex components that have deep dependency trees
jest.mock('./components/Dashboard', () => {
  return function MockDashboard() {
    return <div>DMARC Dashboard</div>;
  };
});

jest.mock('./components/Reports', () => {
  return function MockReports() {
    return <div>Reports</div>;
  };
});

jest.mock('./components/ReportDetail', () => {
  return function MockReportDetail() {
    return <div>ReportDetail</div>;
  };
});

jest.mock('./components/Layout', () => {
  return function MockLayout({ children }: { children: React.ReactNode }) {
    return <div data-testid="layout">{children}</div>;
  };
});

import App from './App';

test('renders the app with layout', () => {
  render(<App />);
  const layout = screen.getByTestId('layout');
  expect(layout).toBeInTheDocument();
});

test('renders DMARC Dashboard', () => {
  render(<App />);
  const dashboard = screen.getByText(/DMARC Dashboard/i);
  expect(dashboard).toBeInTheDocument();
});
