"""
Data API Lambda function for DMARC Lens.

This function provides REST API endpoints for accessing DMARC report data
and analysis results. It handles authentication, filtering, pagination,
and data retrieval from DynamoDB.

Requirements: 6.1, 6.2, 6.4
"""

import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import parse_qs

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
reports_table = dynamodb.Table(os.getenv('REPORTS_TABLE_NAME', 'dmarc-reports'))
analysis_table = dynamodb.Table(os.getenv('ANALYSIS_TABLE_NAME', 'dmarc-analysis'))


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder for DynamoDB Decimal types."""
    
    def default(self, obj):
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
        http_method = event.get('httpMethod') or event.get('requestContext', {}).get('http', {}).get('method')
        path = event.get('path') or event.get('rawPath', '')
        query_params = event.get('queryStringParameters') or {}
        path_params = event.get('pathParameters') or {}
        
        logger.info(f"Processing {http_method} request to {path}")
        
        # Route the request to appropriate handler
        if path.startswith('/reports'):
            if path == '/reports' and http_method == 'GET':
                return handle_list_reports(query_params)
            elif path.startswith('/reports/') and http_method == 'GET':
                report_id = path_params.get('report_id') or path.split('/')[-1]
                return handle_get_report(report_id, query_params)
        elif path.startswith('/analysis'):
            if path.startswith('/analysis/') and http_method == 'GET':
                domain = path_params.get('domain') or path.split('/')[-1]
                return handle_get_analysis(domain, query_params)
        elif path == '/dashboard' and http_method == 'GET':
            return handle_get_dashboard(query_params)
        else:
            return create_error_response(404, "Endpoint not found")
            
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return create_error_response(500, "Internal server error")


def handle_list_reports(query_params: Dict[str, str]) -> Dict[str, Any]:
    """
    Handle GET /reports - List DMARC reports with filtering and pagination.
    
    Query parameters:
    - domain: Filter by domain
    - start_date: Filter by start date (Unix timestamp)
    - end_date: Filter by end date (Unix timestamp)
    - limit: Number of results per page (default: 50, max: 100)
    - next_token: Pagination token
    
    Args:
        query_params: Query string parameters
        
    Returns:
        API response with reports list
    """
    try:
        # Parse query parameters
        domain = query_params.get('domain')
        start_date = query_params.get('start_date')
        end_date = query_params.get('end_date')
        limit = min(int(query_params.get('limit', 50)), 100)
        next_token = query_params.get('next_token')
        
        # Build query based on filters
        if domain:
            # Query by domain using GSI
            query_kwargs = {
                'IndexName': 'domain-index',
                'KeyConditionExpression': Key('domain').eq(domain),
                'Limit': limit,
                'ScanIndexForward': False  # Most recent first
            }
            
            # Add date range filter if provided
            if start_date and end_date:
                query_kwargs['FilterExpression'] = (
                    Attr('date_range_begin').gte(int(start_date)) &
                    Attr('date_range_end').lte(int(end_date))
                )
            elif start_date:
                query_kwargs['FilterExpression'] = Attr('date_range_begin').gte(int(start_date))
            elif end_date:
                query_kwargs['FilterExpression'] = Attr('date_range_end').lte(int(end_date))
                
            # Add pagination token
            if next_token:
                query_kwargs['ExclusiveStartKey'] = json.loads(next_token)
                
            response = reports_table.query(**query_kwargs)
            
        else:
            # Scan all reports with optional date filter
            scan_kwargs = {
                'Limit': limit,
            }
            
            # Add date range filter if provided
            if start_date and end_date:
                scan_kwargs['FilterExpression'] = (
                    Attr('date_range_begin').gte(int(start_date)) &
                    Attr('date_range_end').lte(int(end_date))
                )
            elif start_date:
                scan_kwargs['FilterExpression'] = Attr('date_range_begin').gte(int(start_date))
            elif end_date:
                scan_kwargs['FilterExpression'] = Attr('date_range_end').lte(int(end_date))
                
            # Add pagination token
            if next_token:
                scan_kwargs['ExclusiveStartKey'] = json.loads(next_token)
                
            response = reports_table.scan(**scan_kwargs)
        
        # Prepare response
        items = response.get('Items', [])
        result = {
            'reports': items,
            'count': len(items),
            'scanned_count': response.get('ScannedCount', len(items))
        }
        
        # Add pagination token if more results available
        if 'LastEvaluatedKey' in response:
            result['next_token'] = json.dumps(response['LastEvaluatedKey'], cls=DecimalEncoder)
            
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
    
    Args:
        report_id: Report identifier
        query_params: Query string parameters
        
    Returns:
        API response with report details
    """
    try:
        # Query all records for the report
        response = reports_table.query(
            KeyConditionExpression=Key('report_id').eq(report_id)
        )
        
        items = response.get('Items', [])
        if not items:
            return create_error_response(404, "Report not found")
            
        # Group records by report metadata
        report_data = {
            'report_id': report_id,
            'metadata': {},
            'records': []
        }
        
        for item in items:
            # Extract metadata from first record
            if not report_data['metadata']:
                report_data['metadata'] = {
                    'org_name': item.get('org_name'),
                    'email': item.get('email'),
                    'date_range_begin': item.get('date_range_begin'),
                    'date_range_end': item.get('date_range_end'),
                    'domain': item.get('domain'),
                    'created_at': item.get('created_at')
                }
            
            # Add record data
            report_data['records'].append({
                'record_id': item.get('record_id'),
                'source_ip': item.get('source_ip'),
                'count': item.get('count'),
                'disposition': item.get('disposition'),
                'dkim_result': item.get('dkim_result'),
                'spf_result': item.get('spf_result'),
                'header_from': item.get('header_from')
            })
        
        return create_success_response(report_data)
        
    except ClientError as e:
        logger.error(f"DynamoDB error: {str(e)}")
        return create_error_response(500, "Database error")


