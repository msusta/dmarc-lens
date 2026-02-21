"""
DMARC Analysis Engine Lambda Function.

This Lambda function processes DynamoDB Streams events from the Reports table,
calculates authentication success rates, identifies patterns, and generates
security insights and recommendations.
"""

import json
import logging
import boto3
import traceback
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict, Counter
from decimal import Decimal
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')

# Environment variables (set by CDK)
import os
ANALYSIS_TABLE_NAME = os.getenv('ANALYSIS_TABLE_NAME', 'dmarc-analysis')
REPORTS_TABLE_NAME = os.getenv('REPORTS_TABLE_NAME', 'dmarc-reports')


class AnalysisError(Exception):
    """Exception raised when analysis processing fails."""
    pass


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for processing DynamoDB Streams events.
    
    Args:
        event: DynamoDB Streams event containing record changes
        context: Lambda context object
        
    Returns:
        Response dictionary with processing results
    """
    try:
        logger.info(f"Processing DynamoDB Streams event: {json.dumps(event, default=str)}")
        
        # Process each record in the stream
        domains_to_analyze = set()
        records_processed = 0
        errors = []
        
        for record in event.get('Records', []):
            try:
                # Only process INSERT and MODIFY events
                event_name = record.get('eventName')
                if event_name not in ['INSERT', 'MODIFY']:
                    continue
                
                # Extract domain from the record
                dynamodb_record = record.get('dynamodb', {})
                new_image = dynamodb_record.get('NewImage', {})
                
                if 'domain' in new_image:
                    domain = new_image['domain']['S']
                    domains_to_analyze.add(domain)
                    records_processed += 1
                    
            except Exception as e:
                error_msg = f"Failed to process stream record: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        # Analyze each affected domain
        analyses_completed = 0
        for domain in domains_to_analyze:
            try:
                logger.info(f"Analyzing domain: {domain}")
                analyze_domain(domain)
                analyses_completed += 1
                
            except Exception as e:
                error_msg = f"Failed to analyze domain {domain}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        # Return processing summary
        response = {
            'statusCode': 200,
            'body': {
                'records_processed': records_processed,
                'analyses_completed': analyses_completed,
                'domains_analyzed': list(domains_to_analyze),
                'errors': errors,
                'success': len(errors) == 0
            }
        }
        
        logger.info(f"Analysis complete: {response}")
        return response
        
    except Exception as e:
        logger.error(f"Lambda handler failed: {str(e)}")
        logger.error(traceback.format_exc())
        
        return {
            'statusCode': 500,
            'body': {
                'error': str(e),
                'success': False
            }
        }


def analyze_domain(domain: str) -> None:
    """
    Perform comprehensive analysis for a specific domain.
    
    Args:
        domain: Domain to analyze
    """
    try:
        # Get recent reports for the domain (last 30 days)
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=30)
        
        reports = get_domain_reports(domain, start_date, end_date)
        
        if not reports:
            logger.info(f"No recent reports found for domain: {domain}")
            return
        
        # Calculate authentication success rates
        auth_stats = calculate_authentication_stats(reports)
        
        # Identify failure sources and patterns
        failure_analysis = analyze_failures(reports)
        
        # Detect suspicious patterns
        security_issues = detect_security_issues(reports, auth_stats)
        
        # Generate recommendations
        recommendations = generate_recommendations(auth_stats, failure_analysis, security_issues)
        
        # Calculate trend data
        trend_data = calculate_trends(domain, reports)
        
        # Store analysis results
        store_analysis_results(
            domain=domain,
            auth_stats=auth_stats,
            failure_analysis=failure_analysis,
            security_issues=security_issues,
            recommendations=recommendations,
            trend_data=trend_data,
            analysis_date=end_date.strftime('%Y-%m-%d')
        )
        
        logger.info(f"Analysis completed for domain: {domain}")
        
    except Exception as e:
        logger.error(f"Domain analysis failed for {domain}: {e}")
        raise AnalysisError(f"Analysis failed: {e}") from e


def get_domain_reports(domain: str, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
    """
    Retrieve DMARC reports for a domain within a date range.
    
    Args:
        domain: Domain to query
        start_date: Start of date range
        end_date: End of date range
        
    Returns:
        List of report records
    """
    try:
        table = dynamodb.Table(REPORTS_TABLE_NAME)
        
        # Query reports by domain and date range
        start_timestamp = int(start_date.timestamp())
        end_timestamp = int(end_date.timestamp())
        
        response = table.scan(
            FilterExpression='#domain = :domain AND #date_begin BETWEEN :start_date AND :end_date',
            ExpressionAttributeNames={
                '#domain': 'domain',
                '#date_begin': 'date_range_begin'
            },
            ExpressionAttributeValues={
                ':domain': domain,
                ':start_date': start_timestamp,
                ':end_date': end_timestamp
            }
        )
        
        reports = response.get('Items', [])
        
        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = table.scan(
                FilterExpression='#domain = :domain AND #date_begin BETWEEN :start_date AND :end_date',
                ExpressionAttributeNames={
                    '#domain': 'domain',
                    '#date_begin': 'date_range_begin'
                },
                ExpressionAttributeValues={
                    ':domain': domain,
                    ':start_date': start_timestamp,
                    ':end_date': end_timestamp
                },
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            reports.extend(response.get('Items', []))
        
        logger.info(f"Retrieved {len(reports)} reports for domain {domain}")
        return reports
        
    except Exception as e:
        logger.error(f"Failed to retrieve reports for domain {domain}: {e}")
        raise


def calculate_authentication_stats(reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate authentication success rates and statistics.
    
    Args:
        reports: List of DMARC report records
        
    Returns:
        Dictionary containing authentication statistics
    """
    total_messages = 0
    dmarc_aligned_messages = 0
    dkim_pass_messages = 0
    spf_pass_messages = 0
    
    disposition_counts = defaultdict(int)
    
    for report in reports:
        count = int(report.get('count', 0))
        total_messages += count
        
        # Check DMARC alignment (DKIM or SPF must pass per DMARC spec)
        dkim_result = report.get('dkim_result', 'fail')
        spf_result = report.get('spf_result', 'fail')
        
        if dkim_result == 'pass':
            dkim_pass_messages += count
            
        if spf_result == 'pass':
            spf_pass_messages += count
            
        if dkim_result == 'pass' or spf_result == 'pass':
            dmarc_aligned_messages += count
        
        # Count dispositions
        disposition = report.get('disposition', 'none')
        disposition_counts[disposition] += count
    
    # Calculate percentages
    if total_messages > 0:
        dmarc_success_rate = (dmarc_aligned_messages / total_messages) * 100
        dkim_success_rate = (dkim_pass_messages / total_messages) * 100
        spf_success_rate = (spf_pass_messages / total_messages) * 100
    else:
        dmarc_success_rate = dkim_success_rate = spf_success_rate = 0.0
    
    return {
        'total_messages': total_messages,
        'dmarc_success_rate': round(dmarc_success_rate, 2),
        'dkim_success_rate': round(dkim_success_rate, 2),
        'spf_success_rate': round(spf_success_rate, 2),
        'dmarc_aligned_messages': dmarc_aligned_messages,
        'dkim_pass_messages': dkim_pass_messages,
        'spf_pass_messages': spf_pass_messages,
        'disposition_breakdown': dict(disposition_counts)
    }


