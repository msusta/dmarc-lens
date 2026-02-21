#!/bin/bash
# Web application deployment script for DMARC Lens

set -e

# Default environment
ENVIRONMENT=${1:-dev}

echo "Deploying DMARC Lens web application for environment: $ENVIRONMENT"

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

# Get stack outputs
STACK_NAME="DmarcLensStack-$ENVIRONMENT"

echo "Getting stack outputs..."
if ! aws cloudformation describe-stacks --stack-name "$STACK_NAME" > /dev/null 2>&1; then
    echo "Error: Stack '$STACK_NAME' not found. Please deploy infrastructure first:"
    echo "  cd infrastructure && ./deploy.sh $ENVIRONMENT"
    exit 1
fi

# Extract stack outputs
API_ENDPOINT=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' --output text)
USER_POOL_ID=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' --output text)
USER_POOL_CLIENT_ID=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query 'Stacks[0].Outputs[?OutputKey==`UserPoolClientId`].OutputValue' --output text)
IDENTITY_POOL_ID=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query 'Stacks[0].Outputs[?OutputKey==`IdentityPoolId`].OutputValue' --output text)
WEB_BUCKET=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query 'Stacks[0].Outputs[?OutputKey==`WebHostingBucketName`].OutputValue' --output text)
CLOUDFRONT_ID=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' --output text)
WEBSITE_URL=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query 'Stacks[0].Outputs[?OutputKey==`WebsiteUrl`].OutputValue' --output text)

# Validate required outputs
if [[ -z "$API_ENDPOINT" || -z "$USER_POOL_ID" || -z "$USER_POOL_CLIENT_ID" || -z "$WEB_BUCKET" || -z "$CLOUDFRONT_ID" ]]; then
    echo "Error: Missing required stack outputs. Please ensure infrastructure is properly deployed."
    echo "API_ENDPOINT: $API_ENDPOINT"
    echo "USER_POOL_ID: $USER_POOL_ID"
    echo "USER_POOL_CLIENT_ID: $USER_POOL_CLIENT_ID"
    echo "WEB_BUCKET: $WEB_BUCKET"
    echo "CLOUDFRONT_ID: $CLOUDFRONT_ID"
    exit 1
fi

echo "✓ Stack outputs retrieved"
echo "  API Endpoint: $API_ENDPOINT"
echo "  User Pool ID: $USER_POOL_ID"
echo "  Web Bucket: $WEB_BUCKET"
echo "  CloudFront ID: $CLOUDFRONT_ID"
echo "  Website URL: $WEBSITE_URL"

# Navigate to web directory
cd ../web

# Check if Node.js dependencies are installed
if [ ! -d "node_modules" ]; then
    echo "Installing Node.js dependencies..."
    npm install
else
    echo "✓ Node.js dependencies found"
fi

# Generate AWS configuration file
echo "Generating AWS configuration..."
cat > src/aws-exports.ts << EOF
// Auto-generated AWS configuration for environment: $ENVIRONMENT
// Generated on: $(date)

const awsconfig = {
  Auth: {
    region: '$AWS_REGION',
    userPoolId: '$USER_POOL_ID',
    userPoolWebClientId: '$USER_POOL_CLIENT_ID',
    identityPoolId: '$IDENTITY_POOL_ID',
    mandatorySignIn: true,
    authenticationFlowType: 'USER_SRP_AUTH'
  },
  API: {
    endpoints: [
      {
        name: 'DmarcLensApi',
        endpoint: '$API_ENDPOINT',
        region: '$AWS_REGION'
      }
    ]
  }
};

export default awsconfig;
EOF

echo "✓ AWS configuration generated"

# Build the React application
echo "Building React application..."
REACT_APP_API_ENDPOINT="$API_ENDPOINT" \
REACT_APP_USER_POOL_ID="$USER_POOL_ID" \
REACT_APP_USER_POOL_CLIENT_ID="$USER_POOL_CLIENT_ID" \
REACT_APP_IDENTITY_POOL_ID="$IDENTITY_POOL_ID" \
REACT_APP_REGION="$AWS_REGION" \
REACT_APP_ENVIRONMENT="$ENVIRONMENT" \
npm run build

echo "✓ React application built"

# Deploy to S3
echo "Deploying to S3 bucket: $WEB_BUCKET"
aws s3 sync build/ s3://$WEB_BUCKET --delete --cache-control "public, max-age=31536000" --exclude "*.html" --exclude "service-worker.js" --exclude "manifest.json"

# Deploy HTML files with shorter cache
aws s3 sync build/ s3://$WEB_BUCKET --delete --cache-control "public, max-age=300" --include "*.html" --include "service-worker.js" --include "manifest.json"

echo "✓ Files deployed to S3"

# Invalidate CloudFront cache
echo "Invalidating CloudFront cache..."
INVALIDATION_ID=$(aws cloudfront create-invalidation --distribution-id "$CLOUDFRONT_ID" --paths "/*" --query 'Invalidation.Id' --output text)

echo "✓ CloudFront invalidation created: $INVALIDATION_ID"

# Wait for invalidation to complete (optional)
echo "Waiting for CloudFront invalidation to complete..."
aws cloudfront wait invalidation-completed --distribution-id "$CLOUDFRONT_ID" --id "$INVALIDATION_ID"

echo ""
echo "✓ Web application deployment complete!"
echo ""
echo "Application URL: $WEBSITE_URL"
echo ""
echo "Next steps:"
echo "1. Visit the application URL to verify deployment"
echo "2. Create a user account through the sign-up process"
echo "3. Configure SES to receive DMARC reports at the configured email addresses"
echo "4. Test the complete workflow with sample DMARC reports"