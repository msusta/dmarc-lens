#!/usr/bin/env python3
"""
Deployment verification script for DMARC Lens.

This script verifies that the Lambda functions and infrastructure are ready
for deployment and provides guidance on the deployment process.
"""

import json
import os
import sys
import subprocess
from pathlib import Path


def check_python_version():
    """Check if Python version is 3.8+."""
    
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("✗ Python 3.8+ required. Current version:", f"{version.major}.{version.minor}")
        return False
    
    print(f"✓ Python version: {version.major}.{version.minor}.{version.micro}")
    return True


def check_virtual_environment():
    """Check if virtual environment is active."""
    
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("✓ Virtual environment is active")
        return True
    else:
        print("✗ Virtual environment not active. Run: source venv/bin/activate")
        return False


def check_dependencies():
    """Check if required dependencies are installed."""
    
    try:
        import boto3
        import aws_cdk_lib
        print("✓ Core dependencies installed")
        return True
    except ImportError as e:
        print(f"✗ Missing dependency: {e}")
        return False


def run_tests():
    """Run the test suite."""
    
    print("Running test suite...")
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/", "-v", "--tb=short", "-x"],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            print("✓ All tests passed")
            return True
        else:
            print("✗ Some tests failed:")
            print(result.stdout[-500:])  # Last 500 chars
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ Tests timed out")
        return False
    except Exception as e:
        print(f"✗ Error running tests: {e}")
        return False


def test_lambda_functions():
    """Test Lambda functions locally."""
    
    print("Testing Lambda functions locally...")
    try:
        result = subprocess.run(
            ["python", "scripts/test-deployment.py"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            print("✓ Lambda functions working correctly")
            return True
        else:
            print("✗ Lambda function test failed:")
            print(result.stdout[-500:])
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ Lambda function test timed out")
        return False
    except Exception as e:
        print(f"✗ Error testing Lambda functions: {e}")
        return False


def check_cdk_synthesis():
    """Check if CDK stack can be synthesized."""
    
    print("Testing CDK stack synthesis...")
    try:
        result = subprocess.run(
            ["python", "app.py"],
            cwd="infrastructure",
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print("✓ CDK stack synthesizes successfully")
            return True
        else:
            print("✗ CDK synthesis failed:")
            print(result.stderr[-500:])
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ CDK synthesis timed out")
        return False
    except Exception as e:
        print(f"✗ Error testing CDK synthesis: {e}")
        return False


def check_aws_credentials():
    """Check if AWS credentials are configured."""
    
    try:
        result = subprocess.run(
            ["aws", "sts", "get-caller-identity"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            identity = json.loads(result.stdout)
            print(f"✓ AWS credentials configured")
            print(f"  Account: {identity.get('Account', 'unknown')}")
            print(f"  User/Role: {identity.get('Arn', 'unknown').split('/')[-1]}")
            return True
        else:
            print("✗ AWS credentials not configured")
            print("  Run: aws configure")
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ AWS credential check timed out")
        return False
    except FileNotFoundError:
        print("✗ AWS CLI not installed")
        return False
    except Exception as e:
        print(f"✗ Error checking AWS credentials: {e}")
        return False


def check_cdk_bootstrap():
    """Check if CDK is bootstrapped."""
    
    try:
        result = subprocess.run(
            ["aws", "cloudformation", "describe-stacks", "--stack-name", "CDKToolkit"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print("✓ CDK is bootstrapped")
            return True
        else:
            print("✗ CDK not bootstrapped")
            print("  Run: npx cdk bootstrap")
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ CDK bootstrap check timed out")
        return False
    except Exception as e:
        print("✗ Could not check CDK bootstrap status")
        return False


def print_deployment_instructions():
    """Print deployment instructions."""
    
    print("\n" + "=" * 60)
    print("DEPLOYMENT INSTRUCTIONS")
    print("=" * 60)
    print()
    print("1. Ensure AWS credentials are configured:")
    print("   aws configure")
    print()
    print("2. Bootstrap CDK (if not already done):")
    print("   cd infrastructure")
    print("   npx cdk bootstrap")
    print()
    print("3. Deploy the infrastructure:")
    print("   npx cdk deploy")
    print()
    print("4. Configure SES email receiving:")
    print("   - Verify your domain in SES")
    print("   - Update the receipt rule with your domain")
    print("   - Test with sample DMARC reports")
    print()
    print("5. Monitor the deployment:")
    print("   - Check CloudWatch logs for Lambda functions")
    print("   - Verify DynamoDB tables are created")
    print("   - Test S3 event notifications")


def print_testing_instructions():
    """Print testing instructions."""
    
    print("\n" + "=" * 60)
    print("TESTING INSTRUCTIONS")
    print("=" * 60)
    print()
    print("1. Upload a test email to S3:")
    print("   aws s3 cp tests/fixtures/sample_dmarc_report.xml \\")
    print("     s3://your-bucket/incoming/test-report.xml")
    print()
    print("2. Check Lambda function logs:")
    print("   aws logs tail /aws/lambda/DmarcLensStack-ReportParserFunction")
    print()
    print("3. Verify data in DynamoDB:")
    print("   aws dynamodb scan --table-name dmarc-reports")
    print()
    print("4. Check analysis results:")
    print("   aws dynamodb scan --table-name dmarc-analysis")


def main():
    """Main verification function."""
    
    print("DMARC Lens Deployment Verification")
    print("=" * 60)
    print()
    
    checks = [
        ("Python Version", check_python_version),
        ("Virtual Environment", check_virtual_environment),
        ("Dependencies", check_dependencies),
        ("Test Suite", run_tests),
        ("Lambda Functions", test_lambda_functions),
        ("CDK Synthesis", check_cdk_synthesis),
    ]
    
    # Run basic checks
    passed = 0
    for name, check_func in checks:
        print(f"\nChecking {name}...")
        if check_func():
            passed += 1
        else:
            print(f"  Fix the issue above before proceeding")
    
    print(f"\n{passed}/{len(checks)} basic checks passed")
    
    if passed == len(checks):
        print("\n✓ All basic checks passed!")
        
        # Check AWS-specific requirements
        print("\nChecking AWS deployment requirements...")
        aws_ready = True
        
        if not check_aws_credentials():
            aws_ready = False
        
        if aws_ready and not check_cdk_bootstrap():
            aws_ready = False
        
        if aws_ready:
            print("\n🚀 READY FOR DEPLOYMENT!")
            print("All checks passed. You can now deploy to AWS.")
            print_deployment_instructions()
        else:
            print("\n⚠️  READY FOR LOCAL TESTING")
            print("Basic functionality verified, but AWS setup needed for deployment.")
            print_deployment_instructions()
        
        print_testing_instructions()
        return 0
    else:
        print("\n❌ DEPLOYMENT NOT READY")
        print("Please fix the failed checks above before deploying.")
        return 1


if __name__ == "__main__":
    sys.exit(main())