def analyze_failures(reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze authentication failures to identify patterns and sources.
    
    Args:
        reports: List of DMARC report records
        
    Returns:
        Dictionary containing failure analysis
    """
    failure_sources = defaultdict(int)
    failure_patterns = defaultdict(int)
    top_failing_ips = Counter()
    
    for report in reports:
        count = int(report.get('count', 0))
        dkim_result = report.get('dkim_result', 'fail')
        spf_result = report.get('spf_result', 'fail')
        source_ip = report.get('source_ip', 'unknown')
        
        # Categorize failure types
        if dkim_result == 'fail' and spf_result == 'fail':
            failure_patterns['both_fail'] += count
            top_failing_ips[source_ip] += count
        elif dkim_result == 'fail':
            failure_patterns['dkim_fail'] += count
            failure_sources['dkim'] += count
        elif spf_result == 'fail':
            failure_patterns['spf_fail'] += count
            failure_sources['spf'] += count
    
    # Get top 10 failing IP addresses
    top_failing_ips_list = [
        {'ip': ip, 'count': count}
        for ip, count in top_failing_ips.most_common(10)
    ]
    
    return {
        'failure_sources': dict(failure_sources),
        'failure_patterns': dict(failure_patterns),
        'top_failing_ips': top_failing_ips_list,
        'total_failing_messages': sum(failure_patterns.values())
    }


def detect_security_issues(reports: List[Dict[str, Any]], auth_stats: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Detect potential security issues based on DMARC data patterns.
    
    Args:
        reports: List of DMARC report records
        auth_stats: Authentication statistics
        
    Returns:
        List of detected security issues
    """
    issues = []
    
    # Check for low DMARC success rate
    if auth_stats['dmarc_success_rate'] < 50:
        issues.append({
            'type': 'low_dmarc_success_rate',
            'severity': 'high' if auth_stats['dmarc_success_rate'] < 25 else 'medium',
            'description': f"DMARC success rate is {auth_stats['dmarc_success_rate']}%, indicating potential authentication issues",
            'metric': auth_stats['dmarc_success_rate']
        })
    
    # Check for suspicious IP patterns
    ip_counts = Counter()
    total_messages = 0
    
    for report in reports:
        count = int(report.get('count', 0))
        source_ip = report.get('source_ip', 'unknown')
        ip_counts[source_ip] += count
        total_messages += count
    
    # Flag IPs that send a disproportionate amount of mail
    for ip, count in ip_counts.most_common(5):
        percentage = (count / total_messages) * 100 if total_messages > 0 else 0
        
        if percentage > 30:  # Single IP sending >30% of mail
            issues.append({
                'type': 'suspicious_ip_volume',
                'severity': 'medium',
                'description': f"IP {ip} is sending {percentage:.1f}% of all mail for this domain",
                'metric': percentage,
                'ip_address': ip
            })
    
    # Check for policy violations
    disposition_counts = auth_stats.get('disposition_breakdown', {})
    quarantine_count = disposition_counts.get('quarantine', 0)
    reject_count = disposition_counts.get('reject', 0)
    
    if quarantine_count > 0 or reject_count > 0:
        total_violations = quarantine_count + reject_count
        violation_rate = (total_violations / total_messages) * 100 if total_messages > 0 else 0
        
        issues.append({
            'type': 'policy_violations',
            'severity': 'high' if reject_count > 0 else 'medium',
            'description': f"{total_violations} messages were quarantined or rejected ({violation_rate:.1f}%)",
            'metric': violation_rate,
            'quarantined': quarantine_count,
            'rejected': reject_count
        })
    
    return issues


def generate_recommendations(auth_stats: Dict[str, Any], failure_analysis: Dict[str, Any], 
                           security_issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Generate actionable recommendations based on analysis results.
    
    Args:
        auth_stats: Authentication statistics
        failure_analysis: Failure analysis results
        security_issues: Detected security issues
        
    Returns:
        List of recommendations
    """
    recommendations = []
    
    # DMARC success rate recommendations
    if auth_stats['dmarc_success_rate'] < 95:
        if auth_stats['dkim_success_rate'] < auth_stats['spf_success_rate']:
            recommendations.append({
                'type': 'dkim_improvement',
                'priority': 'high',
                'title': 'Improve DKIM Authentication',
                'description': 'DKIM success rate is lower than SPF. Review DKIM signing configuration and key management.',
                'action_items': [
                    'Verify DKIM keys are properly published in DNS',
                    'Check DKIM signing configuration on mail servers',
                    'Ensure DKIM key rotation is working correctly'
                ]
            })
        else:
            recommendations.append({
                'type': 'spf_improvement',
                'priority': 'high',
                'title': 'Improve SPF Authentication',
                'description': 'SPF success rate is lower than DKIM. Review SPF record configuration.',
                'action_items': [
                    'Review and update SPF record to include all legitimate sending sources',
                    'Check for SPF record syntax errors',
                    'Consider SPF record length and DNS lookup limits'
                ]
            })
    
    # Policy recommendations based on success rate
    if auth_stats['dmarc_success_rate'] > 95:
        recommendations.append({
            'type': 'policy_enforcement',
            'priority': 'medium',
            'title': 'Consider Stricter DMARC Policy',
            'description': 'High authentication success rate allows for stricter policy enforcement.',
            'action_items': [
                'Consider upgrading DMARC policy from "none" to "quarantine"',
                'Monitor for any legitimate mail issues after policy change',
                'Eventually consider "reject" policy for maximum protection'
            ]
        })
    
    # Security issue recommendations
    for issue in security_issues:
        if issue['type'] == 'suspicious_ip_volume':
            recommendations.append({
                'type': 'investigate_ip',
                'priority': 'medium',
                'title': f'Investigate High-Volume IP: {issue["ip_address"]}',
                'description': f'IP address is sending {issue["metric"]:.1f}% of domain mail.',
                'action_items': [
                    'Verify this IP is an authorized sender',
                    'Check if this represents a compromised system',
                    'Consider rate limiting if appropriate'
                ]
            })
        
        elif issue['type'] == 'policy_violations':
            recommendations.append({
                'type': 'policy_violations',
                'priority': 'high',
                'title': 'Address Policy Violations',
                'description': f'{issue["quarantined"] + issue["rejected"]} messages violated DMARC policy.',
                'action_items': [
                    'Investigate sources of policy violations',
                    'Determine if violations are from legitimate or malicious sources',
                    'Update authentication configuration if needed'
                ]
            })
    
    return recommendations


def calculate_trends(domain: str, current_reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate trend data by comparing with historical analysis.
    
    Args:
        domain: Domain being analyzed
        current_reports: Current period reports
        
    Returns:
        Dictionary containing trend information
    """
    try:
        # Get previous analysis for comparison
        table = dynamodb.Table(ANALYSIS_TABLE_NAME)
        
        # Look for analysis from 7 days ago
        previous_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')
        
        response = table.get_item(
            Key={
                'domain': domain,
                'analysis_date': previous_date
            }
        )
        
        trends = {
            'has_historical_data': False,
            'success_rate_trend': 'stable',
            'message_volume_trend': 'stable',
            'new_sources': 0
        }
        
        if 'Item' in response:
            previous_analysis = response['Item']
            trends['has_historical_data'] = True
            
            # Calculate success rate trend
            current_rate = sum(int(r.get('count', 0)) for r in current_reports 
                             if r.get('dkim_result') == 'pass' and r.get('spf_result') == 'pass')
            current_total = sum(int(r.get('count', 0)) for r in current_reports)
            current_success_rate = (current_rate / current_total * 100) if current_total > 0 else 0
            
            previous_success_rate = float(previous_analysis.get('auth_success_rate', 0))
            
            if current_success_rate > previous_success_rate + 5:
                trends['success_rate_trend'] = 'improving'
            elif current_success_rate < previous_success_rate - 5:
                trends['success_rate_trend'] = 'declining'
            
            # Calculate volume trend
            previous_total = int(previous_analysis.get('total_messages', 0))
            
            if current_total > previous_total * 1.2:
                trends['message_volume_trend'] = 'increasing'
            elif current_total < previous_total * 0.8:
                trends['message_volume_trend'] = 'decreasing'
        
        return trends
        
    except Exception as e:
        logger.warning(f"Failed to calculate trends for {domain}: {e}")
        return {
            'has_historical_data': False,
            'success_rate_trend': 'unknown',
            'message_volume_trend': 'unknown',
            'new_sources': 0
        }


def store_analysis_results(domain: str, auth_stats: Dict[str, Any], 
                         failure_analysis: Dict[str, Any], security_issues: List[Dict[str, Any]],
                         recommendations: List[Dict[str, Any]], trend_data: Dict[str, Any],
                         analysis_date: str) -> None:
    """
    Store analysis results in DynamoDB.
    
    Args:
        domain: Domain that was analyzed
        auth_stats: Authentication statistics
        failure_analysis: Failure analysis results
        security_issues: Detected security issues
        recommendations: Generated recommendations
        trend_data: Trend information
        analysis_date: Date of analysis (YYYY-MM-DD)
    """
    try:
        table = dynamodb.Table(ANALYSIS_TABLE_NAME)
        
        # Convert float values to Decimal for DynamoDB
        def convert_floats(obj):
            if isinstance(obj, dict):
                return {k: convert_floats(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_floats(item) for item in obj]
            elif isinstance(obj, float):
                return Decimal(str(obj))
            else:
                return obj
        
        item = {
            'domain': domain,
            'analysis_date': analysis_date,
            'total_messages': auth_stats['total_messages'],
            'auth_success_rate': Decimal(str(auth_stats['dmarc_success_rate'])),
            'dkim_success_rate': Decimal(str(auth_stats['dkim_success_rate'])),
            'spf_success_rate': Decimal(str(auth_stats['spf_success_rate'])),
            'disposition_breakdown': convert_floats(auth_stats['disposition_breakdown']),
            'failure_analysis': convert_floats(failure_analysis),
            'security_issues': convert_floats(security_issues),
            'recommendations': convert_floats(recommendations),
            'trend_data': convert_floats(trend_data),
            'analyzed_at': int(datetime.now(timezone.utc).timestamp()),
            'analysis_version': '1.0'
        }
        
        table.put_item(Item=item)
        logger.info(f"Stored analysis results for domain: {domain}")
        
    except Exception as e:
        logger.error(f"Failed to store analysis results for {domain}: {e}")
        raise AnalysisError(f"Failed to store analysis: {e}") from e