def handle_get_analysis(domain: str, query_params: Dict[str, str]) -> Dict[str, Any]:
    """
    Handle GET /analysis/{domain} - Get domain analysis data.
    
    Query parameters:
    - start_date: Filter by start date (YYYY-MM-DD)
    - end_date: Filter by end date (YYYY-MM-DD)
    - limit: Number of results (default: 30, max: 90)
    
    Args:
        domain: Domain name
        query_params: Query string parameters
        
    Returns:
        API response with analysis data
    """
    try:
        # Parse query parameters
        start_date = query_params.get('start_date')
        end_date = query_params.get('end_date')
        limit = min(int(query_params.get('limit', 30)), 90)
        
        # Build query
        query_kwargs = {
            'KeyConditionExpression': Key('domain').eq(domain),
            'Limit': limit,
            'ScanIndexForward': False  # Most recent first
        }
        
        # Add date range filter if provided
        if start_date and end_date:
            query_kwargs['KeyConditionExpression'] = (
                Key('domain').eq(domain) &
                Key('analysis_date').between(start_date, end_date)
            )
        elif start_date:
            query_kwargs['KeyConditionExpression'] = (
                Key('domain').eq(domain) &
                Key('analysis_date').gte(start_date)
            )
        elif end_date:
            query_kwargs['KeyConditionExpression'] = (
                Key('domain').eq(domain) &
                Key('analysis_date').lte(end_date)
            )
        
        response = analysis_table.query(**query_kwargs)
        
        items = response.get('Items', [])
        if not items:
            return create_error_response(404, "No analysis data found for domain")
            
        return create_success_response({
            'domain': domain,
            'analysis_data': items,
            'count': len(items)
        })
        
    except ValueError as e:
        logger.error(f"Invalid query parameter: {str(e)}")
        return create_error_response(400, f"Invalid query parameter: {str(e)}")
    except ClientError as e:
        logger.error(f"DynamoDB error: {str(e)}")
        return create_error_response(500, "Database error")


