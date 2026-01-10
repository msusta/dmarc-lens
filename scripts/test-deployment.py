#!/usr/bin/env python3
"""
Test deployment script for DMARC Lens Lambda functions.

This script simulates the deployment process and tests the Lambda functions
locally without requiring AWS credentials.
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dmarc_lens.lambda_functions.report_parser import lambda_handler as parser_handler
from dmarc_lens.lambda_functions.analysis_engine import lambda_handler as analysis_handler
from dmarc_lens.models.dmarc_models import DMARCReport, ReportMetadata, PolicyPublished, DMARCRecord, PolicyEvaluated, AuthResult


def create_sample_dmarc_email():
    """Create a sample DMARC report email for testing."""
    
    # Sample DMARC XML report
    dmarc_xml = """<?xml version="1.0" encoding="UTF-8"?>
<feedback>
  <report_metadata>
    <org_name>Example Corp</org_name>
    <email>dmarc@example.com</email>
    <report_id>12345678901234567890</report_id>
    <date_range>
      <begin>1609459200</begin>
      <end>1609545600</end>
    </date_range>
  </report_metadata>
  <policy_published>
    <domain>example.org</domain>
    <p>quarantine</p>
    <sp>none</sp>
    <pct>100</pct>
  </policy_published>
  <record>
    <row>
      <source_ip>192.0.2.1</source_ip>
      <count>12</count>
      <policy_evaluated>
        <disposition>none</disposition>
        <dkim>pass</dkim>
        <spf>pass</spf>
      </policy_evaluated>
    </row>
    <identifiers>
      <header_from>example.org</header_from>
    </identifiers>
    <auth_results>
      <dkim>
        <domain>example.org</domain>
        <result>pass</result>
        <selector>default</selector>
      </dkim>
      <spf>
        <domain>example.org</domain>
        <result>pass</result>
      </spf>
    </auth_results>
  </record>
  <record>
    <row>
      <source_ip>192.0.2.2</source_ip>
      <count>5</count>
      <policy_evaluated>
        <disposition>quarantine</disposition>
        <dkim>fail</dkim>
        <spf>pass</spf>
      </policy_evaluated>
    </row>
    <identifiers>
      <header_from>example.org</header_from>
    </identifiers>
    <auth_results>
      <dkim>
        <domain>example.org</domain>
        <result>fail</result>
      </dkim>
      <spf>
        <domain>example.org</domain>
        <result>pass</result>
      </spf>
    </auth_results>
  </record>
</feedback>"""
    
    # Create email with DMARC attachment
    email_content = f"""From: dmarc@example.com
