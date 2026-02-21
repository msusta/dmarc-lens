"""
Property-based tests for DMARC analysis functionality.

These tests validate universal properties that should hold across all valid
inputs for authentication success rate calculations, analysis completeness,
and security issue detection.

**Feature: dmarc-analysis, Property 5: Authentication Success Rate Calculation**
**Feature: dmarc-analysis, Property 6: Analysis Data Completeness**
**Feature: dmarc-analysis, Property 7: Security Issue Detection**
**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from hypothesis.strategies import composite
from collections import defaultdict

from dmarc_lens.lambda_functions.analysis_engine import (
    calculate_authentication_stats, analyze_failures, detect_security_issues,
    generate_recommendations, analyze_domain
)


# Test data generators
@composite
def dmarc_report_record(draw):
    """Generate a single DMARC report record for testing."""
    return {
        'report_id': draw(st.text(alphabet='0123456789', min_size=5, max_size=10)),
        'record_id': draw(st.text(alphabet='0123456789', min_size=5, max_size=15)),
        'domain': draw(st.sampled_from(['example.com', 'test.org', 'sample.net'])),
        'source_ip': draw(st.sampled_from(['192.168.1.1', '10.0.0.1', '203.0.113.1'])),
        'count': draw(st.integers(min_value=1, max_value=100)),
        'disposition': draw(st.sampled_from(['none', 'quarantine', 'reject'])),
        'dkim_result': draw(st.sampled_from(['pass', 'fail'])),
        'spf_result': draw(st.sampled_from(['pass', 'fail'])),
        'header_from': draw(st.sampled_from(['example.com', 'test.org', 'sample.net'])),
        'date_range_begin': 1600000000,
        'date_range_end': 1600086400,
        'org_name': draw(st.sampled_from(['Example Corp', 'Test Org', 'Sample Inc'])),
        'email': draw(st.sampled_from(['report@example.com', 'noreply@test.org']))
    }


@composite
def dmarc_report_dataset(draw):
    """Generate a dataset of DMARC report records."""
    # Generate 5-20 records
    num_records = draw(st.integers(min_value=5, max_value=20))
    records = []
    
    # Ensure we have some variety in the dataset
    domain = draw(st.sampled_from(['example.com', 'test.org', 'sample.net']))
    
    for _ in range(num_records):
        record = draw(dmarc_report_record())
        record['domain'] = domain  # Keep domain consistent
        records.append(record)
    
    return records


@composite
def authentication_results_dataset(draw):
    """Generate dataset with specific authentication patterns."""
    num_records = draw(st.integers(min_value=5, max_value=15))
    records = []
    
    # Generate records with controlled authentication results
    for _ in range(num_records):
        # Bias towards having some passing and some failing records
        auth_pattern = draw(st.sampled_from([
            ('pass', 'pass'),   # Both pass (DMARC aligned)
            ('pass', 'fail'),   # Only DKIM passes
            ('fail', 'pass'),   # Only SPF passes
            ('fail', 'fail')    # Both fail
        ]))
        
        record = draw(dmarc_report_record())
        record['dkim_result'] = auth_pattern[0]
        record['spf_result'] = auth_pattern[1]
        records.append(record)
    
    return records


class TestAuthenticationSuccessRateCalculation:
    """
    Property 5: Authentication Success Rate Calculation
    **Validates: Requirements 3.1**
    """
    
    @given(authentication_results_dataset())
    @settings(max_examples=50)
    def test_success_rate_calculation_accuracy(self, records):
        """
        **Feature: dmarc-analysis, Property 5: Authentication Success Rate Calculation**
        
        For any set of DMARC records, the calculated authentication success rate
        should equal the percentage of records where both DKIM and SPF pass.
        """
        # Calculate expected values manually
        total_messages = sum(int(record['count']) for record in records)
        assume(total_messages > 0)  # Skip empty datasets
        
        dmarc_aligned_messages = sum(
            int(record['count']) for record in records
            if record['dkim_result'] == 'pass' or record['spf_result'] == 'pass'
        )
        
        dkim_pass_messages = sum(
            int(record['count']) for record in records
            if record['dkim_result'] == 'pass'
        )
        
        spf_pass_messages = sum(
            int(record['count']) for record in records
            if record['spf_result'] == 'pass'
        )
        
        expected_dmarc_rate = (dmarc_aligned_messages / total_messages) * 100
        expected_dkim_rate = (dkim_pass_messages / total_messages) * 100
        expected_spf_rate = (spf_pass_messages / total_messages) * 100
        
        # Calculate using the function
        auth_stats = calculate_authentication_stats(records)
        
        # Verify calculations match expectations
        assert auth_stats['total_messages'] == total_messages
        assert auth_stats['dmarc_aligned_messages'] == dmarc_aligned_messages
        assert auth_stats['dkim_pass_messages'] == dkim_pass_messages
        assert auth_stats['spf_pass_messages'] == spf_pass_messages
        
        # Allow for small floating point differences
        assert abs(auth_stats['dmarc_success_rate'] - expected_dmarc_rate) < 0.01
        assert abs(auth_stats['dkim_success_rate'] - expected_dkim_rate) < 0.01
        assert abs(auth_stats['spf_success_rate'] - expected_spf_rate) < 0.01
        
        # Verify rates are within valid range
        assert 0 <= auth_stats['dmarc_success_rate'] <= 100
        assert 0 <= auth_stats['dkim_success_rate'] <= 100
        assert 0 <= auth_stats['spf_success_rate'] <= 100
    
    @given(st.lists(dmarc_report_record(), min_size=1, max_size=20))
    def test_disposition_breakdown_accuracy(self, records):
        """
        **Feature: dmarc-analysis, Property 5: Authentication Success Rate Calculation**
        
        For any set of records, the disposition breakdown should accurately
        count messages by their DMARC policy disposition.
        """
        # Calculate expected disposition counts
        expected_dispositions = defaultdict(int)
        for record in records:
            disposition = record['disposition']
            count = int(record['count'])
            expected_dispositions[disposition] += count
        
        # Calculate using the function
        auth_stats = calculate_authentication_stats(records)
        actual_dispositions = auth_stats['disposition_breakdown']
        
        # Verify all dispositions are accounted for
        for disposition, expected_count in expected_dispositions.items():
            assert actual_dispositions.get(disposition, 0) == expected_count
        
        # Verify total counts match
        total_expected = sum(expected_dispositions.values())
        total_actual = sum(actual_dispositions.values())
        assert total_expected == total_actual == auth_stats['total_messages']
    
    def test_empty_dataset_handling(self):
        """
        **Feature: dmarc-analysis, Property 5: Authentication Success Rate Calculation**
        
        For empty datasets, all rates should be 0 and counts should be 0.
        """
        auth_stats = calculate_authentication_stats([])
        
        assert auth_stats['total_messages'] == 0
        assert auth_stats['dmarc_success_rate'] == 0.0
        assert auth_stats['dkim_success_rate'] == 0.0
        assert auth_stats['spf_success_rate'] == 0.0
        assert auth_stats['dmarc_aligned_messages'] == 0
        assert auth_stats['dkim_pass_messages'] == 0
        assert auth_stats['spf_pass_messages'] == 0
        assert auth_stats['disposition_breakdown'] == {}


class TestAnalysisDataCompleteness:
    """
    Property 6: Analysis Data Completeness
    **Validates: Requirements 3.2, 3.3, 3.4**
    """
    
    @given(dmarc_report_dataset())
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow])
    def test_failure_analysis_completeness(self, records):
        """
        **Feature: dmarc-analysis, Property 6: Analysis Data Completeness**
        
        For any completed analysis, failure analysis should include all
        required fields and categorize all failure types.
        """
        failure_analysis = analyze_failures(records)
        
        # Verify required fields are present
        required_fields = [
            'failure_sources', 'failure_patterns', 'top_failing_ips', 
            'total_failing_messages'
        ]
        for field in required_fields:
            assert field in failure_analysis
        
        # Verify data types
        assert isinstance(failure_analysis['failure_sources'], dict)
        assert isinstance(failure_analysis['failure_patterns'], dict)
        assert isinstance(failure_analysis['top_failing_ips'], list)
        assert isinstance(failure_analysis['total_failing_messages'], int)
        
        # Verify failure categorization is complete
        total_messages = sum(int(record['count']) for record in records)
        categorized_failures = failure_analysis['total_failing_messages']
        
        # All failures should be categorized
        assert categorized_failures >= 0
        assert categorized_failures <= total_messages
        
        # Top failing IPs should be properly formatted
        for ip_info in failure_analysis['top_failing_ips']:
            assert 'ip' in ip_info
            assert 'count' in ip_info
            assert isinstance(ip_info['count'], int)
            assert ip_info['count'] > 0
    
    @given(dmarc_report_dataset())
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow])
    def test_recommendations_completeness(self, records):
        """
        **Feature: dmarc-analysis, Property 6: Analysis Data Completeness**
        
        For any analysis, generated recommendations should be complete
        and properly structured.
        """
        # Generate required analysis components
        auth_stats = calculate_authentication_stats(records)
        failure_analysis = analyze_failures(records)
        security_issues = detect_security_issues(records, auth_stats)
        
        recommendations = generate_recommendations(auth_stats, failure_analysis, security_issues)
        
        # Verify recommendations structure
        assert isinstance(recommendations, list)
        
        for recommendation in recommendations:
            # Verify required fields
            required_fields = ['type', 'priority', 'title', 'description', 'action_items']
            for field in required_fields:
                assert field in recommendation, f"Missing field: {field}"
            
            # Verify field types and values
            assert isinstance(recommendation['type'], str)
            assert recommendation['priority'] in ['low', 'medium', 'high']
            assert isinstance(recommendation['title'], str)
            assert isinstance(recommendation['description'], str)
            assert isinstance(recommendation['action_items'], list)
            
            # Verify action items are non-empty strings
            for action in recommendation['action_items']:
                assert isinstance(action, str)
                assert len(action.strip()) > 0
    
    @given(dmarc_report_dataset())
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow])
    def test_analysis_output_consistency(self, records):
        """
        **Feature: dmarc-analysis, Property 6: Analysis Data Completeness**
        
        For any dataset, all analysis components should be consistent
        with each other and the input data.
        """
        auth_stats = calculate_authentication_stats(records)
        failure_analysis = analyze_failures(records)
        
        # Total messages should be consistent across analyses
        total_from_auth = auth_stats['total_messages']
        
        # Failure analysis total should not exceed auth stats total
        total_failures = failure_analysis['total_failing_messages']
        assert total_failures <= total_from_auth
        
        # Success count should not exceed total
        success_messages = auth_stats['dmarc_aligned_messages']
        assert success_messages <= total_from_auth
        
        # Disposition breakdown should sum to total
        disposition_total = sum(auth_stats['disposition_breakdown'].values())
        assert disposition_total == total_from_auth


class TestSecurityIssueDetection:
    """
    Property 7: Security Issue Detection
    **Validates: Requirements 3.5**
    """
    
    @given(authentication_results_dataset())
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow])
    def test_low_success_rate_detection(self, records):
        """
        **Feature: dmarc-analysis, Property 7: Security Issue Detection**
        
        For any analysis data with low success rates, appropriate security
        issues should be flagged.
        """
        auth_stats = calculate_authentication_stats(records)
        security_issues = detect_security_issues(records, auth_stats)
        
        # Check if low success rate issue is detected when appropriate
        low_rate_issues = [
            issue for issue in security_issues 
            if issue['type'] == 'low_dmarc_success_rate'
        ]
        
        if auth_stats['dmarc_success_rate'] < 50:
            # Should detect low success rate
            assert len(low_rate_issues) > 0
            
            issue = low_rate_issues[0]
            assert issue['severity'] in ['medium', 'high']
            assert 'description' in issue
            assert 'metric' in issue
            assert issue['metric'] == auth_stats['dmarc_success_rate']
        else:
            # Should not flag high success rates as issues
            assert len(low_rate_issues) == 0
    
    @given(st.lists(dmarc_report_record(), min_size=5, max_size=20))
    def test_policy_violation_detection(self, records):
        """
        **Feature: dmarc-analysis, Property 7: Security Issue Detection**
        
        For any dataset with policy violations (quarantine/reject), 
        appropriate security issues should be detected.
        """
        # Force some policy violations
        for i, record in enumerate(records[:2]):
            if i == 0:
                record['disposition'] = 'quarantine'
            else:
                record['disposition'] = 'reject'
        
        auth_stats = calculate_authentication_stats(records)
        security_issues = detect_security_issues(records, auth_stats)
        
        # Should detect policy violations
        violation_issues = [
            issue for issue in security_issues 
            if issue['type'] == 'policy_violations'
        ]
        
        assert len(violation_issues) > 0
        
        issue = violation_issues[0]
        assert issue['severity'] in ['medium', 'high']
        assert 'quarantined' in issue
        assert 'rejected' in issue
        assert issue['quarantined'] >= 0
        assert issue['rejected'] >= 0
        assert issue['quarantined'] + issue['rejected'] > 0
    
    @given(dmarc_report_dataset())
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow])
    def test_security_issue_structure(self, records):
        """
        **Feature: dmarc-analysis, Property 7: Security Issue Detection**
        
        For any detected security issues, the structure should be complete
        and properly formatted.
        """
        auth_stats = calculate_authentication_stats(records)
        security_issues = detect_security_issues(records, auth_stats)
        
        # Verify structure of all detected issues
        for issue in security_issues:
            # Required fields
            required_fields = ['type', 'severity', 'description', 'metric']
            for field in required_fields:
                assert field in issue, f"Missing field: {field}"
            
            # Verify field values
            assert isinstance(issue['type'], str)
            assert issue['severity'] in ['low', 'medium', 'high']
            assert isinstance(issue['description'], str)
            assert len(issue['description']) > 0
            
            # Metric should be numeric
            assert isinstance(issue['metric'], (int, float))
            
            # Type-specific validations
            if issue['type'] == 'low_dmarc_success_rate':
                assert 0 <= issue['metric'] <= 100
            elif issue['type'] == 'suspicious_ip_volume':
                assert 'ip_address' in issue
                assert isinstance(issue['ip_address'], str)
            elif issue['type'] == 'policy_violations':
                assert 'quarantined' in issue
                assert 'rejected' in issue


class TestAnalysisIntegration:
    """Integration tests for complete analysis pipeline."""
    
    @given(dmarc_report_dataset())
    @settings(max_examples=5, suppress_health_check=[HealthCheck.too_slow])
    def test_complete_analysis_pipeline_consistency(self, records):
        """
        **Feature: dmarc-analysis, Property 5, 6, 7: Complete Analysis Pipeline**
        
        For any valid dataset, the complete analysis pipeline should
        maintain consistency across all analysis components.
        """
        assume(len(records) > 0)
        
        with patch('dmarc_lens.lambda_functions.analysis_engine.dynamodb') as mock_dynamodb:
            # Mock DynamoDB responses
            mock_reports_table = Mock()
            mock_analysis_table = Mock()
            
            # Mock scan response for getting reports
            mock_reports_table.scan.return_value = {
                'Items': records,
                'Count': len(records)
            }
            
            # Mock get_item response for trend analysis (no previous data)
            mock_analysis_table.get_item.return_value = {}
            
            # Mock put_item for storing results
            mock_analysis_table.put_item.return_value = {}
            
            def table_selector(table_name):
                if 'reports' in table_name:
                    return mock_reports_table
                else:
                    return mock_analysis_table
            
            mock_dynamodb.Table.side_effect = table_selector
            
            # Run complete analysis
            domain = records[0]['domain']
            
            # Should not raise any exceptions
            analyze_domain(domain)
            
            # Verify DynamoDB interactions
            mock_reports_table.scan.assert_called()
            mock_analysis_table.put_item.assert_called()
            
            # Verify stored data structure
            stored_call = mock_analysis_table.put_item.call_args
            stored_item = stored_call[1]['Item']
            
            # Verify required fields are present
            required_fields = [
                'domain', 'analysis_date', 'total_messages', 'auth_success_rate',
                'failure_analysis', 'security_issues', 'recommendations'
            ]
            for field in required_fields:
                assert field in stored_item
            
            # Verify data consistency
            assert stored_item['domain'] == domain
            assert isinstance(stored_item['total_messages'], int)
            assert stored_item['total_messages'] >= 0