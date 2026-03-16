"""
Lambda functions for DMARC Lens.

This package contains AWS Lambda functions for processing DMARC reports
and performing analysis on the collected data.
"""

from .report_parser import lambda_handler as report_parser_handler
from .analysis_engine import lambda_handler as analysis_engine_handler

__all__ = ["report_parser_handler", "analysis_engine_handler"]
