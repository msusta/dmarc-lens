# DMARC Lens Deployment Guide

This guide covers the complete deployment of the DMARC Lens platform to AWS, including both infrastructure and web application components.

## Prerequisites

Before deploying, ensure you have:

1. **AWS CLI v2** installed and configured
2. **Node.js 18+** and npm installed
3. **Python 3.11+** installed
4. **AWS CDK v2** installed globally: `npm install -g aws-cdk`
5. **Valid AWS credentials** configured with appropriate permissions

### Required AWS Permissions

Your AWS credentials need the following permissions:
- CloudFormation full access
- S3 full access
- Lambda full access
- DynamoDB full access
- API Gateway full access
- Cognito full access
- CloudFront full access
- SES full access
- IAM role creation and management
- CloudWatch Logs access

## Environment Configuration

The deployment supports two environments: `dev` and `prod`. Environment-specific configurations are stored in:

- `infrastructure/environments/dev.json` - Development environment settings
- `infrastructure/environments/prod.json` - Production environment settings

### Environment Configuration Format

```json
{
  "environment": "prod",
  "domain": {
    "enabled": true,
    "domain_name": "dmarc-lens.yourdomain.com",
    "certificate_arn": "arn:aws:acm:us-east-1:account:certificate/cert-id"
  },
  "ses": {
    "email_addresses": ["dmarc-reports@yourdomain.com"]
  },
  "cognito": {
    "callback_urls": ["https://dmarc-lens.yourdomain.com"],
    "logout_urls": ["https://dmarc-lens.yourdomain.com"]
  },
  "api": {
    "cors_origins": ["https://dmarc-lens.yourdomain.com"]
  },
  "monitoring": {
    "enable_detailed_monitoring": true,
    "log_retention_days": 30
  },
  "tags": {
    "Environment": "prod",
    "Project": "dmarc-lens"
  }
}
```

## Deployment Methods

### Method 1: Complete Automated Deployment (Recommended)

Deploy both infrastructure and web application in one command:

```bash
# Deploy to development environment
./scripts/deploy-complete.sh dev

# Deploy to production environment
./scripts/deploy-complete.sh prod
```

This script will:
1. Deploy the AWS infrastructure using CDK
2. Build and deploy the React web application
3. Configure CloudFront cache invalidation
4. Provide deployment summary and next steps

### Method 2: Step-by-Step Deployment

#### Step 1: Deploy Infrastructure

```bash
cd infrastructure

# Install dependencies
npm install
pip install -r requirements-cdk.txt

# Bootstrap CDK (only needed once per account/region)
npx cdk bootstrap --context environment=dev

# Deploy infrastructure
npx cdk deploy --context environment=dev --require-approval never
```

#### Step 2: Deploy Web Application

```bash
# Deploy web app to development
./scripts/deploy-web.sh dev

# Deploy web app to production
./scripts/deploy-web.sh prod
```

### Method 3: CI/CD Pipeline (GitHub Actions)

The repository includes GitHub Actions workflows for automated deployment:

- **Development**: Triggered on push to `develop` branch
- **Production**: Triggered on push to `main` branch

#### Required GitHub Secrets

For development environment:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

For production environment:
- `AWS_ACCESS_KEY_ID_PROD`
- `AWS_SECRET_ACCESS_KEY_PROD`

## Infrastructure Components

The deployment creates the following AWS resources:

### Core Infrastructure
- **S3 Buckets**: Raw email storage and web hosting
- **DynamoDB Tables**: DMARC reports and analysis data
- **Lambda Functions**: Email processing, analysis engine, API, and authentication
- **API Gateway**: HTTP API with JWT authentication
- **Cognito**: User pools and identity pools for authentication

### Email Processing
- **SES**: Email receiving configuration with receipt rules
- **S3 Event Notifications**: Trigger Lambda processing on new emails

### Web Application
- **CloudFront**: Global CDN for web application delivery
- **S3 Static Website**: React application hosting
- **Custom Domain**: SSL certificate and domain configuration (optional)

### Monitoring and Logging
- **CloudWatch**: Logs and metrics for all Lambda functions
- **CloudWatch Alarms**: Error rate and performance monitoring (production)
- **SNS**: Error notifications (production)

## Custom Domain Setup (Optional)

To use a custom domain with SSL certificate:

1. **Request SSL Certificate** in AWS Certificate Manager (ACM)
   - Must be in `us-east-1` region for CloudFront
   - Validate domain ownership

2. **Update Environment Configuration**
   ```json
   {
     "domain": {
       "enabled": true,
       "domain_name": "dmarc-lens.yourdomain.com",
       "certificate_arn": "arn:aws:acm:us-east-1:account:certificate/cert-id"
     }
   }
   ```

3. **Redeploy Infrastructure**
   ```bash
   ./scripts/deploy-complete.sh prod
   ```

4. **Update DNS**
   - Create CNAME record pointing to CloudFront distribution
   - Or use Route 53 alias record

## Environment-Specific Features

### Development Environment
- Shorter data retention periods
- Debug logging enabled
- Local development CORS origins
- Destroy removal policy for cost optimization
- Reduced lifecycle policies

