"""
XML processing utilities for DMARC Lens.

This module provides functions for validating and processing DMARC XML reports
against the DMARC aggregate report schema.
"""

import xml.etree.ElementTree as ET
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import re

logger = logging.getLogger(__name__)


class XMLValidationError(Exception):
    """Exception raised when XML validation fails."""

    pass


class XMLParsingError(Exception):
    """Exception raised when XML parsing fails."""

    pass


# DMARC XML Schema validation patterns
DMARC_SCHEMA_PATTERNS = {
    "report_metadata": {
        "required_elements": ["org_name", "email", "report_id", "date_range"],
        "date_range_elements": ["begin", "end"],
    },
    "policy_published": {
        "required_elements": ["domain", "p"],
        "optional_elements": ["sp", "pct", "adkim", "aspf"],
        "valid_policies": ["none", "quarantine", "reject"],
        "valid_alignment": ["r", "s"],
    },
    "record": {
        "required_elements": ["row", "identifiers"],
        "row_elements": ["source_ip", "count", "policy_evaluated"],
        "policy_evaluated_elements": ["disposition", "dkim", "spf"],
        "identifiers_elements": ["header_from"],
    },
}


def parse_xml_string(xml_content: str) -> ET.Element:
    """
    Parse XML content from string.

    Args:
        xml_content: XML content as string

    Returns:
        Parsed XML root element

    Raises:
        XMLParsingError: If XML parsing fails
    """
    try:
        # Remove BOM if present
        if xml_content.startswith("\ufeff"):
            xml_content = xml_content[1:]

        # Parse the XML
        root = ET.fromstring(xml_content)
        logger.debug(f"Successfully parsed XML with root element: {root.tag}")
        return root

    except ET.ParseError as e:
        logger.error(f"XML parsing failed: {e}")
        raise XMLParsingError(f"Invalid XML format: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error parsing XML: {e}")
        raise XMLParsingError(f"XML parsing failed: {e}") from e


def validate_dmarc_xml_structure(root: ET.Element) -> bool:
    """
    Validate XML structure against DMARC aggregate report schema.

    Args:
        root: Parsed XML root element

    Returns:
        True if XML structure is valid

    Raises:
        XMLValidationError: If validation fails
    """
    try:
        # Check root element
        if root.tag != "feedback":
            raise XMLValidationError(
                f"Invalid root element: {root.tag}. Expected 'feedback'"
            )

        # Validate report metadata
        _validate_report_metadata(root)

        # Validate policy published
        _validate_policy_published(root)

        # Validate records
        _validate_records(root)

        logger.info("DMARC XML structure validation passed")
        return True

    except XMLValidationError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during XML validation: {e}")
        raise XMLValidationError(f"XML validation failed: {e}") from e


def _validate_report_metadata(root: ET.Element) -> None:
    """Validate report metadata section."""
    metadata = root.find("report_metadata")
    if metadata is None:
        raise XMLValidationError("Missing report_metadata element")

    schema = DMARC_SCHEMA_PATTERNS["report_metadata"]

    # Check required elements
    for element in schema["required_elements"]:
        if element == "date_range":
            date_range = metadata.find("date_range")
            if date_range is None:
                raise XMLValidationError("Missing date_range element")

            # Check date range sub-elements
            for date_element in schema["date_range_elements"]:
                if date_range.find(date_element) is None:
                    raise XMLValidationError(
                        f"Missing date_range/{date_element} element"
                    )

                # Validate timestamp format
                timestamp_text = date_range.find(date_element).text
                if not timestamp_text or not timestamp_text.isdigit():
                    raise XMLValidationError(
                        f"Invalid timestamp in date_range/{date_element}"
                    )
        else:
            element_node = metadata.find(element)
            if element_node is None or not element_node.text:
                raise XMLValidationError(f"Missing or empty {element} element")


def _validate_policy_published(root: ET.Element) -> None:
    """Validate policy published section."""
    policy = root.find("policy_published")
    if policy is None:
        raise XMLValidationError("Missing policy_published element")

    schema = DMARC_SCHEMA_PATTERNS["policy_published"]

    # Check required elements
    for element in schema["required_elements"]:
        element_node = policy.find(element)
        if element_node is None or not element_node.text:
            raise XMLValidationError(
                f"Missing or empty policy_published/{element} element"
            )

        # Validate policy values
        if element == "p":
            if element_node.text not in schema["valid_policies"]:
                raise XMLValidationError(f"Invalid policy value: {element_node.text}")

    # Check optional elements
    for element in schema.get("optional_elements", []):
        element_node = policy.find(element)
        if element_node is not None and element_node.text:
            if element in ["sp"] and element_node.text not in schema["valid_policies"]:
                raise XMLValidationError(
                    f"Invalid subdomain policy value: {element_node.text}"
                )
            elif (
                element in ["adkim", "aspf"]
                and element_node.text not in schema["valid_alignment"]
            ):
                raise XMLValidationError(f"Invalid alignment mode: {element_node.text}")
            elif element == "pct":
                try:
                    pct_value = int(element_node.text)
                    if not 0 <= pct_value <= 100:
                        raise XMLValidationError(
                            f"Invalid percentage value: {pct_value}"
                        )
                except ValueError:
                    raise XMLValidationError(
                        f"Invalid percentage format: {element_node.text}"
                    )


