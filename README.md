# DMARC Lens

A serverless, AWS-native platform for analyzing and visualizing DMARC (Domain-based Message Authentication, Reporting & Conformance) email security reports.

## Overview

DMARC Lens helps organizations understand their email authentication posture by automatically ingesting, processing, and visualizing DMARC aggregate reports. The platform provides insights into authentication failures, identifies potential security issues, and offers recommendations for improving email security.

## Features

- **Automated Email Ingestion**: Receives DMARC reports via AWS SES
- **Serverless Processing**: Processes reports using AWS Lambda functions
- **Real-time Analysis**: Analyzes authentication patterns and trends
- **Interactive Dashboard**: React-based web dashboard with charts and filtering
- **Security Insights**: Identifies suspicious patterns and provides recommendations
- **Scalable Architecture**: Fully serverless and cost-effective
- **Cognito Authentication**: Secure access via AWS Cognito user pools

## Architecture

The platform uses a fully serverless architecture built on AWS managed services:

```
DMARC Report Email
  → AWS SES (email ingestion)
    → S3 (raw email storage)
      → Lambda: report_parser (XML parsing, DynamoDB storage)
        → EventBridge (scheduled trigger)
          → Lambda: analysis_engine (trend analysis, recommendations)
            → DynamoDB (structured report + analysis data)
              → Lambda: data_api (REST API)
                → API Gateway (HTTP endpoints)
                  → CloudFront + S3 (React frontend)
                    → Cognito (user authentication)
```

### AWS Services Used

- **AWS SES**: Email ingestion for DMARC reports
- **AWS S3**: Raw email storage and static website hosting
- **AWS Lambda**: Report parsing, analysis engine, and REST API
- **Amazon DynamoDB**: Structured data storage (reports and analysis)
- **AWS API Gateway**: REST API for the web interface
- **Amazon Cognito**: User authentication
- **Amazon CloudFront**: Global content delivery
- **Amazon EventBridge**: Scheduled analysis triggers

## Quick Start

### Prerequisites

- Python 3.11 or higher
- [UV](https://docs.astral.sh/uv/) package manager
- AWS CLI configured with appropriate permissions
- Node.js 18+ (for CDK deployment and frontend)

### Development Setup

1. Clone the repository:
```bash
git clone https://github.com/msusta/dmarc-lens.git
cd dmarc-lens
```

2. Install Python dependencies with UV:
```bash
uv sync --group dev
```

3. Install frontend dependencies:
```bash
cd web && npm install && cd ..
```

4. Install CDK dependencies:
```bash
cd infrastructure && npm install && cd ..
```

### Infrastructure Deployment

1. Bootstrap CDK (first time only):
```bash
cd infrastructure
npx cdk bootstrap
```

2. Deploy the infrastructure:
```bash
npx cdk deploy
```

## Development

### Running Backend Tests

```bash
# Run all tests with coverage
uv run python -m pytest

# Run tests verbose
uv run python -m pytest -v

# Run property-based tests only
uv run python -m pytest -m property

# Run without coverage (faster)
uv run python -m pytest --override-ini="addopts="
```

### Running Frontend Tests

```bash
cd web
npm test -- --watchAll=false
```

### Code Quality

```bash
# Format code
uv run black src/ tests/

# Type checking
uv run mypy src/dmarc_lens --ignore-missing-imports

# Lint code
uv run flake8 src/ tests/
```

### Frontend Development

```bash
cd web
npm start        # Start dev server
npm run build    # Production build
npm test         # Run tests
```

## Project Structure

```
dmarc-lens/
├── src/dmarc_lens/              # Main Python package
│   ├── lambda_functions/        # AWS Lambda handlers
│   │   ├── report_parser.py     #   SES email → parse XML → DynamoDB
│   │   ├── analysis_engine.py   #   Scheduled analysis & trend detection
│   │   ├── data_api.py          #   REST API (API Gateway handler)
│   │   └── auth.py              #   Cognito JWT authorization
│   ├── models/                  # Data models (dataclasses)
│   │   └── dmarc_models.py      #   DMARCReport, DMARCRecord, etc.
│   ├── parsers/                 # DMARC report parsers
│   ├── analyzers/               # Analysis logic
│   └── utils/                   # Utility functions
│       ├── email_utils.py       #   MIME/email parsing
│       ├── xml_utils.py         #   XML extraction helpers
│       └── logging_utils.py     #   Structured logging
├── web/                         # React frontend (TypeScript)
│   ├── src/
│   │   ├── components/          #   Dashboard, Reports, Layout, charts
│   │   ├── hooks/               #   useDashboard, useDomainAnalysis
│   │   ├── services/            #   API client (api.ts)
│   │   └── types/               #   TypeScript type definitions
│   └── package.json
├── infrastructure/              # AWS CDK infrastructure code
│   ├── dmarc_lens_stack.py      #   CDK stack definition
│   ├── environments/            #   Per-environment config (dev, prod)
│   └── app.py                   #   CDK app entry point
├── tests/                       # Python test files
│   ├── unit/                    #   Unit tests
│   ├── integration/             #   Integration tests
│   └── fixtures/                #   Test data (sample DMARC XML)
├── docs/                        # Documentation
├── pyproject.toml               # Python project config (UV, pytest, mypy, black)
├── .github/workflows/           # CI/CD (GitHub Actions)
└── Makefile                     # Common development tasks
```

## API Endpoints

The REST API (served via API Gateway + Lambda `data_api`) provides:

| Method | Endpoint                    | Description                        |
|--------|-----------------------------|------------------------------------|
| GET    | `/dashboard`                | Dashboard summary with trends      |
| GET    | `/reports`                  | Paginated list of DMARC reports    |
| GET    | `/reports/{id}`             | Individual report details          |
| GET    | `/reports/{id}/export`      | Export report as JSON or CSV       |
| GET    | `/analysis/{domain}`        | Domain-specific analysis           |

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass (`uv run python -m pytest`)
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For questions, issues, or contributions, please visit the [GitHub repository](https://github.com/msusta/dmarc-lens).
