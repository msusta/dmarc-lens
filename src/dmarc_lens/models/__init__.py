"""
Data models for DMARC reports and analysis results.
"""

from .dmarc_models import (
    ReportMetadata,
    PolicyPublished,
    PolicyEvaluated,
    AuthResult,
    DMARCRecord,
    DMARCReport,
)

__all__ = [
    "ReportMetadata",
    "PolicyPublished",
    "PolicyEvaluated",
    "AuthResult",
    "DMARCRecord",
    "DMARCReport",
]
