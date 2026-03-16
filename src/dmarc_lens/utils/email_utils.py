"""
Email processing utilities for DMARC Lens.

This module provides functions for parsing email messages and extracting
DMARC report attachments from email content.
"""

import email
import gzip
import zipfile
import io
import logging
from email.message import EmailMessage
from typing import List, Tuple, Optional, BinaryIO
from pathlib import Path

logger = logging.getLogger(__name__)


class EmailParsingError(Exception):
    """Exception raised when email parsing fails."""

    pass


class AttachmentExtractionError(Exception):
    """Exception raised when attachment extraction fails."""

    pass


def parse_email_from_string(email_content: str) -> EmailMessage:
    """
    Parse an email message from string content.

    Args:
        email_content: Raw email content as string

    Returns:
        Parsed EmailMessage object

    Raises:
        EmailParsingError: If email parsing fails
    """
    try:
        return email.message_from_string(email_content)
    except Exception as e:
        logger.error(f"Failed to parse email from string: {e}")
        raise EmailParsingError(f"Email parsing failed: {e}") from e


def parse_email_from_bytes(email_content: bytes) -> EmailMessage:
    """
    Parse an email message from bytes content.

    Args:
        email_content: Raw email content as bytes

    Returns:
        Parsed EmailMessage object

    Raises:
        EmailParsingError: If email parsing fails
    """
    try:
        return email.message_from_bytes(email_content)
    except Exception as e:
        logger.error(f"Failed to parse email from bytes: {e}")
        raise EmailParsingError(f"Email parsing failed: {e}") from e


