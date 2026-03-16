"""
DMARC Report Parser Lambda Function.

This Lambda function processes S3 events triggered by SES email delivery,
extracts DMARC report attachments, parses them, and stores the structured
data in DynamoDB.
"""

import json
import logging
import os
import xml.etree.ElementTree as ET
import boto3
import traceback
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from botocore.exceptions import ClientError

from ..models.dmarc_models import (
    DMARCReport,
    ReportMetadata,
    PolicyPublished,
    PolicyEvaluated,
    AuthResult,
    DMARCRecord,
)
from ..utils.email_utils import (
    parse_email_from_string,
    extract_dmarc_reports,
    EmailParsingError,
    AttachmentExtractionError,
    get_email_metadata,
    validate_email_structure,
)
from ..utils.xml_utils import (
    parse_xml_string,
    validate_dmarc_xml_structure,
    XMLValidationError,
    XMLParsingError,
    extract_xml_text,
    extract_xml_int,
    extract_xml_timestamp,
)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
REPORTS_TABLE_NAME = os.getenv("REPORTS_TABLE_NAME", "dmarc-reports")
FAILED_REPORTS_TABLE_NAME = os.getenv(
    "FAILED_REPORTS_TABLE_NAME", "dmarc-failed-reports"
)


class ReportProcessingError(Exception):
    """Exception raised when report processing fails."""

    pass


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for processing S3 events from SES email delivery.

    Args:
        event: S3 event containing bucket and object information
        context: Lambda context object

    Returns:
        Response dictionary with processing results
    """
    try:
        logger.info(f"Processing S3 event: {json.dumps(event)}")

        # Parse S3 event
        records_processed = 0
        errors = []

        for record in event.get("Records", []):
            try:
                # Extract S3 information
                s3_info = record["s3"]
                bucket_name = s3_info["bucket"]["name"]
                object_key = s3_info["object"]["key"]

                logger.info(f"Processing email: s3://{bucket_name}/{object_key}")

                # Process the email
                result = process_email_from_s3(bucket_name, object_key)
                records_processed += result["reports_processed"]

                if result["errors"]:
                    errors.extend(result["errors"])

            except Exception as e:
                error_msg = f"Failed to process record {record}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        # Return processing summary
        response = {
            "statusCode": 200,
            "body": {
                "records_processed": records_processed,
                "errors": errors,
                "success": len(errors) == 0,
            },
        }

        logger.info(f"Processing complete: {response}")
        return response

    except Exception as e:
        logger.error(f"Lambda handler failed: {str(e)}")
        logger.error(traceback.format_exc())

        return {"statusCode": 500, "body": {"error": str(e), "success": False}}


def process_email_from_s3(bucket_name: str, object_key: str) -> Dict[str, Any]:
    """
    Process a single email from S3 and extract DMARC reports.

    Args:
        bucket_name: S3 bucket name
        object_key: S3 object key

    Returns:
        Dictionary with processing results
    """
    try:
        # Download email from S3
        logger.info(f"Downloading email from s3://{bucket_name}/{object_key}")

        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        email_content = response["Body"].read().decode("utf-8")

        # Parse email
        message = parse_email_from_string(email_content)

        # Validate email structure
        if not validate_email_structure(message):
            raise ReportProcessingError("Email structure validation failed")

        # Extract email metadata
        email_metadata = get_email_metadata(message)
        logger.info(f"Processing email from: {email_metadata.get('from', 'unknown')}")

        # Extract DMARC reports
        dmarc_reports = extract_dmarc_reports(message)

        if not dmarc_reports:
            logger.warning("No DMARC reports found in email")
            return {
                "reports_processed": 0,
                "errors": ["No DMARC reports found in email"],
                "email_metadata": email_metadata,
            }

        # Process each DMARC report
        reports_processed = 0
        errors = []

        for filename, xml_content in dmarc_reports:
            try:
                logger.info(f"Processing DMARC report: {filename}")

                # Parse and validate XML
                root = parse_xml_string(xml_content)
                validate_dmarc_xml_structure(root)

                # Convert XML to data model
                dmarc_report = parse_dmarc_report_xml(root)

                # Store in DynamoDB
                store_dmarc_report(dmarc_report, email_metadata, object_key, filename)

                reports_processed += 1
                logger.info(f"Successfully processed report: {filename}")

            except Exception as e:
                error_msg = f"Failed to process report {filename}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

                # Store failed report for manual review
                try:
                    store_failed_report(
                        filename, xml_content, str(e), email_metadata, object_key
                    )
                except Exception as store_error:
                    logger.error(f"Failed to store failed report: {store_error}")

        return {
            "reports_processed": reports_processed,
            "errors": errors,
            "email_metadata": email_metadata,
        }

    except EmailParsingError as e:
        error_msg = f"Email parsing failed: {str(e)}"
        logger.error(error_msg)
        return {"reports_processed": 0, "errors": [error_msg], "email_metadata": {}}

    except AttachmentExtractionError as e:
        error_msg = f"Attachment extraction failed: {str(e)}"
        logger.error(error_msg)
        return {"reports_processed": 0, "errors": [error_msg], "email_metadata": {}}

    except ClientError as e:
        error_msg = f"AWS service error: {str(e)}"
        logger.error(error_msg)
        return {"reports_processed": 0, "errors": [error_msg], "email_metadata": {}}

    except Exception as e:
        error_msg = f"Unexpected error processing email: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return {"reports_processed": 0, "errors": [error_msg], "email_metadata": {}}


def parse_dmarc_report_xml(root: ET.Element) -> DMARCReport:
    """
    Parse DMARC report XML into data model objects.

    Args:
        root: Parsed XML root element

    Returns:
        DMARCReport object

    Raises:
        XMLParsingError: If XML parsing fails
    """
    try:
        # Parse report metadata
        metadata_elem = root.find("report_metadata")
        if metadata_elem is None:
            raise XMLParsingError("Missing report_metadata element")

        date_range = metadata_elem.find("date_range")
        if date_range is None:
            raise XMLParsingError("Missing date_range element")

        begin_timestamp = extract_xml_timestamp(date_range, "begin")
        end_timestamp = extract_xml_timestamp(date_range, "end")

        if begin_timestamp is None or end_timestamp is None:
            raise XMLParsingError("Invalid date range timestamps")

        metadata = ReportMetadata(
            org_name=extract_xml_text(metadata_elem, "org_name"),
            email=extract_xml_text(metadata_elem, "email"),
            report_id=extract_xml_text(metadata_elem, "report_id"),
            date_range_begin=begin_timestamp,
            date_range_end=end_timestamp,
            extra_contact_info=extract_xml_text(metadata_elem, "extra_contact_info"),
        )

        # Parse policy published
        policy_elem = root.find("policy_published")
        if policy_elem is None:
            raise XMLParsingError("Missing policy_published element")

        policy = PolicyPublished(
            domain=extract_xml_text(policy_elem, "domain"),
            p=extract_xml_text(policy_elem, "p"),
            sp=extract_xml_text(policy_elem, "sp") or None,
            pct=extract_xml_int(policy_elem, "pct", 100),
            adkim=extract_xml_text(policy_elem, "adkim") or None,
            aspf=extract_xml_text(policy_elem, "aspf") or None,
        )

        # Parse records
        records = []
        for record_elem in root.findall("record"):
            record = parse_dmarc_record_xml(record_elem)
            records.append(record)

        return DMARCReport(metadata=metadata, policy_published=policy, records=records)

    except Exception as e:
        logger.error(f"Failed to parse DMARC report XML: {e}")
        raise XMLParsingError(f"DMARC report parsing failed: {e}") from e


def parse_dmarc_record_xml(record_elem: ET.Element) -> DMARCRecord:
    """
    Parse a single DMARC record from XML.

    Args:
        record_elem: XML element containing record data

    Returns:
        DMARCRecord object
    """
    # Parse row section
    row = record_elem.find("row")
    if row is None:
        raise XMLParsingError("Missing row element in record")

    # Parse policy evaluated
    policy_eval_elem = row.find("policy_evaluated")
    if policy_eval_elem is None:
        raise XMLParsingError("Missing policy_evaluated element")

    # Parse reason elements if present
    reasons = []
    for reason_elem in policy_eval_elem.findall("reason"):
        reason_type = extract_xml_text(reason_elem, "type")
        reason_comment = extract_xml_text(reason_elem, "comment")
        if reason_type:
            reason_str = reason_type
            if reason_comment:
                reason_str = f"{reason_type}: {reason_comment}"
            reasons.append(reason_str)

    policy_evaluated = PolicyEvaluated(
        disposition=extract_xml_text(policy_eval_elem, "disposition"),
        dkim=extract_xml_text(policy_eval_elem, "dkim"),
        spf=extract_xml_text(policy_eval_elem, "spf"),
        reason=reasons if reasons else None,
    )

    # Parse identifiers
    identifiers = record_elem.find("identifiers")
    if identifiers is None:
        raise XMLParsingError("Missing identifiers element in record")

    header_from = extract_xml_text(identifiers, "header_from")

    # Parse authentication results
    auth_results = record_elem.find("auth_results")
    dkim_results = []
    spf_results = []

    if auth_results is not None:
        # Parse DKIM results
        for dkim_elem in auth_results.findall("dkim"):
            dkim_result = AuthResult(
                domain=extract_xml_text(dkim_elem, "domain"),
                result=extract_xml_text(dkim_elem, "result"),
                selector=extract_xml_text(dkim_elem, "selector") or None,
            )
            dkim_results.append(dkim_result)

        # Parse SPF results
        for spf_elem in auth_results.findall("spf"):
            spf_result = AuthResult(
                domain=extract_xml_text(spf_elem, "domain"),
                result=extract_xml_text(spf_elem, "result"),
            )
            spf_results.append(spf_result)

    return DMARCRecord(
        source_ip=extract_xml_text(row, "source_ip"),
        count=extract_xml_int(row, "count"),
        policy_evaluated=policy_evaluated,
        header_from=header_from,
        dkim_results=dkim_results,
        spf_results=spf_results,
    )


def store_dmarc_report(
    report: DMARCReport, email_metadata: Dict[str, Any], s3_key: str, filename: str
) -> None:
    """
    Store DMARC report data in DynamoDB.

    Args:
        report: Parsed DMARC report
        email_metadata: Email metadata
        s3_key: S3 object key for the original email
        filename: Original attachment filename
    """
    try:
        table = dynamodb.Table(REPORTS_TABLE_NAME)

        # Store each record as a separate DynamoDB item
        for i, record in enumerate(report.records):
            item = {
                "report_id": report.metadata.report_id,
                "record_id": f"{report.metadata.report_id}#{i:04d}",
                "org_name": report.metadata.org_name,
                "email": report.metadata.email,
                "date_range_begin": int(report.metadata.date_range_begin.timestamp()),
                "date_range_end": int(report.metadata.date_range_end.timestamp()),
                "domain": report.policy_published.domain,
                "policy_p": report.policy_published.p,
                "policy_sp": report.policy_published.sp,
                "policy_pct": report.policy_published.pct,
                "source_ip": record.source_ip,
                "count": record.count,
                "disposition": record.policy_evaluated.disposition,
                "dkim_result": record.policy_evaluated.dkim,
                "spf_result": record.policy_evaluated.spf,
                "header_from": record.header_from,
                "created_at": int(datetime.now(timezone.utc).timestamp()),
                "s3_key": s3_key,
                "filename": filename,
                "email_from": email_metadata.get("from", ""),
                "email_subject": email_metadata.get("subject", ""),
                "email_date": email_metadata.get("date", ""),
            }

            # Add DKIM results if present
            if record.dkim_results:
                item["dkim_domains"] = [dr.domain for dr in record.dkim_results]
                item["dkim_detailed_results"] = [
                    {"domain": dr.domain, "result": dr.result, "selector": dr.selector}
                    for dr in record.dkim_results
                ]

            # Add SPF results if present
            if record.spf_results:
                item["spf_domains"] = [sr.domain for sr in record.spf_results]
                item["spf_detailed_results"] = [
                    {"domain": sr.domain, "result": sr.result}
                    for sr in record.spf_results
                ]

            # Store item in DynamoDB
            table.put_item(Item=item)

        logger.info(
            f"Stored {len(report.records)} records for report {report.metadata.report_id}"
        )

    except Exception as e:
        logger.error(f"Failed to store DMARC report: {e}")
        raise ReportProcessingError(f"DynamoDB storage failed: {e}") from e


def store_failed_report(
    filename: str,
    xml_content: str,
    error_message: str,
    email_metadata: Dict[str, Any],
    s3_key: str,
) -> None:
    """
    Store failed report information for manual review.

    Args:
        filename: Original attachment filename
        xml_content: Raw XML content
        error_message: Error that occurred during processing
        email_metadata: Email metadata
        s3_key: S3 object key for the original email
    """
    try:
        table = dynamodb.Table(FAILED_REPORTS_TABLE_NAME)

        item = {
            "failure_id": f"{s3_key}#{filename}",
            "filename": filename,
            "xml_content": xml_content[:10000],  # Truncate if too large
            "error_message": error_message,
            "email_from": email_metadata.get("from", ""),
            "email_subject": email_metadata.get("subject", ""),
            "email_date": email_metadata.get("date", ""),
            "s3_key": s3_key,
            "failed_at": int(datetime.now(timezone.utc).timestamp()),
            "processed": False,
        }

        table.put_item(Item=item)
        logger.info(f"Stored failed report: {filename}")

    except Exception as e:
        logger.error(f"Failed to store failed report: {e}")
        # Don't raise exception here to avoid masking original error
