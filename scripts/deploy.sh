#!/bin/bash
# Deployment script for DMARC Lens infrastructure

set -e

echo "Deploying DMARC Lens infrastructure..."

# Check if AWS CLI is configured
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "Error: AWS CLI is not configured or credentials are invalid"
    echo "Please run 'aws configure' to set up your credentials"
    echo "See docs/aws-setup.md for detailed setup instructions"
    exit 1
fi

echo "✓ AWS credentials verified"

# Get AWS account and region info
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region)

echo "  Account: $AWS_ACCOUNT"
echo "  Region: $AWS_REGION"

# Check if virtual environment exists and activate it
if [ ! -d "../venv" ]; then
    echo "Error: Virtual environment not found. Please run setup-dev.sh first"
    exit 1
fi

echo "Activating virtual environment..."
source ../venv/bin/activate

# Check if CDK is bootstrapped
if ! aws cloudformation describe-stacks --stack-name CDKToolkit > /dev/null 2>&1; then
    echo "CDK not bootstrapped. Running bootstrap..."
    npx cdk bootstrap
    echo "✓ CDK bootstrap complete"
else
    echo "✓ CDK already bootstrapped"
fi

# Synthesize the stack
echo "Synthesizing CDK stack..."
npx cdk synth > /dev/null

# Deploy the stack
echo "Deploying infrastructure..."
npx cdk deploy --require-approval never

echo ""
echo "✓ Infrastructure deployment complete!"
echo ""
echo "Stack Information:"
aws cloudformation describe-stacks --stack-name DmarcLensStack --query 'Stacks[0].{Status:StackStatus,Created:CreationTime}' --output table

echo ""
echo "To view all deployed resources:"
echo "  aws cloudformation describe-stack-resources --stack-name DmarcLensStack"