def parse_email_from_file(file_path: Path) -> EmailMessage:
    """
    Parse an email message from a file.

    Args:
        file_path: Path to the email file

    Returns:
        Parsed EmailMessage object

    Raises:
        EmailParsingError: If email parsing fails
        FileNotFoundError: If file doesn't exist
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return email.message_from_file(f)
    except FileNotFoundError:
        logger.error(f"Email file not found: {file_path}")
        raise
    except Exception as e:
        logger.error(f"Failed to parse email from file {file_path}: {e}")
        raise EmailParsingError(f"Email parsing failed: {e}") from e


def extract_attachments(message: EmailMessage) -> List[Tuple[str, bytes, str]]:
    """
    Extract all attachments from an email message.

    Args:
        message: Parsed EmailMessage object

    Returns:
        List of tuples containing (filename, content, content_type)

    Raises:
        AttachmentExtractionError: If attachment extraction fails
    """
    attachments = []

    try:
        for part in message.walk():
            # Skip multipart containers
            if part.get_content_maintype() == "multipart":
                continue

            # Skip text parts that are not attachments
            if part.get_content_disposition() is None:
                continue

            filename = part.get_filename()
            if filename is None:
                # Generate a default filename if none provided
                content_type = part.get_content_type()
                if "xml" in content_type:
                    filename = "dmarc_report.xml"
                elif "zip" in content_type:
                    filename = "dmarc_report.zip"
                elif "gzip" in content_type:
                    filename = "dmarc_report.gz"
                else:
                    filename = "attachment"

            # Get the attachment content
            content = part.get_payload(decode=True)
            if content is None:
                logger.warning(f"Could not decode attachment: {filename}")
                continue

            content_type = part.get_content_type()
            attachments.append((filename, content, content_type))

        logger.info(f"Extracted {len(attachments)} attachments from email")
        return attachments

    except Exception as e:
        logger.error(f"Failed to extract attachments: {e}")
        raise AttachmentExtractionError(f"Attachment extraction failed: {e}") from e


def decompress_attachment(content: bytes, filename: str) -> bytes:
    """
    Decompress attachment content if it's compressed.

    Args:
        content: Raw attachment content
        filename: Original filename to determine compression type

    Returns:
        Decompressed content

    Raises:
        AttachmentExtractionError: If decompression fails
    """
    try:
        # Handle gzip files
        if filename.endswith(".gz") or filename.endswith(".gzip"):
            return gzip.decompress(content)

        # Handle zip files
        elif filename.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(content)) as zip_file:
                # Get the first file in the zip
                names = zip_file.namelist()
                if not names:
                    raise AttachmentExtractionError("Zip file is empty")

                # Look for XML files first, otherwise take the first file
                xml_files = [name for name in names if name.endswith(".xml")]
                target_file = xml_files[0] if xml_files else names[0]

                return zip_file.read(target_file)

        # Return content as-is if not compressed
        else:
            return content

    except Exception as e:
        logger.error(f"Failed to decompress attachment {filename}: {e}")
        raise AttachmentExtractionError(f"Decompression failed: {e}") from e


def extract_dmarc_reports(message: EmailMessage) -> List[Tuple[str, str]]:
    """
    Extract DMARC report XML content from email attachments.

    Args:
        message: Parsed EmailMessage object

    Returns:
        List of tuples containing (filename, xml_content)

    Raises:
        AttachmentExtractionError: If extraction fails
    """
    dmarc_reports = []

    try:
        attachments = extract_attachments(message)

        for filename, content, content_type in attachments:
            # Skip non-DMARC attachments based on content type and filename
            if not _is_dmarc_attachment(filename, content_type):
                logger.debug(f"Skipping non-DMARC attachment: {filename}")
                continue

            # Decompress if needed
            decompressed_content = decompress_attachment(content, filename)

            # Convert to string
            try:
                xml_content = decompressed_content.decode("utf-8")
            except UnicodeDecodeError:
                # Try other encodings
                for encoding in ["latin-1", "cp1252"]:
                    try:
                        xml_content = decompressed_content.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    raise AttachmentExtractionError(
                        f"Could not decode XML content in {filename}"
                    )

            dmarc_reports.append((filename, xml_content))

        logger.info(f"Extracted {len(dmarc_reports)} DMARC reports from email")
        return dmarc_reports

    except Exception as e:
        logger.error(f"Failed to extract DMARC reports: {e}")
        raise AttachmentExtractionError(f"DMARC report extraction failed: {e}") from e


def _is_dmarc_attachment(filename: str, content_type: str) -> bool:
    """
    Determine if an attachment is likely a DMARC report.

    Args:
        filename: Attachment filename
        content_type: MIME content type

    Returns:
        True if attachment appears to be a DMARC report
    """
    # Check filename patterns
    filename_lower = filename.lower()
    dmarc_patterns = ["dmarc", "aggregate", "report", ".xml", ".zip", ".gz"]

    filename_match = any(pattern in filename_lower for pattern in dmarc_patterns)

    # Check content type
    content_type_lower = content_type.lower()
    valid_content_types = [
        "application/xml",
        "text/xml",
        "application/zip",
        "application/gzip",
        "application/x-gzip",
    ]

    content_type_match = any(ct in content_type_lower for ct in valid_content_types)

    return filename_match or content_type_match


def get_email_metadata(message: EmailMessage) -> dict:
    """
    Extract metadata from an email message.

    Args:
        message: Parsed EmailMessage object

    Returns:
        Dictionary containing email metadata
    """
    return {
        "from": message.get("From", ""),
        "to": message.get("To", ""),
        "subject": message.get("Subject", ""),
        "date": message.get("Date", ""),
        "message_id": message.get("Message-ID", ""),
        "return_path": message.get("Return-Path", ""),
        "received": message.get_all("Received", []),
    }


def validate_email_structure(message: EmailMessage) -> bool:
    """
    Validate that an email has the basic structure expected for DMARC reports.

    Args:
        message: Parsed EmailMessage object

    Returns:
        True if email structure is valid for DMARC processing
    """
    try:
        # Check for required headers
        required_headers = ["From", "Subject", "Date"]
        for header in required_headers:
            if not message.get(header):
                logger.warning(f"Missing required header: {header}")
                return False

        # Check if email has attachments
        has_attachments = False
        for part in message.walk():
            if part.get_content_disposition() is not None:
                has_attachments = True
                break

        if not has_attachments:
            logger.warning("Email has no attachments")
            return False

        return True

    except Exception as e:
        logger.error(f"Email structure validation failed: {e}")
        return False
