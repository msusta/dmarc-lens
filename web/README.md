# DMARC Lens Web Application

This is the React-based web interface for the DMARC Lens platform, providing visualization and analysis of DMARC email security reports.

## Features

- **Authentication**: Secure login using AWS Cognito
- **Dashboard**: Overview of DMARC activity and authentication metrics
- **Reports**: Detailed listing and analysis of DMARC reports
- **Responsive Design**: Works on desktop and mobile devices
- **Real-time Data**: Live updates from the DMARC analysis backend

## Technology Stack

- **React 18** with TypeScript
- **Material-UI (MUI)** for UI components
- **AWS Amplify** for authentication and API integration
- **React Router** for navigation
- **React Query** for data fetching and caching
- **Recharts** for data visualization

## Getting Started

### Prerequisites

- Node.js 16+ and npm
- AWS account with Cognito User Pool configured
- DMARC Lens backend API deployed

### Installation

1. Install dependencies:
   ```bash
   npm install
   ```

2. Copy environment configuration:
   ```bash
   cp .env.example .env.local
   ```

3. Update `.env.local` with your AWS configuration:
   ```
   REACT_APP_AWS_REGION=your-aws-region
   REACT_APP_USER_POOL_ID=your-user-pool-id
   REACT_APP_USER_POOL_CLIENT_ID=your-user-pool-client-id
   REACT_APP_IDENTITY_POOL_ID=your-identity-pool-id
   REACT_APP_API_ENDPOINT=your-api-gateway-endpoint
   ```

### Development

Start the development server:
```bash
npm start
```

The application will open at `http://localhost:3000`.

### Building for Production

Build the application for production:
```bash
npm run build
```

The built files will be in the `build/` directory, ready for deployment to S3 or CloudFront.

### Testing

Run the test suite:
```bash
npm test
```

## Project Structure

```
src/
├── components/          # React components
│   ├── Dashboard.tsx    # Main dashboard view
│   ├── Layout.tsx       # Application layout with navigation
│   ├── Reports.tsx      # Reports listing view
│   └── ReportDetail.tsx # Individual report details
├── hooks/               # Custom React hooks
│   └── useAuth.ts       # Authentication hook
├── services/            # API service functions
│   └── api.ts           # Backend API integration
├── types/               # TypeScript type definitions
│   └── index.ts         # DMARC and application types
├── App.tsx              # Main application component
├── aws-exports.ts       # AWS Amplify configuration
└── index.tsx            # Application entry point
```

## Configuration

The application uses environment variables for configuration:

- `REACT_APP_AWS_REGION`: AWS region for Cognito and API
- `REACT_APP_USER_POOL_ID`: Cognito User Pool ID
- `REACT_APP_USER_POOL_CLIENT_ID`: Cognito User Pool Client ID
- `REACT_APP_IDENTITY_POOL_ID`: Cognito Identity Pool ID
- `REACT_APP_API_ENDPOINT`: API Gateway endpoint URL

## Deployment

The application is designed to be deployed as a static website on AWS S3 with CloudFront distribution. The CDK infrastructure automatically handles the deployment configuration.

## Authentication Flow

1. Users are redirected to AWS Cognito hosted UI for login
2. After successful authentication, JWT tokens are stored
3. API requests include the JWT token for authorization
4. Token refresh is handled automatically by AWS Amplify

## API Integration

The application communicates with the DMARC Lens backend through API Gateway endpoints:

- `GET /dashboard` - Dashboard summary data
- `GET /reports` - List of DMARC reports with filtering
- `GET /reports/{id}` - Individual report details
- `GET /analysis/{domain}` - Domain-specific analysis data

All API requests are authenticated using JWT tokens from Cognito.