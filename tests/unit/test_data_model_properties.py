"""
Property-based tests for DMARC data model serialization.

These tests validate universal properties that should hold for data model
serialization and deserialization operations.

**Feature: dmarc-analysis, Property 3: DMARC Report Parsing Round-Trip**
**Validates: Requirements 2.1, 2.2, 2.3, 2.5**
"""

import pytest
import json
from datetime import datetime, timezone
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from hypothesis.strategies import composite

from dmarc_lens.models.dmarc_models import (
    DMARCReport, ReportMetadata, PolicyPublished, PolicyEvaluated,
    AuthResult, DMARCRecord
)


# Test data generators
@composite
def valid_email_addresses(draw):
    """Generate valid email addresses."""
    local_part = draw(st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz0123456789',
        min_size=1, max_size=10
    ))
    
    domain_part = draw(st.sampled_from([
        'example.com', 'test.org', 'sample.net', 'demo.co.uk'
    ]))
    
    return f"{local_part}@{domain_part}"


@composite
def valid_domains(draw):
    """Generate valid domain names."""
    return draw(st.sampled_from([
        'example.com', 'test.org', 'sample.net', 'demo.co.uk', 'company.com'
    ]))


@composite
def valid_ip_addresses(draw):
    """Generate valid IP addresses."""
    return draw(st.sampled_from([
        '192.168.1.1', '10.0.0.1', '203.0.113.1', '198.51.100.1',
        '172.16.0.1', '127.0.0.1', '8.8.8.8', '1.1.1.1'
    ]))


@composite
def valid_datetimes(draw):
    """Generate valid datetime objects."""
    # Generate timestamps between 2020 and 2025
    timestamp = draw(st.integers(min_value=1577836800, max_value=1735689600))
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=None)


@composite
def report_metadata_strategy(draw):
    """Generate valid ReportMetadata instances."""
    begin_time = draw(valid_datetimes())
    # Ensure end time is after begin time
    end_timestamp = begin_time.timestamp() + draw(st.integers(min_value=3600, max_value=86400))
    end_time = datetime.fromtimestamp(end_timestamp)
    
    return ReportMetadata(
        org_name=draw(st.sampled_from(['Example Corp', 'Test Org', 'Sample Inc', 'Demo Company'])),
        email=draw(valid_email_addresses()),
        report_id=draw(st.text(alphabet='0123456789abcdef', min_size=5, max_size=15)),
        date_range_begin=begin_time,
        date_range_end=end_time,
        extra_contact_info=draw(st.one_of(st.none(), st.text(min_size=1, max_size=50)))
    )


@composite
def policy_published_strategy(draw):
    """Generate valid PolicyPublished instances."""
    return PolicyPublished(
        domain=draw(valid_domains()),
        p=draw(st.sampled_from(['none', 'quarantine', 'reject'])),
        sp=draw(st.one_of(st.none(), st.sampled_from(['none', 'quarantine', 'reject']))),
        pct=draw(st.integers(min_value=0, max_value=100)),
        adkim=draw(st.one_of(st.none(), st.sampled_from(['r', 's']))),
        aspf=draw(st.one_of(st.none(), st.sampled_from(['r', 's'])))
    )


@composite
def policy_evaluated_strategy(draw):
    """Generate valid PolicyEvaluated instances."""
    return PolicyEvaluated(
        disposition=draw(st.sampled_from(['none', 'quarantine', 'reject'])),
        dkim=draw(st.sampled_from(['pass', 'fail'])),
        spf=draw(st.sampled_from(['pass', 'fail'])),
        reason=draw(st.one_of(
            st.none(),
            st.lists(st.sampled_from(['forwarded', 'sampled_out', 'trusted_forwarder']), min_size=1, max_size=3)
        ))
    )


@composite
def auth_result_strategy(draw):
    """Generate valid AuthResult instances."""
    return AuthResult(
        domain=draw(valid_domains()),
        result=draw(st.sampled_from(['pass', 'fail', 'neutral', 'policy', 'temperror', 'permerror'])),
        selector=draw(st.one_of(st.none(), st.text(alphabet='abcdefghijklmnopqrstuvwxyz', min_size=1, max_size=10)))
    )