def _validate_records(root: ET.Element) -> None:
    """Validate record sections."""
    records = root.findall("record")
    if not records:
        raise XMLValidationError("No record elements found")

    schema = DMARC_SCHEMA_PATTERNS["record"]

    for i, record in enumerate(records):
        # Check required elements
        for element in schema["required_elements"]:
            element_node = record.find(element)
            if element_node is None:
                raise XMLValidationError(f"Missing {element} element in record {i}")

        # Validate row section
        row = record.find("row")
        for row_element in schema["row_elements"]:
            if row_element == "policy_evaluated":
                policy_eval = row.find("policy_evaluated")
                if policy_eval is None:
                    raise XMLValidationError(f"Missing policy_evaluated in record {i}")

                # Check policy evaluated sub-elements
                for pe_element in schema["policy_evaluated_elements"]:
                    pe_node = policy_eval.find(pe_element)
                    if pe_node is None or not pe_node.text:
                        raise XMLValidationError(
                            f"Missing policy_evaluated/{pe_element} in record {i}"
                        )
            else:
                row_node = row.find(row_element)
                if row_node is None or not row_node.text:
                    raise XMLValidationError(f"Missing row/{row_element} in record {i}")

                # Validate specific formats
                if row_element == "source_ip":
                    if not _is_valid_ip(row_node.text):
                        raise XMLValidationError(
                            f"Invalid IP address in record {i}: {row_node.text}"
                        )
                elif row_element == "count":
                    try:
                        count_value = int(row_node.text)
                        if count_value <= 0:
                            raise XMLValidationError(
                                f"Invalid count value in record {i}: {count_value}"
                            )
                    except ValueError:
                        raise XMLValidationError(
                            f"Invalid count format in record {i}: {row_node.text}"
                        )

        # Validate identifiers section
        identifiers = record.find("identifiers")
        for id_element in schema["identifiers_elements"]:
            id_node = identifiers.find(id_element)
            if id_node is None or not id_node.text:
                raise XMLValidationError(
                    f"Missing identifiers/{id_element} in record {i}"
                )


def _is_valid_ip(ip_string: str) -> bool:
    """Validate IP address format (IPv4 or IPv6)."""
    # IPv4 pattern
    ipv4_pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
    if re.match(ipv4_pattern, ip_string):
        parts = ip_string.split(".")
        return all(0 <= int(part) <= 255 for part in parts)

    # IPv6 pattern (simplified)
    ipv6_pattern = r"^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$|^::1$|^::$"
    if re.match(ipv6_pattern, ip_string):
        return True

    # IPv6 compressed format (basic check)
    if "::" in ip_string and ip_string.count("::") == 1:
        return True

    return False


def extract_xml_text(element: ET.Element, path: str, default: str = "") -> str:
    """
    Extract text content from XML element by path.

    Args:
        element: XML element to search in
        path: XPath-like path to the target element
        default: Default value if element not found

    Returns:
        Text content of the element or default value
    """
    try:
        target = element.find(path)
        if target is not None and target.text:
            return target.text.strip()
        return default
    except Exception as e:
        logger.warning(f"Failed to extract text from path {path}: {e}")
        return default


def extract_xml_int(element: ET.Element, path: str, default: int = 0) -> int:
    """
    Extract integer content from XML element by path.

    Args:
        element: XML element to search in
        path: XPath-like path to the target element
        default: Default value if element not found or invalid

    Returns:
        Integer value of the element or default value
    """
    try:
        text_value = extract_xml_text(element, path)
        if text_value:
            return int(text_value)
        return default
    except ValueError as e:
        logger.warning(f"Failed to convert {path} to integer: {e}")
        return default


def extract_xml_timestamp(element: ET.Element, path: str) -> Optional[datetime]:
    """
    Extract timestamp from XML element and convert to datetime.

    Args:
        element: XML element to search in
        path: XPath-like path to the target element

    Returns:
        Datetime object or None if conversion fails
    """
    try:
        timestamp_str = extract_xml_text(element, path)
        if timestamp_str:
            timestamp = int(timestamp_str)
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        return None
    except (ValueError, OSError) as e:
        logger.warning(f"Failed to convert timestamp from {path}: {e}")
        return None


def validate_xml_encoding(xml_content: str) -> str:
    """
    Validate and normalize XML encoding.

    Args:
        xml_content: Raw XML content

    Returns:
        Normalized XML content

    Raises:
        XMLValidationError: If encoding issues cannot be resolved
    """
    try:
        # Remove BOM if present
        if xml_content.startswith("\ufeff"):
            xml_content = xml_content[1:]

        # Check for encoding declaration
        encoding_pattern = r'<\?xml[^>]*encoding=["\']([^"\']+)["\'][^>]*\?>'
        match = re.search(encoding_pattern, xml_content)

        if match:
            declared_encoding = match.group(1).lower()
            logger.debug(f"XML declares encoding: {declared_encoding}")

        # Validate that content can be parsed
        try:
            ET.fromstring(xml_content)
        except ET.ParseError as e:
            raise XMLValidationError(f"XML encoding validation failed: {e}")

        return xml_content

    except Exception as e:
        logger.error(f"XML encoding validation failed: {e}")
        raise XMLValidationError(f"Encoding validation failed: {e}") from e


def get_xml_statistics(root: ET.Element) -> Dict[str, Any]:
    """
    Get statistics about the XML structure.

    Args:
        root: Parsed XML root element

    Returns:
        Dictionary containing XML statistics
    """
    try:
        stats = {
            "root_tag": root.tag,
            "total_elements": len(list(root.iter())),
            "record_count": len(root.findall("record")),
            "has_metadata": root.find("report_metadata") is not None,
            "has_policy": root.find("policy_published") is not None,
            "namespaces": list(
                set(
                    elem.tag.split("}")[0][1:]
                    for elem in root.iter()
                    if "}" in elem.tag
                )
            ),
        }

        # Get domain from policy if available
        policy = root.find("policy_published")
        if policy is not None:
            domain_elem = policy.find("domain")
            if domain_elem is not None:
                stats["domain"] = domain_elem.text

        return stats

    except Exception as e:
        logger.error(f"Failed to generate XML statistics: {e}")
        return {"error": str(e)}
