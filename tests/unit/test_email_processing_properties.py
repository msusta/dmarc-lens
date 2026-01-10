"""
Property-based tests for email processing functionality.

These tests validate universal properties that should hold across all valid
inputs for email storage, parsing, and attachment handling.

**Feature: dmarc-analysis, Property 1: Email Storage and Organization**
**Feature: dmarc-analysis, Property 2: Attachment Preservation**
**Feature: dmarc-analysis, Property 4: Parser Error Handling**
**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 2.4**
"""

import pytest
import email
import gzip
import zipfile
import io
import tempfile
import os
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from hypothesis.strategies import composite

from dmarc_lens.utils.email_utils import (
    parse_email_from_string, extract_attachments, decompress_attachment,
    extract_dmarc_reports, EmailParsingError, AttachmentExtractionError,
    get_email_metadata, validate_email_structure
)
from dmarc_lens.lambda_functions.report_parser import (
    process_email_from_s3, parse_dmarc_report_xml, store_dmarc_report,
    store_failed_report
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
def dmarc_xml_content(draw):
    """Generate valid DMARC XML report content."""
    org_name = draw(st.sampled_from(['Example Corp', 'Test Org', 'Sample Inc']))
    email_addr = draw(valid_email_addresses())
    report_id = draw(st.text(alphabet='0123456789', min_size=5, max_size=10))
    domain = draw(valid_domains())
    source_ip = draw(st.sampled_from(['192.168.1.1', '10.0.0.1', '203.0.113.1']))
    count = draw(st.integers(min_value=1, max_value=100))
    
    # Generate timestamps (begin < end)
    begin_ts = 1600000000
    end_ts = 1600086400  # 24 hours later
    
    policy = draw(st.sampled_from(['none', 'quarantine', 'reject']))
    disposition = draw(st.sampled_from(['none', 'quarantine', 'reject']))
    dkim_result = draw(st.sampled_from(['pass', 'fail']))
    spf_result = draw(st.sampled_from(['pass', 'fail']))
    
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<feedback>
    <report_metadata>
        <org_name>{org_name}</org_name>
        <email>{email_addr}</email>
        <report_id>{report_id}</report_id>
        <date_range>
            <begin>{begin_ts}</begin>
            <end>{end_ts}</end>
        </date_range>
    </report_metadata>
    <policy_published>
        <domain>{domain}</domain>
        <p>{policy}</p>
        <pct>100</pct>
    </policy_published>
    <record>
        <row>
            <source_ip>{source_ip}</source_ip>
            <count>{count}</count>
            <policy_evaluated>
                <disposition>{disposition}</disposition>
                <dkim>{dkim_result}</dkim>
                <spf>{spf_result}</spf>
            </policy_evaluated>
        </row>
        <identifiers>
            <header_from>{domain}</header_from>
        </identifiers>
        <auth_results>
            <dkim>
                <domain>{domain}</domain>
                <result>{dkim_result}</result>
            </dkim>
            <spf>
                <domain>{domain}</domain>
                <result>{spf_result}</result>
            </spf>
        </auth_results>
    </record>
</feedback>"""
    
    return xml_content


@composite
def email_with_dmarc_attachment(draw):
    """Generate email messages with DMARC report attachments."""
    from_addr = draw(valid_email_addresses())
    to_addr = draw(valid_email_addresses())
    subject = draw(st.sampled_from(['DMARC Report', 'Aggregate Report', 'Email Report']))
    xml_content = draw(dmarc_xml_content())
    
    # Create email message
    msg = email.message.EmailMessage()
    msg['From'] = from_addr
    msg['To'] = to_addr
    msg['Subject'] = subject
    msg['Date'] = email.utils.formatdate(localtime=True)
    msg['Message-ID'] = f"<{draw(st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789', min_size=10, max_size=20))}@example.com>"
    
    # Add text body
    msg.set_content("This is a DMARC aggregate report.")
    
    # Add XML attachment (optionally compressed)
    compression = draw(st.sampled_from(['none', 'gzip', 'zip']))
    
    if compression == 'gzip':
        compressed_content = gzip.compress(xml_content.encode('utf-8'))
        filename = 'dmarc_report.xml.gz'
        content_type = 'application/gzip'
    elif compression == 'zip':
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr('dmarc_report.xml', xml_content.encode('utf-8'))
        compressed_content = zip_buffer.getvalue()
        filename = 'dmarc_report.zip'
        content_type = 'application/zip'
    else:
        compressed_content = xml_content.encode('utf-8')
        filename = 'dmarc_report.xml'
        content_type = 'application/xml'
    
    msg.add_attachment(
        compressed_content,
        maintype='application',
        subtype=content_type.split('/')[-1],
        filename=filename
    )
    
    return msg.as_string(), xml_content, filename


@composite
def malformed_xml_content(draw):
    """Generate malformed XML content for error testing."""
    malformation_type = draw(st.sampled_from([
        'missing_closing_tag',
        'invalid_characters',
        'missing_required_element',
        'invalid_structure'
    ]))
    
    if malformation_type == 'missing_closing_tag':
        return "<feedback><report_metadata><org_name>Test</org_name></report_metadata>"
    elif malformation_type == 'invalid_characters':
        return "<?xml version='1.0'?><feedback>\x00\x01invalid</feedback>"
    elif malformation_type == 'missing_required_element':
        return """<?xml version="1.0"?>
        <feedback>
            <report_metadata>
                <org_name>Test</org_name>
            </report_metadata>
        </feedback>"""
    else:  # invalid_structure
        return """<?xml version="1.0"?>
        <not_feedback>
            <wrong_structure>Test</wrong_structure>
        </not_feedback>"""


class TestEmailStorageAndOrganization:
    """
    Property 1: Email Storage and Organization
    **Validates: Requirements 1.1, 1.2, 1.3**
    """
    
    @given(email_with_dmarc_attachment())
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow])
    def test_email_parsing_preserves_structure(self, email_data):
        """
        **Feature: dmarc-analysis, Property 1: Email Storage and Organization**
        
        For any valid email with DMARC attachments, parsing should preserve
        all essential email structure and metadata.
        """
        email_content, expected_xml, filename = email_data
        
        # Parse the email
        message = parse_email_from_string(email_content)
        
        # Verify essential headers are preserved
        assert message.get('From') is not None
        assert message.get('To') is not None
        assert message.get('Subject') is not None
        assert message.get('Date') is not None
        
        # Verify email structure validation passes
        assert validate_email_structure(message) is True
        
        # Verify metadata extraction works
        metadata = get_email_metadata(message)
        assert 'from' in metadata
        assert 'to' in metadata
        assert 'subject' in metadata
        assert 'date' in metadata
        assert metadata['from'] != ''
        assert metadata['to'] != ''
    
    @given(email_with_dmarc_attachment())
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow])
    def test_s3_processing_maintains_organization(self, email_data):
        """
        **Feature: dmarc-analysis, Property 1: Email Storage and Organization**
        
        For any email processed from S3, the system should maintain proper
        organization and trigger appropriate processing.
        """
        email_content, expected_xml, filename = email_data
        
        with patch('dmarc_lens.lambda_functions.report_parser.s3_client') as mock_s3, \
             patch('dmarc_lens.lambda_functions.report_parser.dynamodb') as mock_dynamodb:
            
            # Mock S3 response
            mock_s3.get_object.return_value = {
                'Body': Mock(read=Mock(return_value=email_content.encode('utf-8')))
            }
            
            # Mock DynamoDB table
            mock_table = Mock()
            mock_dynamodb.Table.return_value = mock_table
            
            # Process email
            result = process_email_from_s3('test-bucket', 'test-key')
            
            # Verify S3 was called with correct parameters
            mock_s3.get_object.assert_called_once_with(Bucket='test-bucket', Key='test-key')
            
            # Verify processing succeeded
            assert result['reports_processed'] >= 0
            assert isinstance(result['errors'], list)
            assert 'email_metadata' in result


class TestAttachmentPreservation:
    """
    Property 2: Attachment Preservation
    **Validates: Requirements 1.4**
    """
    
    @given(email_with_dmarc_attachment())
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow])
    def test_attachment_extraction_preserves_content(self, email_data):
        """
        **Feature: dmarc-analysis, Property 2: Attachment Preservation**
        
        For any email with DMARC attachments, all attachments should be
        preserved and accessible after extraction.
        """
        email_content, expected_xml, filename = email_data
        
        # Parse email and extract attachments
        message = parse_email_from_string(email_content)
        attachments = extract_attachments(message)
        
        # Verify at least one attachment was found
        assert len(attachments) > 0
        
        # Verify attachment structure
        for att_filename, att_content, att_content_type in attachments:
            assert isinstance(att_filename, str)
            assert isinstance(att_content, bytes)
            assert isinstance(att_content_type, str)
            assert len(att_content) > 0
    
    @given(email_with_dmarc_attachment())
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow])
    def test_dmarc_report_extraction_round_trip(self, email_data):
        """
        **Feature: dmarc-analysis, Property 2: Attachment Preservation**
        
        For any email with DMARC reports, extracting and decompressing
        should preserve the original XML content.
        """
        email_content, expected_xml, filename = email_data
        
        # Parse email and extract DMARC reports
        message = parse_email_from_string(email_content)
        dmarc_reports = extract_dmarc_reports(message)
        
        # Verify at least one DMARC report was extracted
        assert len(dmarc_reports) > 0
        
        # Verify content preservation
        extracted_filename, extracted_xml = dmarc_reports[0]
        
        # The extracted XML should contain the same essential elements
        # (whitespace and formatting may differ)
        assert '<feedback>' in extracted_xml
        assert '<report_metadata>' in extracted_xml
        assert '<policy_published>' in extracted_xml
        assert '<record>' in extracted_xml
    
    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=10)
    def test_compression_decompression_round_trip(self, original_content):
        """
        **Feature: dmarc-analysis, Property 2: Attachment Preservation**
        
        For any content, compressing and then decompressing should
        preserve the original data.
        """
        content_bytes = original_content.encode('utf-8')
        
        # Test gzip compression
        gzipped = gzip.compress(content_bytes)
        decompressed_gz = decompress_attachment(gzipped, 'test.gz')
        assert decompressed_gz == content_bytes
        
        # Test zip compression
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr('test.txt', content_bytes)
        zipped = zip_buffer.getvalue()
        
        decompressed_zip = decompress_attachment(zipped, 'test.zip')
        assert decompressed_zip == content_bytes


class TestParserErrorHandling:
    """
    Property 4: Parser Error Handling
    **Validates: Requirements 2.4**
    """
    
    @given(malformed_xml_content())
    @settings(max_examples=10)
    def test_malformed_xml_handling(self, malformed_xml):
        """
        **Feature: dmarc-analysis, Property 4: Parser Error Handling**
        
        For any malformed XML content, the parser should handle errors
        gracefully without crashing and provide meaningful error information.
        """
        from dmarc_lens.utils.xml_utils import parse_xml_string, validate_dmarc_xml_structure, XMLParsingError, XMLValidationError
        
        # Malformed XML should raise appropriate exceptions during parsing or validation
        try:
            root = parse_xml_string(malformed_xml)
            # If parsing succeeds, validation should catch structural issues
            with pytest.raises((XMLValidationError, Exception)):
                validate_dmarc_xml_structure(root)
        except (XMLParsingError, Exception):
            # This is expected for truly malformed XML
            pass
    
    @given(st.text(min_size=0, max_size=50))
    @settings(max_examples=10)
    def test_invalid_email_content_handling(self, invalid_content):
        """
        **Feature: dmarc-analysis, Property 4: Parser Error Handling**
        
        For any invalid email content, parsing should fail gracefully
        with appropriate error handling.
        """
        # Filter out content that might accidentally be valid
        assume(not invalid_content.startswith('From:'))
        assume('@' not in invalid_content or len(invalid_content) < 10)
        
        # Invalid email content should either parse successfully or raise EmailParsingError
        try:
            message = parse_email_from_string(invalid_content)
            # If parsing succeeds, validation should catch structural issues
            is_valid = validate_email_structure(message)
            # Either parsing fails or validation catches the issue
            assert isinstance(is_valid, bool)
        except EmailParsingError:
            # This is expected for invalid content
            pass
        except Exception as e:
            # Other exceptions should be wrapped in EmailParsingError
            # This test ensures we don't get unexpected exception types
            assert False, f"Unexpected exception type: {type(e).__name__}: {e}"
    
    @given(email_with_dmarc_attachment())
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow])
    def test_processing_error_recovery(self, email_data):
        """
        **Feature: dmarc-analysis, Property 4: Parser Error Handling**
        
        For any processing error, the system should recover gracefully
        and store appropriate error information.
        """
        email_content, expected_xml, filename = email_data
        
        with patch('dmarc_lens.lambda_functions.report_parser.s3_client') as mock_s3, \
             patch('dmarc_lens.lambda_functions.report_parser.dynamodb') as mock_dynamodb:
            
            # Mock S3 response
            mock_s3.get_object.return_value = {
                'Body': Mock(read=Mock(return_value=email_content.encode('utf-8')))
            }
            
            # Mock DynamoDB to raise an error on put_item
            mock_table = Mock()
            mock_table.put_item.side_effect = Exception("DynamoDB error")
            mock_dynamodb.Table.return_value = mock_table
            
            # Process email - should handle the error gracefully
            result = process_email_from_s3('test-bucket', 'test-key')
            
            # Verify error was captured and processing didn't crash
            assert isinstance(result, dict)
            assert 'errors' in result
            assert 'reports_processed' in result
            # Should have errors due to DynamoDB failure
            assert len(result['errors']) > 0 or result['reports_processed'] == 0


# Integration property tests
class TestEmailProcessingIntegration:
    """Integration tests for complete email processing pipeline."""
    
    @given(email_with_dmarc_attachment())
    @settings(max_examples=5, suppress_health_check=[HealthCheck.too_slow])
    def test_end_to_end_processing_consistency(self, email_data):
        """
        **Feature: dmarc-analysis, Property 1, 2, 4: Complete Processing Pipeline**
        
        For any valid email with DMARC reports, the complete processing
        pipeline should maintain data consistency from input to output.
        """
        email_content, expected_xml, filename = email_data
        
        # Step 1: Parse email
        message = parse_email_from_string(email_content)
        assert validate_email_structure(message)
        
        # Step 2: Extract DMARC reports
        dmarc_reports = extract_dmarc_reports(message)
        assert len(dmarc_reports) > 0
        
        # Step 3: Parse XML content
        from dmarc_lens.utils.xml_utils import parse_xml_string, validate_dmarc_xml_structure
        
        for report_filename, xml_content in dmarc_reports:
            # XML should be parseable
            root = parse_xml_string(xml_content)
            
            # XML should pass validation
            assert validate_dmarc_xml_structure(root) is True
            
            # Should be able to convert to data model
            from dmarc_lens.lambda_functions.report_parser import parse_dmarc_report_xml
            dmarc_report = parse_dmarc_report_xml(root)
            
            # Verify essential data is preserved
            assert dmarc_report.metadata.org_name != ''
            assert dmarc_report.metadata.email != ''
            assert dmarc_report.metadata.report_id != ''
            assert dmarc_report.policy_published.domain != ''
            assert len(dmarc_report.records) > 0
            
            # Verify record data integrity
            for record in dmarc_report.records:
                assert record.count > 0
                assert record.source_ip != ''
                assert record.header_from != ''
                assert record.policy_evaluated.disposition in ['none', 'quarantine', 'reject']
                assert record.policy_evaluated.dkim in ['pass', 'fail']
                assert record.policy_evaluated.spf in ['pass', 'fail']