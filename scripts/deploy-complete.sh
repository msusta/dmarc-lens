#!/bin/bash
# Complete deployment script for DMARC Lens platform

set -e

# Default environment
ENVIRONMENT=${1:-dev}

echo "=========================================="
echo "DMARC Lens Complete Deployment"
echo "Environment: $ENVIRONMENT"
echo "=========================================="

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|prod)$ ]]; then
    echo "Error: Invalid environment '$ENVIRONMENT'. Must be 'dev' or 'prod'"
    echo "Usage: $0 [dev|prod]"
    exit 1
fi

# Check if AWS CLI is configured
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "Error: AWS CLI is not configured or credentials are invalid"
    echo "Please run 'aws configure' to set up your credentials"
    exit 1
fi

echo "✓ AWS credentials verified"

# Get AWS account and region info
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region)

echo "  Account: $AWS_ACCOUNT"
echo "  Region: $AWS_REGION"
echo "  Environment: $ENVIRONMENT"

# Step 1: Deploy Infrastructure
echo ""
echo "=========================================="
echo "Step 1: Deploying Infrastructure"
echo "=========================================="

cd infrastructure
./deploy.sh $ENVIRONMENT

if [ $? -ne 0 ]; then
    echo "Error: Infrastructure deployment failed"
    exit 1
fi

echo "✓ Infrastructure deployment completed"

# Step 2: Deploy Web Application
echo ""
echo "=========================================="
echo "Step 2: Deploying Web Application"
echo "=========================================="

cd ../scripts
./deploy-web.sh $ENVIRONMENT

if [ $? -ne 0 ]; then
    echo "Error: Web application deployment failed"
    exit 1
fi

echo "✓ Web application deployment completed"

# Step 3: Verify Deployment
echo ""
echo "=========================================="
echo "Step 3: Verifying Deployment"
echo "=========================================="

STACK_NAME="DmarcLensStack-$ENVIRONMENT"

# Get final outputs
WEBSITE_URL=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query 'Stacks[0].Outputs[?OutputKey==`WebsiteUrl`].OutputValue' --output text)
API_ENDPOINT=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' --output text)
SES_EMAILS=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query 'Stacks[0].Outputs[?OutputKey==`SesEmailAddresses`].OutputValue' --output text)

echo "✓ Deployment verification completed"

# Final Summary
echo ""
echo "=========================================="
echo "Deployment Summary"
echo "=========================================="
echo "Environment: $ENVIRONMENT"
echo "AWS Account: $AWS_ACCOUNT"
echo "AWS Region: $AWS_REGION"
echo "Stack Name: $STACK_NAME"
echo ""
echo "Application URL: $WEBSITE_URL"
echo "API Endpoint: $API_ENDPOINT"
echo "SES Email Addresses: $SES_EMAILS"
echo ""
echo "=========================================="
echo "Next Steps"
echo "=========================================="
echo "1. Visit the application URL to verify deployment"
echo "2. Create a user account through the sign-up process"
echo "3. Configure DNS for your domain (if using custom domain)"
echo "4. Configure SES to receive DMARC reports at:"
echo "   $SES_EMAILS"
echo "5. Test the complete workflow with sample DMARC reports"
echo ""
echo "For troubleshooting, check:"
echo "- CloudFormation stack events in AWS Console"
echo "- Lambda function logs in CloudWatch"
echo "- CloudFront distribution status"
echo ""
echo "✓ Complete deployment finished successfully!"