### Production Environment
- Extended data retention periods
- Info-level logging
- Production domain CORS origins
- Retain removal policy for data protection
- Point-in-time recovery enabled
- Enhanced monitoring and alerting

## Post-Deployment Configuration

### 1. SES Email Configuration

Configure SES to receive DMARC reports:

```bash
# Get SES email addresses from stack outputs
aws cloudformation describe-stacks \
  --stack-name DmarcLensStack-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`SesEmailAddresses`].OutputValue' \
  --output text
```

Set up your domain's DMARC policy to send reports to these addresses:

```dns
_dmarc.yourdomain.com. IN TXT "v=DMARC1; p=quarantine; rua=mailto:dmarc-reports@ses.yourdomain.com"
```

### 2. User Account Creation

1. Visit the deployed application URL
2. Click "Sign Up" to create a new account
3. Verify your email address
4. Sign in to access the dashboard

### 3. DNS Configuration (Custom Domain)

If using a custom domain, update your DNS:

```dns
dmarc-lens.yourdomain.com. IN CNAME d1234567890.cloudfront.net.
```

## Monitoring and Troubleshooting

### CloudWatch Logs

Monitor Lambda function logs:
- `/aws/lambda/DmarcLensStack-{env}-ReportParserFunction`
- `/aws/lambda/DmarcLensStack-{env}-AnalysisEngineFunction`
- `/aws/lambda/DmarcLensStack-{env}-DataApiFunction`
- `/aws/lambda/DmarcLensStack-{env}-AuthFunction`

### Common Issues

1. **CloudFront Distribution Not Working**
   - Wait 15-20 minutes for initial distribution deployment
   - Check Origin Access Control configuration
   - Verify S3 bucket policy allows CloudFront access

2. **API Calls Failing**
   - Verify API Gateway endpoint in aws-exports.ts
   - Check CORS configuration
   - Ensure Cognito authentication is working

3. **Authentication Issues**
   - Verify Cognito User Pool and Client IDs
   - Check redirect URLs match your domain
   - Ensure JWT tokens are being sent with API requests

4. **SES Email Processing**
   - Verify SES receipt rules are active
   - Check S3 bucket permissions for SES
   - Monitor Lambda function logs for processing errors

### Useful Commands

```bash
# Check stack status
aws cloudformation describe-stacks --stack-name DmarcLensStack-prod

# View stack outputs
aws cloudformation describe-stacks \
  --stack-name DmarcLensStack-prod \
  --query 'Stacks[0].Outputs[*].{Key:OutputKey,Value:OutputValue}' \
  --output table

# Create CloudFront invalidation
aws cloudfront create-invalidation \
  --distribution-id DIST_ID \
  --paths "/*"

# Check Lambda function logs
aws logs tail /aws/lambda/DmarcLensStack-prod-ReportParserFunction --follow

# List S3 bucket contents
aws s3 ls s3://dmarc-lens-web-prod-account-region --recursive
```

## Cost Optimization

### Development Environment
- Uses shorter retention periods
- Destroy removal policies
- Reduced storage classes
- Minimal monitoring

### Production Environment
- Lifecycle policies for S3 storage optimization
- CloudFront price class 100 (North America and Europe)
- DynamoDB on-demand billing
- Lambda provisioned concurrency only when needed

### Estimated Monthly Costs

**Development Environment**: $5-15/month
- Minimal data storage
- Low request volume
- Basic monitoring

**Production Environment**: $20-100/month (depending on volume)
- Includes data retention
- Enhanced monitoring
- Higher request volume
- CloudFront distribution

## Security Considerations

### Infrastructure Security
- All S3 buckets are private with CloudFront-only access
- DynamoDB tables use AWS managed encryption
- Lambda functions use least-privilege IAM roles
- API Gateway requires JWT authentication
- VPC endpoints for enhanced security (optional)

### Application Security
- HTTPS enforced everywhere
- JWT token validation
- CORS properly configured
- Security headers in CloudFront
- Input validation in Lambda functions

### Data Protection
- Encryption at rest for all data stores
- Encryption in transit for all communications
- Point-in-time recovery for production databases
- Automated backups and retention policies

## Disaster Recovery

### Backup Strategy
- DynamoDB point-in-time recovery (production)
- S3 versioning and lifecycle policies
- CloudFormation templates in version control
- Automated infrastructure deployment

### Recovery Procedures
1. **Infrastructure Recovery**: Redeploy using CDK templates
2. **Data Recovery**: Restore from DynamoDB point-in-time recovery
3. **Application Recovery**: Redeploy web application from CI/CD pipeline

## Next Steps

After successful deployment:

1. **Test the Complete Workflow**
   - Send test DMARC reports to configured email addresses
   - Verify email processing and data storage
   - Check dashboard displays and analytics

2. **Configure Monitoring**
   - Set up CloudWatch alarms for error rates
   - Configure SNS notifications for critical issues
   - Monitor costs and usage patterns

3. **Scale and Optimize**
   - Adjust Lambda memory and timeout settings based on usage
   - Optimize DynamoDB read/write capacity if needed
   - Consider additional CloudFront edge locations for global users

4. **Security Hardening**
   - Review and tighten IAM policies
   - Enable AWS Config for compliance monitoring
   - Set up AWS GuardDuty for threat detection