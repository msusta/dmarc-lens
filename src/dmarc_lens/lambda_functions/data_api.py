"""
Data API Lambda function for DMARC Lens.

This function provides REST API endpoints for accessing DMARC report data
and analysis results. It handles authentication, filtering, pagination,
and data retrieval from DynamoDB.

Requirements: 6.1, 6.2, 6.4
"""

import csv
import io
import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Any
from collections import defaultdict

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")
reports_table = dynamodb.Table(os.getenv("REPORTS_TABLE_NAME", "dmarc-reports"))
analysis_table = dynamodb.Table(os.getenv("ANALYSIS_TABLE_NAME", "dmarc-analysis"))


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder for DynamoDB Decimal types."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for Data API requests.

    Args:
        event: API Gateway event containing request details
        context: Lambda context object

    Returns:
        API Gateway response with status code, headers, and body
    """
    try:
        # Extract request information
        http_method = event.get("httpMethod") or event.get("requestContext", {}).get(
            "http", {}
        ).get("method")
        path = event.get("path") or event.get("rawPath", "")
        query_params = event.get("queryStringParameters") or {}
        path_params = event.get("pathParameters") or {}

        logger.info(f"Processing {http_method} request to {path}")

        # Route the request to appropriate handler
        if path.startswith("/reports"):
            if path == "/reports" and http_method == "GET":
                return handle_list_reports(query_params)
            # Match /reports/{id}/export before /reports/{id}
            elif "/export" in path and http_method == "GET":
                parts = path.split("/")
                # /reports/{report_id}/export
                report_id = path_params.get("report_id") or parts[2]
                return handle_export_report(report_id, query_params)
            elif path.startswith("/reports/") and http_method == "GET":
                report_id = path_params.get("report_id") or path.split("/")[2]
                return handle_get_report(report_id, query_params)
        elif path.startswith("/analysis"):
            if path.startswith("/analysis/") and http_method == "GET":
                domain = path_params.get("domain") or path.split("/")[-1]
                return handle_get_analysis(domain, query_params)
        elif path == "/dashboard" and http_method == "GET":
            return handle_get_dashboard(query_params)
        return create_error_response(404, "Endpoint not found")

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return create_error_response(500, "Internal server error")


def _group_records_into_report(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Group flat DynamoDB record items into a nested DMARCReport shape.

    Transforms flat items (one per record) into:
    {metadata, policy_published, records: [...]}

    Args:
        items: List of DynamoDB items belonging to the same report

    Returns:
        Nested DMARCReport-shaped dictionary
    """
    if not items:
        return {}

    first = items[0]

    records: List[Dict[str, Any]] = []

    for item in items:
        record: Dict[str, Any] = {
            "source_ip": item.get("source_ip", ""),
            "count": item.get("count", 0),
            "policy_evaluated": {
                "disposition": item.get("disposition", "none"),
                "dkim": item.get("dkim_result", "fail"),
                "spf": item.get("spf_result", "fail"),
            },
            "header_from": item.get("header_from", ""),
            "dkim_results": item.get("dkim_detailed_results", []),
            "spf_results": item.get("spf_detailed_results", []),
        }
        records.append(record)

    report: Dict[str, Any] = {
        "metadata": {
            "org_name": first.get("org_name", ""),
            "email": first.get("email", ""),
            "report_id": first.get("report_id", ""),
            "date_range_begin": first.get("date_range_begin"),
            "date_range_end": first.get("date_range_end"),
        },
        "policy_published": {
            "domain": first.get("domain", ""),
            "p": first.get("policy_p", "none"),
            "sp": first.get("policy_sp"),
            "pct": first.get("policy_pct", 100),
        },
        "records": records,
    }

    return report


