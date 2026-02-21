"""
Property-based tests for authentication and authorization functionality.

These tests validate universal properties that should hold across all valid
inputs for JWT token validation, user authentication, and API authorization.

**Feature: dmarc-analysis, Property 8: Authentication and Authorization**
**Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**
"""

import json
import time
import jwt
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, strategies as st, settings, assume

from dmarc_lens.lambda_functions.auth import (
    validate_jwt_token, get_user_info, lambda_handler,
    create_success_response, create_error_response
)


# Test data strategies
@st.composite
def valid_jwt_claims(draw):
    """Generate valid JWT claims for testing."""
    current_time = int(time.time())
    
    return {
        'sub': draw(st.text(min_size=10, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))),
        'username': draw(st.text(min_size=3, max_size=30, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))),
        'email': draw(st.emails()),
        'email_verified': draw(st.booleans()),
        'given_name': draw(st.text(min_size=1, max_size=50)),
        'family_name': draw(st.text(min_size=1, max_size=50)),
        'aud': 'test-client-id',
        'iss': 'https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TestPool',
        'token_use': draw(st.sampled_from(['access', 'id'])),
        'iat': current_time - draw(st.integers(min_value=0, max_value=3600)),  # Issued in the past
        'exp': current_time + draw(st.integers(min_value=60, max_value=3600)),  # Expires in the future
        'nbf': current_time - draw(st.integers(min_value=0, max_value=60)),     # Valid from past/now
        'cognito:groups': draw(st.lists(st.text(min_size=1, max_size=20), max_size=5))
    }


@st.composite
def expired_jwt_claims(draw):
    """Generate expired JWT claims for testing."""
    current_time = int(time.time())
    
    claims = draw(valid_jwt_claims())
    # Make token expired
    claims['exp'] = current_time - draw(st.integers(min_value=1, max_value=3600))
    return claims


@st.composite
def invalid_jwt_claims(draw):
    """Generate invalid JWT claims for testing."""
    claims = draw(valid_jwt_claims())
    
    # Introduce various types of invalidity that the code actually checks
    # after jwt.decode (which is mocked in tests)
    invalidity_type = draw(st.sampled_from([
        'invalid_token_use', 'future_nbf', 'missing_sub'
    ]))
    
    if invalidity_type == 'invalid_token_use':
        claims['token_use'] = 'invalid'
    elif invalidity_type == 'future_nbf':
        claims['nbf'] = int(time.time()) + 3600  # Valid in the future
    elif invalidity_type == 'missing_sub':
        del claims['sub']
    
    return claims


@st.composite
def api_gateway_auth_event(draw):
    """Generate API Gateway event for authentication testing."""
    # Only generate valid method+path combinations
    method_path = draw(st.sampled_from([
        ('POST', '/auth/validate'),
        ('GET', '/health')
    ]))
    method, path = method_path
    
    event = {
        'httpMethod': method,
        'path': path,
        'headers': {},
        'queryStringParameters': {},
        'pathParameters': {},
        'body': '{}'
    }
    
    # Add authorization header sometimes
    if draw(st.booleans()) and path == '/auth/validate':
        token = draw(st.text(min_size=10, max_size=200))
        event['headers']['Authorization'] = f'Bearer {token}'
    
    # Add body with token sometimes
    if method == 'POST' and path == '/auth/validate' and draw(st.booleans()):
        token = draw(st.text(min_size=10, max_size=200))
        event['body'] = json.dumps({'token': token})
    
    return event