@composite
def dmarc_record_strategy(draw):
    """Generate valid DMARCRecord instances."""
    return DMARCRecord(
        source_ip=draw(valid_ip_addresses()),
        count=draw(st.integers(min_value=1, max_value=1000)),
        policy_evaluated=draw(policy_evaluated_strategy()),
        header_from=draw(valid_domains()),
        dkim_results=draw(st.lists(auth_result_strategy(), min_size=0, max_size=3)),
        spf_results=draw(st.lists(auth_result_strategy(), min_size=0, max_size=3))
    )


@composite
def dmarc_report_strategy(draw):
    """Generate valid DMARCReport instances."""
    return DMARCReport(
        metadata=draw(report_metadata_strategy()),
        policy_published=draw(policy_published_strategy()),
        records=draw(st.lists(dmarc_record_strategy(), min_size=1, max_size=5))
    )


class TestDMARCReportSerialization:
    """
    Property 3: DMARC Report Parsing Round-Trip
    **Validates: Requirements 2.1, 2.2, 2.3, 2.5**
    """
    
    @given(dmarc_report_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_dmarc_report_dict_round_trip(self, dmarc_report):
        """
        **Feature: dmarc-analysis, Property 3: DMARC Report Parsing Round-Trip**
        
        For any valid DMARC report, converting to dictionary and back should
        preserve all essential report information.
        """
        # Convert to dictionary
        report_dict = dmarc_report.to_dict()
        
        # Verify dictionary structure
        assert isinstance(report_dict, dict)
        assert 'metadata' in report_dict
        assert 'policy_published' in report_dict
        assert 'records' in report_dict
        
        # Convert back to DMARCReport
        reconstructed_report = DMARCReport.from_dict(report_dict)
        
        # Verify essential metadata is preserved
        assert reconstructed_report.metadata.org_name == dmarc_report.metadata.org_name
        assert reconstructed_report.metadata.email == dmarc_report.metadata.email
        assert reconstructed_report.metadata.report_id == dmarc_report.metadata.report_id
        assert reconstructed_report.metadata.date_range_begin == dmarc_report.metadata.date_range_begin
        assert reconstructed_report.metadata.date_range_end == dmarc_report.metadata.date_range_end
        assert reconstructed_report.metadata.extra_contact_info == dmarc_report.metadata.extra_contact_info
        
        # Verify policy information is preserved
        assert reconstructed_report.policy_published.domain == dmarc_report.policy_published.domain
        assert reconstructed_report.policy_published.p == dmarc_report.policy_published.p
        assert reconstructed_report.policy_published.sp == dmarc_report.policy_published.sp
        assert reconstructed_report.policy_published.pct == dmarc_report.policy_published.pct
        assert reconstructed_report.policy_published.adkim == dmarc_report.policy_published.adkim
        assert reconstructed_report.policy_published.aspf == dmarc_report.policy_published.aspf
        
        # Verify record count is preserved
        assert len(reconstructed_report.records) == len(dmarc_report.records)
        
        # Verify each record is preserved
        for orig_record, recon_record in zip(dmarc_report.records, reconstructed_report.records):
            assert recon_record.source_ip == orig_record.source_ip
            assert recon_record.count == orig_record.count
            assert recon_record.header_from == orig_record.header_from
            
            # Verify policy evaluation
            assert recon_record.policy_evaluated.disposition == orig_record.policy_evaluated.disposition
            assert recon_record.policy_evaluated.dkim == orig_record.policy_evaluated.dkim
            assert recon_record.policy_evaluated.spf == orig_record.policy_evaluated.spf
            assert recon_record.policy_evaluated.reason == orig_record.policy_evaluated.reason
            
            # Verify authentication results
            assert len(recon_record.dkim_results) == len(orig_record.dkim_results)
            assert len(recon_record.spf_results) == len(orig_record.spf_results)
            
            for orig_dkim, recon_dkim in zip(orig_record.dkim_results, recon_record.dkim_results):
                assert recon_dkim.domain == orig_dkim.domain
                assert recon_dkim.result == orig_dkim.result
                assert recon_dkim.selector == orig_dkim.selector
            
            for orig_spf, recon_spf in zip(orig_record.spf_results, recon_record.spf_results):
                assert recon_spf.domain == orig_spf.domain
                assert recon_spf.result == orig_spf.result
                assert recon_spf.selector == orig_spf.selector
    
    @given(dmarc_report_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_dmarc_report_json_round_trip(self, dmarc_report):
        """
        **Feature: dmarc-analysis, Property 3: DMARC Report Parsing Round-Trip**
        
        For any valid DMARC report, converting to JSON and back should
        preserve all essential report information.
        """
        # Convert to JSON
        json_str = dmarc_report.to_json()
        
        # Verify JSON is valid
        assert isinstance(json_str, str)
        assert len(json_str) > 0
        
        # Verify it's valid JSON
        parsed_json = json.loads(json_str)
        assert isinstance(parsed_json, dict)
        
        # Convert back to DMARCReport
        reconstructed_report = DMARCReport.from_json(json_str)
        
        # Verify essential data is preserved (same checks as dict test)
        assert reconstructed_report.metadata.org_name == dmarc_report.metadata.org_name
        assert reconstructed_report.metadata.email == dmarc_report.metadata.email
        assert reconstructed_report.metadata.report_id == dmarc_report.metadata.report_id
        assert reconstructed_report.policy_published.domain == dmarc_report.policy_published.domain
        assert len(reconstructed_report.records) == len(dmarc_report.records)
        
        # Verify calculated properties are preserved
        assert reconstructed_report.get_total_messages() == dmarc_report.get_total_messages()
        assert abs(reconstructed_report.get_alignment_rate() - dmarc_report.get_alignment_rate()) < 0.01
        assert set(reconstructed_report.get_source_ips()) == set(dmarc_report.get_source_ips())
    
    @given(dmarc_report_strategy())
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_serialization_preserves_business_logic(self, dmarc_report):
        """
        **Feature: dmarc-analysis, Property 3: DMARC Report Parsing Round-Trip**
        
        For any valid DMARC report, serialization and deserialization should
        preserve business logic calculations and derived properties.
        """
        # Get original calculated values
        original_total = dmarc_report.get_total_messages()
        original_alignment_rate = dmarc_report.get_alignment_rate()
        original_source_ips = dmarc_report.get_source_ips()
        original_summary = dmarc_report.get_summary_stats()
        
        # Round trip through JSON
        json_str = dmarc_report.to_json()
        reconstructed_report = DMARCReport.from_json(json_str)
        
        # Verify calculated values are preserved
        assert reconstructed_report.get_total_messages() == original_total
        assert abs(reconstructed_report.get_alignment_rate() - original_alignment_rate) < 0.01
        assert set(reconstructed_report.get_source_ips()) == set(original_source_ips)
        
        # Verify summary statistics are preserved
        reconstructed_summary = reconstructed_report.get_summary_stats()
        assert reconstructed_summary['total_messages'] == original_summary['total_messages']
        assert abs(reconstructed_summary['alignment_rate'] - original_summary['alignment_rate']) < 0.01
        assert reconstructed_summary['unique_sources'] == original_summary['unique_sources']
        assert reconstructed_summary['domain'] == original_summary['domain']
        
        # Verify disposition breakdown is preserved
        assert reconstructed_summary['disposition_breakdown'] == original_summary['disposition_breakdown']
        
        # Verify individual record business logic
        for orig_record, recon_record in zip(dmarc_report.records, reconstructed_report.records):
            assert recon_record.is_dmarc_aligned() == orig_record.is_dmarc_aligned()
            
            orig_auth_summary = orig_record.get_authentication_summary()
            recon_auth_summary = recon_record.get_authentication_summary()
            
            assert recon_auth_summary['dmarc_aligned'] == orig_auth_summary['dmarc_aligned']
            assert recon_auth_summary['dkim_pass'] == orig_auth_summary['dkim_pass']
            assert recon_auth_summary['spf_pass'] == orig_auth_summary['spf_pass']
            assert recon_auth_summary['disposition'] == orig_auth_summary['disposition']
            assert recon_auth_summary['message_count'] == orig_auth_summary['message_count']
    
    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=20)
    def test_invalid_json_handling(self, invalid_json):
        """
        **Feature: dmarc-analysis, Property 3: DMARC Report Parsing Round-Trip**
        
        For any invalid JSON input, deserialization should fail gracefully
        with appropriate error messages.
        """
        # Filter out strings that might accidentally be valid JSON
        assume(not invalid_json.strip().startswith('{'))
        assume(not invalid_json.strip().startswith('['))
        assume('"' not in invalid_json or invalid_json.count('"') < 2)
        # Also filter out simple numbers and booleans that are valid JSON
        assume(invalid_json.strip() not in ['true', 'false', 'null'])
        assume(not invalid_json.strip().isdigit())
        assume(not (invalid_json.strip().startswith('-') and invalid_json.strip()[1:].isdigit()))
        
        # Invalid JSON should raise ValueError
        with pytest.raises(ValueError):
            DMARCReport.from_json(invalid_json)
    
    @given(st.one_of(
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.booleans(),
        st.none(),
        st.lists(st.text(), min_size=1, max_size=3),
        st.text()
    ))
    @settings(max_examples=20)
    def test_valid_json_non_dict_handling(self, non_dict_value):
        """
        **Feature: dmarc-analysis, Property 3: DMARC Report Parsing Round-Trip**
        
        For any valid JSON that's not a dictionary, deserialization should
        fail with appropriate error message.
        """
        json_str = json.dumps(non_dict_value)
        
        # Valid JSON that's not a dict should raise ValueError
        with pytest.raises(ValueError, match="JSON must represent a dictionary object"):
            DMARCReport.from_json(json_str)
    
    @given(st.dictionaries(
        keys=st.text(min_size=1, max_size=10),
        values=st.one_of(st.text(), st.integers(), st.booleans()),
        min_size=1,
        max_size=5
    ))
    @settings(max_examples=20)
    def test_invalid_dict_structure_handling(self, invalid_dict):
        """
        **Feature: dmarc-analysis, Property 3: DMARC Report Parsing Round-Trip**
        
        For any invalid dictionary structure, deserialization should fail
        gracefully with appropriate error messages.
        """
        # Ensure the dict doesn't accidentally have valid DMARC structure
        assume('metadata' not in invalid_dict)
        assume('policy_published' not in invalid_dict)
        assume('records' not in invalid_dict)
        
        # Invalid structure should raise ValueError
        with pytest.raises(ValueError, match="Invalid DMARC report data format"):
            DMARCReport.from_dict(invalid_dict)
    
    @given(dmarc_report_strategy())
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
    def test_serialization_idempotency(self, dmarc_report):
        """
        **Feature: dmarc-analysis, Property 3: DMARC Report Parsing Round-Trip**
        
        For any valid DMARC report, multiple serialization operations should
        produce identical results (idempotency).
        """
        # Serialize multiple times
        json_str1 = dmarc_report.to_json()
        json_str2 = dmarc_report.to_json()
        
        # Results should be identical
        assert json_str1 == json_str2
        
        # Dictionary serialization should also be idempotent
        dict1 = dmarc_report.to_dict()
        dict2 = dmarc_report.to_dict()
        
        assert dict1 == dict2
        
        # Round trip should also be idempotent
        reconstructed1 = DMARCReport.from_json(json_str1)
        reconstructed2 = DMARCReport.from_json(json_str2)
        
        # Both reconstructed reports should serialize to the same result
        assert reconstructed1.to_json() == reconstructed2.to_json()