# DMARC Lens

A serverless, AWS-native platform for analyzing and visualizing DMARC (Domain-based Message Authentication, Reporting & Conformance) email security reports.

## Overview

DMARC Lens helps organizations understand their email authentication posture by automatically ingesting, processing, and visualizing DMARC aggregate reports. The platform provides insights into authentication failures, identifies potential security issues, and offers recommendations for improving email security.

## Features

- **Automated Email Ingestion**: Receives DMARC reports via AWS SES
- **Serverless Processing**: Processes reports using AWS Lambda functions
- **Real-time Analysis**: Analyzes authentication patterns and trends
- **Interactive Dashboard**: Web-based visualization of DMARC data
- **Security Insights**: Identifies suspicious patterns and provides recommendations
- **Scalable Architecture**: Fully serverless and cost-effective

## Architecture

The platform uses a fully serverless architecture built on AWS managed services:

- **AWS SES**: Email ingestion
- **AWS S3**: Raw email and static website storage
- **AWS Lambda**: Report processing and analysis
- **Amazon DynamoDB**: Structured data storage
- **AWS API Gateway**: REST API for web interface
- **Amazon Cognito**: User authentication
- **Amazon CloudFront**: Global content delivery

## Quick Start

### Prerequisites

- Python 3.8 or higher
- AWS CLI configured with appropriate permissions
- Node.js 16+ (for CDK deployment)

### Development Setup

1. Clone the repository:
```bash
git clone https://github.com/msusta/dmarc-lens.git
cd dmarc-lens
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements-dev.txt
```

4. Install CDK dependencies:
```bash
pip install -r requirements-cdk.txt
```

### Infrastructure Deployment

1. Navigate to the infrastructure directory:
```bash
cd infrastructure
```

2. Bootstrap CDK (first time only):
```bash
cdk bootstrap
```

3. Deploy the infrastructure:
```bash
cdk deploy
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/dmarc_lens

# Run property-based tests only
pytest -m property
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/
```

## Project Structure

```
dmarc-lens/
├── src/dmarc_lens/          # Main Python package
│   ├── models/              # Data models
│   ├── parsers/             # DMARC report parsers
│   ├── analyzers/           # Analysis engines
│   ├── lambda_functions/    # AWS Lambda handlers
│   └── utils/               # Utility functions
├── infrastructure/          # AWS CDK infrastructure code
├── tests/                   # Test files
├── docs/                    # Documentation
└── web/                     # React web application (future)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For questions, issues, or contributions, please visit the [GitHub repository](https://github.com/msusta/dmarc-lens).