def handle_list_reports(query_params: Dict[str, str]) -> Dict[str, Any]:
    """
    Handle GET /reports - List DMARC reports with filtering and pagination.

    Returns PaginatedResponse<DMARCReport> shaped response:
    {items: [...], total: N, page: N, limit: N, has_next: bool}
    """
    try:
        # Parse query parameters
        domain = query_params.get("domain")
        start_date = query_params.get("start_date")
        end_date = query_params.get("end_date")
        page = int(query_params.get("page", 1))
        limit = min(int(query_params.get("limit", 50)), 100)
        next_token = query_params.get("next_token")

        # Build query based on filters
        if domain:
            query_kwargs = {
                "IndexName": "domain-index",
                "KeyConditionExpression": Key("domain").eq(domain),
                "ScanIndexForward": False,
            }

            if start_date and end_date:
                query_kwargs["FilterExpression"] = Attr("date_range_begin").gte(
                    int(start_date)
                ) & Attr("date_range_end").lte(int(end_date))
            elif start_date:
                query_kwargs["FilterExpression"] = Attr("date_range_begin").gte(
                    int(start_date)
                )
            elif end_date:
                query_kwargs["FilterExpression"] = Attr("date_range_end").lte(
                    int(end_date)
                )

            if next_token:
                query_kwargs["ExclusiveStartKey"] = json.loads(next_token)

            response = reports_table.query(**query_kwargs)
        else:
            scan_kwargs = {}

            if start_date and end_date:
                scan_kwargs["FilterExpression"] = Attr("date_range_begin").gte(
                    int(start_date)
                ) & Attr("date_range_end").lte(int(end_date))
            elif start_date:
                scan_kwargs["FilterExpression"] = Attr("date_range_begin").gte(
                    int(start_date)
                )
            elif end_date:
                scan_kwargs["FilterExpression"] = Attr("date_range_end").lte(
                    int(end_date)
                )

            if next_token:
                scan_kwargs["ExclusiveStartKey"] = json.loads(next_token)

            response = reports_table.scan(**scan_kwargs)

        all_items = response.get("Items", [])

        # Paginate through all results to group properly
        while "LastEvaluatedKey" in response:
            if domain:
                query_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
                response = reports_table.query(**query_kwargs)
            else:
                scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
                response = reports_table.scan(**scan_kwargs)
            all_items.extend(response.get("Items", []))

        # Group records by report_id
        reports_by_id: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for item in all_items:
            report_id = item.get("report_id", "unknown")
            reports_by_id[report_id].append(item)

        # Sort reports by date (most recent first)
        sorted_report_ids = sorted(
            reports_by_id.keys(),
            key=lambda rid: max(
                int(item.get("date_range_begin", 0)) for item in reports_by_id[rid]
            ),
            reverse=True,
        )

        total = len(sorted_report_ids)

        # Apply pagination
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        page_report_ids = sorted_report_ids[start_idx:end_idx]

        # Build nested report objects
        items = []
        for report_id in page_report_ids:
            report = _group_records_into_report(reports_by_id[report_id])
            items.append(report)

        result = {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "has_next": end_idx < total,
        }

        return create_success_response(result)

    except ValueError as e:
        logger.error(f"Invalid query parameter: {str(e)}")
        return create_error_response(400, f"Invalid query parameter: {str(e)}")
    except ClientError as e:
        logger.error(f"DynamoDB error: {str(e)}")
        return create_error_response(500, "Database error")


def handle_get_report(report_id: str, query_params: Dict[str, str]) -> Dict[str, Any]:
    """
    Handle GET /reports/{report_id} - Get specific report details.

    Returns a nested DMARCReport object.
    """
    try:
        response = reports_table.query(
            KeyConditionExpression=Key("report_id").eq(report_id)
        )

        items = response.get("Items", [])
        if not items:
            return create_error_response(404, "Report not found")

        report = _group_records_into_report(items)
        return create_success_response(report)

    except ClientError as e:
        logger.error(f"DynamoDB error: {str(e)}")
        return create_error_response(500, "Database error")


def handle_get_analysis(domain: str, query_params: Dict[str, str]) -> Dict[str, Any]:
    """
    Handle GET /analysis/{domain} - Get domain analysis data.

    Returns a DomainAnalysis-shaped response:
    {domain, analysis_date, total_messages, auth_success_rate,
     top_sources, failure_reasons, recommendations, trend_data}
    """
    try:
        start_date = query_params.get("start_date")
        end_date = query_params.get("end_date")
        limit = min(int(query_params.get("limit", 30)), 90)

        query_kwargs = {
            "KeyConditionExpression": Key("domain").eq(domain),
            "Limit": limit,
            "ScanIndexForward": False,
        }

        if start_date and end_date:
            query_kwargs["KeyConditionExpression"] = Key("domain").eq(domain) & Key(
                "analysis_date"
            ).between(start_date, end_date)
        elif start_date:
            query_kwargs["KeyConditionExpression"] = Key("domain").eq(domain) & Key(
                "analysis_date"
            ).gte(start_date)
        elif end_date:
            query_kwargs["KeyConditionExpression"] = Key("domain").eq(domain) & Key(
                "analysis_date"
            ).lte(end_date)

        response = analysis_table.query(**query_kwargs)

        items = response.get("Items", [])
        if not items:
            return create_error_response(404, "No analysis data found for domain")

        # Transform the most recent analysis into DomainAnalysis shape
        latest = items[0]

        # Extract top_sources from failure_analysis
        failure_analysis: Dict[str, Any] = latest.get(
            "failure_analysis", {}
        )  # type: ignore[assignment]
        top_failing_ips: List[Dict[str, Any]] = failure_analysis.get(
            "top_failing_ips", []
        )  # type: ignore[assignment]
        top_sources = [
            entry.get("ip", "") for entry in top_failing_ips if entry.get("ip")
        ]

        # Flatten failure_reasons
        failure_patterns: Dict[str, Any] = failure_analysis.get(
            "failure_patterns", {}
        )  # type: ignore[assignment]
        failure_sources: Dict[str, Any] = failure_analysis.get(
            "failure_sources", {}
        )  # type: ignore[assignment]
        failure_reasons: Dict[str, Any] = {}
        failure_reasons.update(failure_patterns)
        failure_reasons.update(failure_sources)

        # Extract recommendation titles
        raw_recommendations: List[Any] = latest.get(
            "recommendations", []
        )  # type: ignore[assignment]
        recommendations = [
            rec.get("title", "") if isinstance(rec, dict) else str(rec)
            for rec in raw_recommendations
        ]

        # Build trend_data from historical items
        trend_data: Dict[str, Any] = {}
        for item in items:
            date = str(item.get("analysis_date", ""))
            rate = item.get("auth_success_rate", 0)
            if date:
                trend_data[date] = (
                    float(rate)
                    if isinstance(rate, Decimal)
                    else rate
                )  # type: ignore[arg-type]

        result = {
            "domain": domain,
            "analysis_date": latest.get("analysis_date", ""),
            "total_messages": latest.get("total_messages", 0),
            "auth_success_rate": float(
                latest.get("auth_success_rate", 0)
            ),  # type: ignore[arg-type]
            "top_sources": top_sources,
            "failure_reasons": failure_reasons,
            "recommendations": recommendations,
            "trend_data": trend_data,
        }

        return create_success_response(result)

    except ValueError as e:
        logger.error(f"Invalid query parameter: {str(e)}")
        return create_error_response(400, f"Invalid query parameter: {str(e)}")
    except ClientError as e:
        logger.error(f"DynamoDB error: {str(e)}")
        return create_error_response(500, "Database error")


