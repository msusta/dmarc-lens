#!/usr/bin/env python3
"""
AWS CDK application entry point for DMARC Lens infrastructure.
"""

import aws_cdk as cdk
from dmarc_lens_stack import DmarcLensStack

app = cdk.App()

# Get environment from context (defaults to 'dev')
environment = app.node.try_get_context("environment") or "dev"

# Create the main DMARC Lens stack with environment-specific naming
DmarcLensStack(
    app, 
    f"DmarcLensStack-{environment}",
    description=f"DMARC Lens - Serverless DMARC analysis platform ({environment})",
    env=cdk.Environment(
        # Use environment variables or default to current AWS CLI configuration
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region")
    )
)

app.synth()