To: dmarc-reports@yourdomain.com
Subject: Report Domain: example.org Submitter: example.com Report-ID: 12345678901234567890
Date: {datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')}
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="boundary123"

--boundary123
Content-Type: text/plain

This is a DMARC aggregate report for example.org.

--boundary123
Content-Type: application/gzip
Content-Disposition: attachment; filename="example.org!example.com!1609459200!1609545600.xml.gz"
Content-Transfer-Encoding: base64

{encode_gzip_base64(dmarc_xml)}
--boundary123--
"""
    
    return email_content


def encode_gzip_base64(content):
    """Encode content as gzipped base64."""
    import gzip
    import base64
    
    compressed = gzip.compress(content.encode('utf-8'))
    return base64.b64encode(compressed).decode('ascii')


def create_s3_event(bucket_name, object_key):
    """Create a sample S3 event for testing."""
    
    return {
        "Records": [
            {
                "eventVersion": "2.1",
                "eventSource": "aws:s3",
                "awsRegion": "us-east-1",
                "eventTime": datetime.now(timezone.utc).isoformat(),
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "s3SchemaVersion": "1.0",
                    "configurationId": "dmarc-reports-config",
                    "bucket": {
                        "name": bucket_name,
                        "arn": f"arn:aws:s3:::{bucket_name}"
                    },
                    "object": {
                        "key": object_key,
                        "size": 1024,
                        "eTag": "d41d8cd98f00b204e9800998ecf8427e"
                    }
                }
            }
        ]
    }


def create_dynamodb_stream_event():
    """Create a sample DynamoDB Streams event for testing."""
    
    return {
        "Records": [
            {
                "eventID": "1",
                "eventName": "INSERT",
                "eventVersion": "1.1",
                "eventSource": "aws:dynamodb",
                "awsRegion": "us-east-1",
                "dynamodb": {
                    "ApproximateCreationDateTime": datetime.now(timezone.utc).timestamp(),
                    "Keys": {
                        "report_id": {"S": "12345678901234567890"},
                        "record_id": {"S": "12345678901234567890#0000"}
                    },
                    "NewImage": {
                        "report_id": {"S": "12345678901234567890"},
                        "record_id": {"S": "12345678901234567890#0000"},
                        "domain": {"S": "example.org"},
                        "source_ip": {"S": "192.0.2.1"},
                        "count": {"N": "12"},
                        "disposition": {"S": "none"},
                        "dkim_result": {"S": "pass"},
                        "spf_result": {"S": "pass"}
                    },
                    "SequenceNumber": "111",
                    "SizeBytes": 26,
                    "StreamViewType": "NEW_AND_OLD_IMAGES"
                }
            }
        ]
    }


class MockS3Client:
    """Mock S3 client for testing."""
    
    def __init__(self):
        self.objects = {}
    
    def get_object(self, Bucket, Key):
        """Mock get_object method."""
        if Key in self.objects:
            content = self.objects[Key]
            return {
                'Body': MockBody(content)
            }
        else:
            raise Exception(f"Object not found: {Key}")
    
    def put_object(self, bucket, key, content):
        """Store object for testing."""
        self.objects[key] = content


class MockBody:
    """Mock S3 object body."""
    
    def __init__(self, content):
        self.content = content.encode('utf-8') if isinstance(content, str) else content
    
    def read(self):
        return self.content


class MockDynamoDBTable:
    """Mock DynamoDB table for testing."""
    
    def __init__(self, table_name):
        self.table_name = table_name
        self.items = []
    
    def put_item(self, Item):
        """Mock put_item method."""
        self.items.append(Item)
        print(f"✓ Stored item in {self.table_name}: {Item.get('report_id', 'unknown')}")
    
    def scan(self, **kwargs):
        """Mock scan method."""
        # Return sample data for analysis
        if self.table_name == 'dmarc-reports':
            return {
                'Items': [
                    {
                        'report_id': '12345678901234567890',
                        'record_id': '12345678901234567890#0000',
                        'domain': 'example.org',
                        'source_ip': '192.0.2.1',
                        'count': 12,
                        'disposition': 'none',
                        'dkim_result': 'pass',
                        'spf_result': 'pass',
                        'date_range_begin': 1609459200,
                        'date_range_end': 1609545600
                    },
                    {
                        'report_id': '12345678901234567890',
                        'record_id': '12345678901234567890#0001',
                        'domain': 'example.org',
                        'source_ip': '192.0.2.2',
                        'count': 5,
                        'disposition': 'quarantine',
                        'dkim_result': 'fail',
                        'spf_result': 'pass',
                        'date_range_begin': 1609459200,
                        'date_range_end': 1609545600
                    }
                ]
            }
        return {'Items': []}
    
    def get_item(self, Key):
        """Mock get_item method."""
        return {}  # No previous analysis


class MockDynamoDBResource:
    """Mock DynamoDB resource."""
    
    def __init__(self):
        self.tables = {}
    
    def Table(self, table_name):
        if table_name not in self.tables:
            self.tables[table_name] = MockDynamoDBTable(table_name)
        return self.tables[table_name]


def test_report_parser():
    """Test the Report Parser Lambda function."""
    
    print("Testing Report Parser Lambda Function...")
    print("=" * 50)
    
    # Create sample email and S3 event
    email_content = create_sample_dmarc_email()
    bucket_name = "test-dmarc-emails"
    object_key = "incoming/2024/01/10/example.com/test-email.eml"
    
    # Mock S3 client
    mock_s3 = MockS3Client()
    mock_s3.put_object(bucket_name, object_key, email_content)
    
    # Mock DynamoDB
    mock_dynamodb = MockDynamoDBResource()
    
    # Patch the global clients in the report parser module
    import dmarc_lens.lambda_functions.report_parser as parser_module
    parser_module.s3_client = mock_s3
    parser_module.dynamodb = mock_dynamodb
    
    # Create S3 event
    event = create_s3_event(bucket_name, object_key)
    
    # Test the lambda handler
    try:
        response = parser_handler(event, None)
        
        print(f"✓ Parser Lambda executed successfully")
        print(f"  Status Code: {response['statusCode']}")
        print(f"  Records Processed: {response['body']['records_processed']}")
        print(f"  Errors: {len(response['body']['errors'])}")
        
        if response['body']['errors']:
            for error in response['body']['errors']:
                print(f"    - {error}")
        
        # Check if data was stored
        reports_table = mock_dynamodb.Table('dmarc-reports')
        print(f"  Items stored in reports table: {len(reports_table.items)}")
        
        return response['statusCode'] == 200
        
    except Exception as e:
        print(f"✗ Parser Lambda failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_analysis_engine():
    """Test the Analysis Engine Lambda function."""
    
    print("\nTesting Analysis Engine Lambda Function...")
    print("=" * 50)
    
    # Mock DynamoDB
    mock_dynamodb = MockDynamoDBResource()
    
    # Patch the global clients in the analysis engine module
    import dmarc_lens.lambda_functions.analysis_engine as analysis_module
    analysis_module.dynamodb = mock_dynamodb
    
    # Create DynamoDB Streams event
    event = create_dynamodb_stream_event()
    
    # Test the lambda handler
    try:
        response = analysis_handler(event, None)
        
        print(f"✓ Analysis Lambda executed successfully")
        print(f"  Status Code: {response['statusCode']}")
        print(f"  Records Processed: {response['body']['records_processed']}")
        print(f"  Analyses Completed: {response['body']['analyses_completed']}")
        print(f"  Domains Analyzed: {response['body']['domains_analyzed']}")
        print(f"  Errors: {len(response['body']['errors'])}")
        
        if response['body']['errors']:
            for error in response['body']['errors']:
                print(f"    - {error}")
        
        # Check if analysis was stored
        analysis_table = mock_dynamodb.Table('dmarc-analysis')
        print(f"  Items stored in analysis table: {len(analysis_table.items)}")
        
        if analysis_table.items:
            analysis = analysis_table.items[0]
            print(f"  Analysis for domain: {analysis.get('domain', 'unknown')}")
            print(f"  Success rate: {analysis.get('auth_success_rate', 0)}%")
        
        return response['statusCode'] == 200
        
    except Exception as e:
        print(f"✗ Analysis Lambda failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_flow():
    """Test the complete data flow from S3 to DynamoDB to Analysis."""
    
    print("\nTesting Complete Data Flow...")
    print("=" * 50)
    
    # Test both functions in sequence
    parser_success = test_report_parser()
    analysis_success = test_analysis_engine()
    
    if parser_success and analysis_success:
        print("\n✓ Complete data flow test PASSED")
        print("  S3 → Lambda (Parser) → DynamoDB → Lambda (Analysis) → DynamoDB")
        return True
    else:
        print("\n✗ Complete data flow test FAILED")
        return False


def main():
    """Main test function."""
    
    print("DMARC Lens Lambda Function Deployment Test")
    print("=" * 60)
    print()
    
    # Set environment variables for testing
    os.environ['REPORTS_TABLE_NAME'] = 'dmarc-reports'
    os.environ['FAILED_REPORTS_TABLE_NAME'] = 'dmarc-failed-reports'
    os.environ['ANALYSIS_TABLE_NAME'] = 'dmarc-analysis'
    os.environ['LOG_LEVEL'] = 'INFO'
    
    # Run tests
    success = test_data_flow()
    
    print("\n" + "=" * 60)
    if success:
        print("✓ ALL TESTS PASSED - Lambda functions are ready for deployment")
        print("\nNext steps:")
        print("1. Configure AWS credentials: aws configure")
        print("2. Deploy infrastructure: make deploy")
        print("3. Test with real DMARC reports")
    else:
        print("✗ SOME TESTS FAILED - Please review the errors above")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())