def handle_get_dashboard(query_params: Dict[str, str]) -> Dict[str, Any]:
    """
    Handle GET /dashboard - Get dashboard summary data.

    Returns a DashboardSummary-shaped response:
    {total_reports, total_messages, overall_success_rate,
     domains_monitored, security_issues, recent_activity, top_domains}
    """
    try:
        days = min(int(query_params.get("days", 30)), 90)

        end_date = datetime.now(timezone.utc)
        start_timestamp = int((end_date.timestamp() - (days * 24 * 3600)))

        # Get recent reports
        reports_data: List[Dict[str, Any]] = []
        scan_kwargs: Dict[str, Any] = {
            "FilterExpression": Attr("date_range_begin").gte(start_timestamp),
            "ProjectionExpression": (
                "report_id, domain, #count, disposition,"
                " dkim_result, spf_result, date_range_begin"
            ),
            "ExpressionAttributeNames": {"#count": "count"},
            "Limit": 1000,
        }
        reports_response = reports_table.scan(**scan_kwargs)
        reports_data.extend(reports_response.get("Items", []))

        while "LastEvaluatedKey" in reports_response and len(reports_data) < 5000:
            scan_kwargs["ExclusiveStartKey"] = reports_response["LastEvaluatedKey"]
            reports_response = reports_table.scan(**scan_kwargs)
            reports_data.extend(reports_response.get("Items", []))

        # Get recent analysis data for security issues count
        analysis_response = analysis_table.scan(Limit=50)
        analysis_items = analysis_response.get("Items", [])

        # Count security issues across all recent analyses
        security_issues_count = 0
        for analysis_item in analysis_items:
            issues = analysis_item.get("security_issues", [])
            if isinstance(issues, list):
                security_issues_count += len(issues)

        # Process reports data
        domain_stats: Dict[str, Dict[str, int]] = {}
        total_messages = 0
        auth_success = 0
        report_ids = set()

        # Track per-day stats for recent_activity
        daily_stats: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"success": 0, "total": 0}
        )

        for report in reports_data:
            domain = report.get("domain", "unknown")
            count = int(report.get("count", 0))
            dkim_pass = report.get("dkim_result") == "pass"
            spf_pass = report.get("spf_result") == "pass"
            report_id = report.get("report_id", "")

            report_ids.add(report_id)

            if domain not in domain_stats:
                domain_stats[domain] = {
                    "total_messages": 0,
                    "auth_success": 0,
                    "auth_failure": 0,
                }

            domain_stats[domain]["total_messages"] += count
            total_messages += count

            # DMARC alignment: DKIM OR SPF must pass (per RFC 7489)
            is_aligned = dkim_pass or spf_pass
            if is_aligned:
                domain_stats[domain]["auth_success"] += count
                auth_success += count
            else:
                domain_stats[domain]["auth_failure"] += count

            # Track daily activity
            date_begin = report.get("date_range_begin")
            if date_begin:
                day_str = datetime.fromtimestamp(
                    int(date_begin), tz=timezone.utc
                ).strftime("%Y-%m-%d")
                daily_stats[day_str]["total"] += count
                if is_aligned:
                    daily_stats[day_str]["success"] += count

        overall_success_rate = (
            (auth_success / total_messages * 100) if total_messages > 0 else 0
        )

        # Build top_domains
        top_domains = sorted(
            domain_stats.items(),
            key=lambda x: x[1]["total_messages"],
            reverse=True,
        )[:10]

        top_domains_list = [
            {
                "domain": domain,
                "total_messages": stats["total_messages"],
                "success_rate": round(
                    (
                        (stats["auth_success"] / stats["total_messages"] * 100)
                        if stats["total_messages"] > 0
                        else 0
                    ),
                    2,
                ),
            }
            for domain, stats in top_domains
        ]

        # Build recent_activity sorted by date
        recent_activity = sorted(
            [
                {
                    "date": day,
                    "success_rate": round(
                        (
                            (stats["success"] / stats["total"] * 100)
                            if stats["total"] > 0
                            else 0
                        ),
                        2,
                    ),
                    "message_count": stats["total"],
                }
                for day, stats in daily_stats.items()
            ],
            key=lambda x: str(x["date"]),
        )

        dashboard_data = {
            "total_reports": len(report_ids),
            "total_messages": total_messages,
            "overall_success_rate": round(overall_success_rate, 2),
            "domains_monitored": len(domain_stats),
            "security_issues": security_issues_count,
            "recent_activity": recent_activity,
            "top_domains": top_domains_list,
        }

        return create_success_response(dashboard_data)

    except ValueError as e:
        logger.error(f"Invalid query parameter: {str(e)}")
        return create_error_response(400, f"Invalid query parameter: {str(e)}")
    except ClientError as e:
        logger.error(f"DynamoDB error: {str(e)}")
        return create_error_response(500, "Database error")