def handle_get_dashboard(query_params: Dict[str, str]) -> Dict[str, Any]:
    """
    Handle GET /dashboard - Get dashboard summary data.
    
    Query parameters:
    - days: Number of days to include (default: 30, max: 90)
    
    Args:
        query_params: Query string parameters
        
    Returns:
        API response with dashboard data
    """
    try:
        # Parse query parameters
        days = min(int(query_params.get('days', 30)), 90)
        
        # Calculate date range
        end_date = datetime.now(timezone.utc)
        start_timestamp = int((end_date.timestamp() - (days * 24 * 3600)))
        
        # Get recent reports summary
        reports_response = reports_table.scan(
            FilterExpression=Attr('date_range_begin').gte(start_timestamp),
            ProjectionExpression='domain, #count, disposition, dkim_result, spf_result',
            ExpressionAttributeNames={'#count': 'count'}
        )
        
        # Get recent analysis data
        analysis_response = analysis_table.scan(
            FilterExpression=Attr('analysis_date').gte(end_date.strftime('%Y-%m-%d')),
            Limit=50
        )
        
        # Process reports data
        reports_data = reports_response.get('Items', [])
        domain_stats = {}
        total_messages = 0
        auth_success = 0
        
        for report in reports_data:
            domain = report.get('domain', 'unknown')
            count = int(report.get('count', 0))
            dkim_pass = report.get('dkim_result') == 'pass'
            spf_pass = report.get('spf_result') == 'pass'
            
            if domain not in domain_stats:
                domain_stats[domain] = {
                    'total_messages': 0,
                    'auth_success': 0,
                    'auth_failure': 0
                }
            
            domain_stats[domain]['total_messages'] += count
            total_messages += count
            
            if dkim_pass and spf_pass:
                domain_stats[domain]['auth_success'] += count
                auth_success += count
            else:
                domain_stats[domain]['auth_failure'] += count
        
        # Calculate overall success rate
        overall_success_rate = (auth_success / total_messages * 100) if total_messages > 0 else 0
        
        # Get top domains by volume
        top_domains = sorted(
            domain_stats.items(),
            key=lambda x: x[1]['total_messages'],
            reverse=True
        )[:10]
        
        # Process analysis data
        analysis_data = analysis_response.get('Items', [])
        
        dashboard_data = {
            'summary': {
                'total_messages': total_messages,
                'total_domains': len(domain_stats),
                'overall_success_rate': round(overall_success_rate, 2),
                'total_reports': len(reports_data),
                'date_range_days': days
            },
            'top_domains': [
                {
                    'domain': domain,
                    'total_messages': stats['total_messages'],
                    'success_rate': round(
                        (stats['auth_success'] / stats['total_messages'] * 100)
                        if stats['total_messages'] > 0 else 0, 2
                    )
                }
                for domain, stats in top_domains
            ],
            'recent_analysis': analysis_data[:10]  # Latest 10 analysis results
        }
        
        return create_success_response(dashboard_data)
        
    except ValueError as e:
        logger.error(f"Invalid query parameter: {str(e)}")
        return create_error_response(400, f"Invalid query parameter: {str(e)}")
    except ClientError as e:
        logger.error(f"DynamoDB error: {str(e)}")
        return create_error_response(500, "Database error")


def create_success_response(data: Any) -> Dict[str, Any]:
    """
    Create a successful API response.
    
    Args:
        data: Response data
        
    Returns:
        API Gateway response
    """
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        },
        'body': json.dumps(data, cls=DecimalEncoder)
    }


def create_error_response(status_code: int, message: str) -> Dict[str, Any]:
    """
    Create an error API response.
    
    Args:
        status_code: HTTP status code
        message: Error message
        
    Returns:
        API Gateway response
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        },
        'body': json.dumps({
            'error': {
                'code': status_code,
                'message': message,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        })
    }