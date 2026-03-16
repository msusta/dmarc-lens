# Technology Stack

## Development Environment
- **Language**: Python 3.11+
- **Package Manager**: UV with pyproject.toml (hatchling build backend)
- **Frontend**: React 19 with TypeScript
- **Version Control**: Git with GitHub remote (msusta/dmarc-lens)
- **CI/CD**: GitHub Actions

## Python Stack
- **Package Management**: UV with dependency-groups in pyproject.toml
- **Testing**: pytest with hypothesis (property-based), pytest-cov, pytest-mock, moto (AWS mocking)
- **Formatting**: black
- **Linting**: flake8
- **Type Checking**: mypy (strict mode with targeted overrides for boto3 typing)
- **AWS SDK**: boto3 with boto3-stubs for type hints

## Frontend Stack
- **Framework**: React 19 with TypeScript (Create React App)
- **UI Library**: MUI (Material UI) v7
- **Data Fetching**: TanStack React Query v5
- **Routing**: react-router-dom v7
- **Charts**: Recharts v3
- **Authentication**: AWS Amplify v6 with @aws-amplify/ui-react
- **Date Handling**: date-fns v4

## AWS Services
- **SES**: Email ingestion
- **S3**: Raw email storage, static website hosting
- **Lambda**: Report parsing, analysis engine, REST API
- **DynamoDB**: Structured data storage
- **API Gateway**: REST API
- **Cognito**: User authentication
- **CloudFront**: CDN
- **EventBridge**: Scheduled analysis triggers
- **CDK**: Infrastructure as code (v2, TypeScript/Python)

## Common Commands

```bash
# Environment setup
uv sync --group dev              # Install all dev dependencies
cd web && npm install            # Install frontend dependencies

# Backend development
uv run python -m pytest          # Run tests with coverage
uv run python -m pytest -v       # Verbose test output
uv run black src/ tests/         # Format code
uv run flake8 src/ tests/        # Lint code
uv run mypy src/dmarc_lens --ignore-missing-imports  # Type checking

# Frontend development
cd web && npm start              # Start dev server
cd web && npm run build          # Production build
cd web && npm test -- --watchAll=false  # Run tests

# Infrastructure
cd infrastructure && npx cdk synth    # Synthesize CloudFormation
cd infrastructure && npx cdk deploy   # Deploy stack
```

## Configuration Files
- `pyproject.toml` — Python project config (dependencies, pytest, mypy, black)
- `web/package.json` — Frontend dependencies and scripts
- `infrastructure/cdk.json` — CDK configuration
- `infrastructure/environments/*.json` — Per-environment settings
- `.github/workflows/deploy.yml` — CI/CD pipeline
