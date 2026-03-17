# Project Structure

## Current Structure

```
dmarc-lens/
├── src/
│   └── dmarc_lens/                  # Main Python package
│       ├── __init__.py
│       ├── main.py                  # CLI entry point (stub)
│       ├── lambda_functions/        # AWS Lambda handlers
│       │   ├── __init__.py
│       │   ├── report_parser.py     # SES → parse DMARC XML → DynamoDB
│       │   ├── analysis_engine.py   # Scheduled analysis & trend detection
│       │   ├── data_api.py          # REST API (API Gateway handler)
│       │   └── auth.py              # Cognito JWT authorization
│       ├── models/                  # Data models (Python dataclasses)
│       │   ├── __init__.py
│       │   └── dmarc_models.py      # DMARCReport, DMARCRecord, PolicyEvaluated, etc.
│       ├── parsers/                 # DMARC report parsers
│       │   └── __init__.py
│       ├── analyzers/               # Analysis logic
│       │   └── __init__.py
│       └── utils/                   # Utility functions
│           ├── __init__.py
│           ├── email_utils.py       # MIME/email parsing
│           ├── xml_utils.py         # XML text extraction helpers
│           └── logging_utils.py     # Structured logging
├── web/                             # React frontend (TypeScript)
│   ├── public/
│   ├── src/
│   │   ├── App.tsx                  # Root component (Authenticator + Router)
│   │   ├── aws-exports.ts          # Amplify configuration
│   │   ├── components/
│   │   │   ├── Dashboard.tsx        # Main dashboard with summary cards + charts
│   │   │   ├── Reports.tsx          # Paginated report list with filters
│   │   │   ├── ReportDetail.tsx     # Individual report detail view
│   │   │   ├── Layout.tsx           # App shell (nav, sidebar)
│   │   │   ├── TimePeriodFilter.tsx # Date range filter component
│   │   │   └── charts/             # Recharts chart components
│   │   │       ├── AuthenticationTrendChart.tsx
│   │   │       ├── FailureSourcesChart.tsx
│   │   │       └── DomainComparisonChart.tsx
│   │   ├── hooks/
│   │   │   ├── useDashboard.ts      # Dashboard data fetching hook
│   │   │   └── useDomainAnalysis.ts # Domain analysis fetching hook
│   │   ├── services/
│   │   │   └── api.ts               # API client (Amplify auth headers)
│   │   ├── types/
│   │   │   └── index.ts             # TypeScript type definitions
│   │   └── __mocks__/
│   │       └── styleMock.js         # Jest CSS module mock
│   ├── package.json
│   └── tsconfig.json
├── infrastructure/                  # AWS CDK infrastructure code
│   ├── app.py                       # CDK app entry point (Python)
│   ├── dmarc_lens_stack.py          # CDK stack definition (Python)
│   ├── environments/                # Per-environment config
│   │   ├── dev.json
│   │   └── prod.json
│   ├── cdk.json                     # CDK config (uses uv run for Python)
│   └── package.json                 # CDK CLI (Node.js wrapper only)
├── tests/                           # Python test files
│   ├── unit/
│   │   ├── test_dmarc_models.py     # Data model tests
│   │   ├── test_report_parser.py    # Parser tests
│   │   ├── test_analysis_engine.py  # Analysis engine tests
│   │   ├── test_data_api.py         # API handler tests
│   │   ├── test_email_utils.py      # Email utility tests
│   │   └── test_xml_utils.py        # XML utility tests
│   ├── integration/                 # Integration tests (placeholder)
│   └── fixtures/                    # Test data
│       └── sample_dmarc_report.xml
├── docs/                            # Documentation
│   ├── aws-setup.md                 # AWS configuration guide
│   └── deployment.md                # Deployment guide
├── scripts/                         # Utility scripts
├── .github/
│   └── workflows/
│       └── deploy.yml               # CI/CD pipeline (UV, pytest, frontend build)
├── pyproject.toml                   # Python project config (UV, pytest, mypy, black)
├── Makefile                         # Common development tasks
├── .gitignore
└── README.md
```

## Organization Principles
- Source code in `src/dmarc_lens/` — installable Python package via UV
- Lambda functions are self-contained handlers in `lambda_functions/`
- Frontend is a full React app in `web/` (CRA + TypeScript + MUI)
- Infrastructure as code in `infrastructure/` (AWS CDK v2)
- Dependencies managed via `pyproject.toml` dependency-groups (dev, cdk)
- Type hints throughout; mypy strict mode enforced
- Follow PEP 8 style guidelines (enforced by black)
- Prefix test files with `test_`

## File Naming Conventions
- Use snake_case for Python files and directories
- Use PascalCase for React components and TypeScript class names
- Use camelCase for TypeScript functions and variables
- Use UPPER_CASE for constants
- Prefix test files with `test_` (Python) or `.test.` (TypeScript)
