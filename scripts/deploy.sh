#!/bin/bash
# Deployment script for DMARC Lens infrastructure

set -e

# Default environment
ENVIRONMENT=${1:-dev}

echo "Deploying DMARC Lens infrastructure for environment: $ENVIRONMENT"

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
    echo "See docs/aws-setup.md for detailed setup instructions"
    exit 1
fi

echo "✓ AWS credentials verified"

# Get AWS account and region info
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region)

echo "  Account: $AWS_ACCOUNT"
echo "  Region: $AWS_REGION"
echo "  Environment: $ENVIRONMENT"

# Resolve the project root directory (parent of scripts/)
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check if virtual environment exists and activate it
if [ ! -d "$PROJECT_ROOT/venv" ]; then
    echo "Error: Virtual environment not found. Please run setup-dev.sh first"
    exit 1
fi

echo "Activating virtual environment..."
source "$PROJECT_ROOT/venv/bin/activate"

# Install CDK dependencies
echo "Installing CDK dependencies..."
pip install -r "$PROJECT_ROOT/requirements-cdk.txt" > /dev/null

# Install Node.js dependencies for CDK
echo "Installing Node.js dependencies..."
npm install > /dev/null

# Check if CDK is bootstrapped
if ! aws cloudformation describe-stacks --stack-name CDKToolkit > /dev/null 2>&1; then
    echo "CDK not bootstrapped. Running bootstrap..."
    npx cdk bootstrap
    echo "✓ CDK bootstrap complete"
else
    echo "✓ CDK already bootstrapped"
fi

# Synthesize the stack with environment context
echo "Synthesizing CDK stack for $ENVIRONMENT environment..."
npx cdk synth --context environment=$ENVIRONMENT

# Show diff if stack already exists
STACK_NAME="DmarcLensStack-$ENVIRONMENT"
if aws cloudformation describe-stacks --stack-name "$STACK_NAME" > /dev/null 2>&1; then
    echo "Stack exists. Showing changes..."
    npx cdk diff --context environment=$ENVIRONMENT
    
    echo ""
    read -p "Do you want to proceed with deployment? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Deployment cancelled"
        exit 0
    fi
fi

# Deploy the stack
echo "Deploying infrastructure..."
npx cdk deploy --context environment=$ENVIRONMENT --require-approval never

echo ""
echo "✓ Infrastructure deployment complete!"
echo ""
echo "Stack Information:"
aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query 'Stacks[0].{Status:StackStatus,Created:CreationTime}' --output table

echo ""
echo "Stack Outputs:"
aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query 'Stacks[0].Outputs[*].{Key:OutputKey,Value:OutputValue}' --output table

echo ""
echo "To view all deployed resources:"
echo "  aws cloudformation describe-stack-resources --stack-name $STACK_NAME"

echo ""
echo "Next steps:"
echo "1. Configure your domain DNS to point to the CloudFront distribution"
echo "2. Update the React app configuration with the API endpoint and Cognito settings"
echo "3. Build and deploy the React app to the S3 bucket using: ./deploy-web.sh $ENVIRONMENT"
echo "4. Configure SES to receive emails at the specified addresses"
