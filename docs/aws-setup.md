# AWS Setup Guide

This guide helps you configure AWS CLI and CDK for DMARC Lens deployment.

## Prerequisites

- AWS Account with appropriate permissions
- AWS CLI installed
- Node.js 16+ installed
- Python 3.8+ installed

## AWS CLI Configuration

1. **Install AWS CLI** (if not already installed):
   ```bash
   # On Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install awscli
   
   # On macOS
   brew install awscli
   
   # Or using pip
   pip install awscli
   ```

2. **Configure AWS credentials**:
   ```bash
   aws configure
   ```
   
   You'll be prompted for:
   - AWS Access Key ID
   - AWS Secret Access Key
   - Default region name (e.g., `us-east-1`)
   - Default output format (recommend `json`)

3. **Verify configuration**:
   ```bash
   aws sts get-caller-identity
   ```

## Required AWS Permissions

Your AWS user/role needs the following permissions for DMARC Lens deployment:

### Core Services
- **S3**: Full access for bucket creation and management
- **Lambda**: Full access for function deployment
- **DynamoDB**: Full access for table creation
- **SES**: Full access for email receiving configuration
- **API Gateway**: Full access for REST API creation
- **Cognito**: Full access for user pool management
- **CloudFront**: Full access for distribution creation

### Infrastructure Management
- **CloudFormation**: Full access for stack management
- **IAM**: Role and policy creation permissions
- **CloudWatch**: Logs and metrics access
- **EventBridge**: Rule creation and management

### Recommended Policy
For development, you can use the `PowerUserAccess` managed policy, or create a custom policy with the specific permissions listed above.

## CDK Bootstrap

Before deploying DMARC Lens, you need to bootstrap CDK in your AWS account:

```bash
cd infrastructure
npx cdk bootstrap
```

This creates the necessary resources for CDK deployments in your account.

## Environment Variables (Optional)

You can set these environment variables for easier deployment:

```bash
export AWS_REGION=us-east-1
export AWS_PROFILE=default
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export CDK_DEFAULT_REGION=$AWS_REGION
```

## Verification

Test your setup by synthesizing the CDK stack:

```bash
cd infrastructure
source ../venv/bin/activate
npx cdk synth
```

If successful, you should see CloudFormation template output without errors.

## Troubleshooting

### Common Issues

1. **Permission Denied**: Ensure your AWS user has sufficient permissions
2. **Region Mismatch**: Verify your AWS CLI region matches your intended deployment region
3. **CDK Version**: Ensure you're using CDK v2 (not v1)

### Getting Help

- Check AWS CLI configuration: `aws configure list`
- Verify credentials: `aws sts get-caller-identity`
- Check CDK version: `npx cdk --version`