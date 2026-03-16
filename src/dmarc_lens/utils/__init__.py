"""
Utility functions for email processing, logging, and common operations.
"""

from .email_utils import (
    EmailParsingError,
    AttachmentExtractionError,
    parse_email_from_string,
    parse_email_from_bytes,
    parse_email_from_file,
    extract_attachments,
    decompress_attachment,
    extract_dmarc_reports,
    get_email_metadata,
    validate_email_structure,
)

from .xml_utils import (
    XMLValidationError,
    XMLParsingError,
    parse_xml_string,
    validate_dmarc_xml_structure,
    extract_xml_text,
    extract_xml_int,
    extract_xml_timestamp,
    validate_xml_encoding,
    get_xml_statistics,
)

from .logging_utils import (
    DMARCLensFormatter,
    ErrorHandler,
    setup_logging,
    setup_lambda_logging,
    create_context_logger,
    log_performance,
    get_error_handler,
    set_error_handler,
)

__all__ = [
    # Email utilities
    "EmailParsingError",
    "AttachmentExtractionError",
    "parse_email_from_string",
    "parse_email_from_bytes",
    "parse_email_from_file",
    "extract_attachments",
    "decompress_attachment",
    "extract_dmarc_reports",
    "get_email_metadata",
    "validate_email_structure",
    # XML utilities
    "XMLValidationError",
    "XMLParsingError",
    "parse_xml_string",
    "validate_dmarc_xml_structure",
    "extract_xml_text",
    "extract_xml_int",
    "extract_xml_timestamp",
    "validate_xml_encoding",
    "get_xml_statistics",
    # Logging utilities
    "DMARCLensFormatter",
    "ErrorHandler",
    "setup_logging",
    "setup_lambda_logging",
    "create_context_logger",
    "log_performance",
    "get_error_handler",
    "set_error_handler",
]