def handle_export_report(
    report_id: str, query_params: Dict[str, str]
) -> Dict[str, Any]:
    """
    Handle GET /reports/{report_id}/export - Export report data.

    Query parameters:
    - format: 'json' or 'csv' (default: 'json')
    """
    try:
        response = reports_table.query(
            KeyConditionExpression=Key("report_id").eq(report_id)
        )

        items = response.get("Items", [])
        if not items:
            return create_error_response(404, "Report not found")

        export_format = query_params.get("format", "json")
        report = _group_records_into_report(items)

        if export_format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)

            # Header
            writer.writerow(
                [
                    "source_ip",
                    "count",
                    "disposition",
                    "dkim",
                    "spf",
                    "header_from",
                    "domain",
                    "org_name",
                    "report_id",
                ]
            )

            for record in report.get("records", []):
                pe = record.get("policy_evaluated", {})
                writer.writerow(
                    [
                        record.get("source_ip", ""),
                        record.get("count", 0),
                        pe.get("disposition", ""),
                        pe.get("dkim", ""),
                        pe.get("spf", ""),
                        record.get("header_from", ""),
                        report["policy_published"]["domain"],
                        report["metadata"]["org_name"],
                        report["metadata"]["report_id"],
                    ]
                )

            cors_origin = os.getenv("CORS_ORIGIN", "http://localhost:3000")
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "text/csv",
                    "Content-Disposition": (
                        f'attachment; filename="dmarc-report-'
                        f'{report_id}.csv"'
                    ),
                    "Access-Control-Allow-Origin": cors_origin,
                    "Access-Control-Allow-Headers": "Content-Type,Authorization",
                    "Access-Control-Allow-Methods": "GET,OPTIONS",
                },
                "body": output.getvalue(),
            }
        else:
            # JSON export
            cors_origin = os.getenv("CORS_ORIGIN", "http://localhost:3000")
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Content-Disposition": (
                        f'attachment; filename="dmarc-report-'
                        f'{report_id}.json"'
                    ),
                    "Access-Control-Allow-Origin": cors_origin,
                    "Access-Control-Allow-Headers": "Content-Type,Authorization",
                    "Access-Control-Allow-Methods": "GET,OPTIONS",
                },
                "body": json.dumps(report, cls=DecimalEncoder, indent=2),
            }

    except ClientError as e:
        logger.error(f"DynamoDB error: {str(e)}")
        return create_error_response(500, "Database error")


def create_success_response(data: Any) -> Dict[str, Any]:
    """Create a successful API response."""
    cors_origin = os.getenv("CORS_ORIGIN", "http://localhost:3000")
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": cors_origin,
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,OPTIONS",
        },
        "body": json.dumps(data, cls=DecimalEncoder),
    }


def create_error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Create an error API response."""
    cors_origin = os.getenv("CORS_ORIGIN", "http://localhost:3000")
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": cors_origin,
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,OPTIONS",
        },
        "body": json.dumps(
            {
                "error": {
                    "code": status_code,
                    "message": message,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            }
        ),
    }
