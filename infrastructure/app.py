#!/usr/bin/env python3
"""
AWS CDK application entry point for DMARC Lens infrastructure.
"""

import aws_cdk as cdk
from dmarc_lens_stack import DmarcLensStack

app = cdk.App()

# Create the main DMARC Lens stack
DmarcLensStack(
    app, 
    "DmarcLensStack",
    description="DMARC Lens - Serverless DMARC analysis platform"
)

app.synth()