class TestAuthenticationAndAuthorization:
    """
    Property 8: Authentication and Authorization
    
    **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**
    """
    
    @given(valid_jwt_claims())
    @settings(max_examples=100)
    def test_valid_token_authentication_success(self, claims):
        """
        **Feature: dmarc-analysis, Property 8: Authentication and Authorization**
        
        For any valid JWT token with proper claims, the authentication
        should succeed and return user information.
        """
        # Mock environment variables
        with patch.dict('os.environ', {
            'USER_POOL_ID': 'us-east-1_TestPool',
            'USER_POOL_CLIENT_ID': 'test-client-id',
            'AWS_REGION': 'us-east-1'
        }):
            # Mock JWKS retrieval and JWT validation
            mock_jwks = {
                'keys': [{
                    'kid': 'test-key-id',
                    'kty': 'RSA',
                    'use': 'sig',
                    'n': 'test-n',
                    'e': 'AQAB'
                }]
            }
            
            with patch('dmarc_lens.lambda_functions.auth.get_jwks', return_value=mock_jwks), \
                 patch('jwt.get_unverified_header', return_value={'kid': 'test-key-id'}), \
                 patch('jwt.decode', return_value=claims), \
                 patch('jwt.algorithms.RSAAlgorithm.from_jwk'):
                
                result = validate_jwt_token('mock-token')
                
                # Verify successful validation
                assert result['valid'] is True
                assert 'claims' in result
                assert result['claims'] == claims
    
    @given(expired_jwt_claims())
    @settings(max_examples=50)
    def test_expired_token_authentication_failure(self, claims):
        """
        **Feature: dmarc-analysis, Property 8: Authentication and Authorization**
        
        For any expired JWT token, the authentication should fail
        with an appropriate error message.
        """
        with patch.dict('os.environ', {
            'USER_POOL_ID': 'us-east-1_TestPool',
            'USER_POOL_CLIENT_ID': 'test-client-id',
            'AWS_REGION': 'us-east-1'
        }):
            mock_jwks = {
                'keys': [{
                    'kid': 'test-key-id',
                    'kty': 'RSA',
                    'use': 'sig',
                    'n': 'test-n',
                    'e': 'AQAB'
                }]
            }
            
            with patch('dmarc_lens.lambda_functions.auth.get_jwks', return_value=mock_jwks), \
                 patch('jwt.get_unverified_header', return_value={'kid': 'test-key-id'}), \
                 patch('jwt.decode', return_value=claims), \
                 patch('jwt.algorithms.RSAAlgorithm.from_jwk'):
                
                result = validate_jwt_token('mock-token')
                
                # Verify authentication failure for expired token
                assert result['valid'] is False
                assert 'error' in result
                assert 'expired' in result['error'].lower()
    
    @given(invalid_jwt_claims())
    @settings(max_examples=50)
    def test_invalid_token_authentication_failure(self, claims):
        """
        **Feature: dmarc-analysis, Property 8: Authentication and Authorization**
        
        For any JWT token with invalid claims, the authentication should fail
        with an appropriate error message.
        """
        with patch.dict('os.environ', {
            'USER_POOL_ID': 'us-east-1_TestPool',
            'USER_POOL_CLIENT_ID': 'test-client-id',
            'AWS_REGION': 'us-east-1'
        }):
            mock_jwks = {
                'keys': [{
                    'kid': 'test-key-id',
                    'kty': 'RSA',
                    'use': 'sig',
                    'n': 'test-n',
                    'e': 'AQAB'
                }]
            }
            
            with patch('dmarc_lens.lambda_functions.auth.get_jwks', return_value=mock_jwks), \
                 patch('jwt.get_unverified_header', return_value={'kid': 'test-key-id'}), \
                 patch('jwt.decode', return_value=claims), \
                 patch('jwt.algorithms.RSAAlgorithm.from_jwk'):
                
                result = validate_jwt_token('mock-token')
                
                # Verify authentication failure for invalid claims
                assert result['valid'] is False
                assert 'error' in result
    
    @given(api_gateway_auth_event())
    @settings(max_examples=50)
    def test_api_gateway_authentication_flow(self, event):
        """
        **Feature: dmarc-analysis, Property 8: Authentication and Authorization**
        
        For any API Gateway authentication request, the response should have
        proper structure with status code, headers, and body.
        """
        with patch.dict('os.environ', {
            'USER_POOL_ID': 'us-east-1_TestPool',
            'USER_POOL_CLIENT_ID': 'test-client-id',
            'AWS_REGION': 'us-east-1'
        }):
            # Mock all external dependencies
            with patch('dmarc_lens.lambda_functions.auth.validate_jwt_token') as mock_validate, \
                 patch('dmarc_lens.lambda_functions.auth.get_user_info') as mock_user_info:
                
                # Configure mocks based on event
                if event['path'] == '/health':
                    # Health check should always succeed
                    response = lambda_handler(event, {})
                    assert response['statusCode'] == 200
                    
                elif event['path'] == '/auth/validate':
                    # Mock token validation
                    mock_validate.return_value = {
                        'valid': True,
                        'claims': {'sub': 'test-user', 'exp': int(time.time()) + 3600}
                    }
                    mock_user_info.return_value = {
                        'username': 'test-user',
                        'email': 'test@example.com'
                    }
                    
                    response = lambda_handler(event, {})
                    
                    # Verify response structure
                    assert 'statusCode' in response
                    assert response['statusCode'] in [200, 400, 401, 500]
                    assert 'headers' in response
                    assert 'body' in response
                    
                    # Verify CORS headers are present
                    headers = response['headers']
                    assert 'Access-Control-Allow-Origin' in headers
                    assert 'Content-Type' in headers
                    
                    # Verify body is valid JSON
                    try:
                        json.loads(response['body'])
                    except json.JSONDecodeError:
                        pytest.fail("Response body is not valid JSON")
    
    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=30)
    def test_malformed_token_handling(self, malformed_token):
        """
        **Feature: dmarc-analysis, Property 8: Authentication and Authorization**
        
        For any malformed token string, the authentication should fail gracefully
        without crashing and return an appropriate error.
        """
        # Assume the token is not a valid JWT format
        assume(not malformed_token.count('.') == 2)
        
        with patch.dict('os.environ', {
            'USER_POOL_ID': 'us-east-1_TestPool',
            'USER_POOL_CLIENT_ID': 'test-client-id',
            'AWS_REGION': 'us-east-1'
        }):
            mock_jwks = {
                'keys': [{
                    'kid': 'test-key-id',
                    'kty': 'RSA',
                    'use': 'sig',
                    'n': 'test-n',
                    'e': 'AQAB'
                }]
            }
            
            with patch('dmarc_lens.lambda_functions.auth.get_jwks', return_value=mock_jwks):
                result = validate_jwt_token(malformed_token)
                
                # Verify graceful failure
                assert result['valid'] is False
                assert 'error' in result
                assert isinstance(result['error'], str)
                assert len(result['error']) > 0
    
    @given(valid_jwt_claims())
    @settings(max_examples=30)
    def test_user_info_extraction_consistency(self, claims):
        """
        **Feature: dmarc-analysis, Property 8: Authentication and Authorization**
        
        For any valid JWT claims, the extracted user information should
        be consistent and contain expected fields.
        """
        mock_cognito = MagicMock()
        mock_cognito.admin_get_user.return_value = {
            'UserAttributes': [
                {'Name': 'email', 'Value': claims.get('email', 'test@example.com')},
                {'Name': 'email_verified', 'Value': 'true'},
                {'Name': 'given_name', 'Value': claims.get('given_name', 'Test')},
                {'Name': 'family_name', 'Value': claims.get('family_name', 'User')}
            ],
            'UserStatus': 'CONFIRMED',
            'Enabled': True
        }
        
        with patch('dmarc_lens.lambda_functions.auth.cognito_client', mock_cognito), \
             patch.dict('os.environ', {'USER_POOL_ID': 'test-pool'}):
            user_info = get_user_info(claims)
            
            # Verify user info structure and consistency
            assert isinstance(user_info, dict)
            assert 'username' in user_info
            assert 'email' in user_info
            assert 'groups' in user_info
            
            # Verify username consistency
            expected_username = claims.get('username') or claims.get('sub')
            if expected_username:
                assert user_info['username'] == expected_username
            
            # Verify groups are always a list
            assert isinstance(user_info['groups'], list)
    
    @given(st.integers(min_value=400, max_value=599), st.text(min_size=1, max_size=200))
    @settings(max_examples=20)
    def test_error_response_format_consistency(self, status_code, error_message):
        """
        **Feature: dmarc-analysis, Property 8: Authentication and Authorization**
        
        For any error status code and message, the error response should have
        consistent format with proper structure and CORS headers.
        """
        response = create_error_response(status_code, error_message)
        
        # Verify response structure
        assert response['statusCode'] == status_code
        assert 'headers' in response
        assert 'body' in response
        
        # Verify CORS headers
        headers = response['headers']
        assert 'Access-Control-Allow-Origin' in headers
        assert 'Content-Type' in headers
        
        # Verify body structure
        body = json.loads(response['body'])
        assert 'error' in body
        assert body['error']['code'] == status_code
        assert body['error']['message'] == error_message
        assert 'timestamp' in body['error']
    
    @given(st.dictionaries(st.text(min_size=1, max_size=50), st.text(max_size=100)))
    @settings(max_examples=20)
    def test_success_response_format_consistency(self, data):
        """
        **Feature: dmarc-analysis, Property 8: Authentication and Authorization**
        
        For any success data, the success response should have consistent
        format with proper structure and CORS headers.
        """
        response = create_success_response(data)
        
        # Verify response structure
        assert response['statusCode'] == 200
        assert 'headers' in response
        assert 'body' in response
        
        # Verify CORS headers
        headers = response['headers']
        assert 'Access-Control-Allow-Origin' in headers
        assert 'Content-Type' in headers
        
        # Verify body contains the data
        body = json.loads(response['body'])
        assert body == data