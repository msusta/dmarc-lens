"""
Authentication Lambda function for DMARC Lens.

This function handles JWT token validation and authorization for API endpoints.
It validates Cognito JWT tokens and implements authorization checks.

Requirements: 4.3, 4.4, 4.5
"""

import json
import logging
import os
import time
from typing import Dict, Any, Optional
from urllib.request import urlopen
from urllib.error import URLError

import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))

# Initialize Cognito client
cognito_client = boto3.client('cognito-idp')

# Cache for JWKS (JSON Web Key Set)
_jwks_cache = {}
_jwks_cache_expiry = 0


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for authentication requests.
    
    Args:
        event: API Gateway event containing request details
        context: Lambda context object
        
    Returns:
        API Gateway response with authentication result
    """
    try:
        # Extract request information
        http_method = event.get('httpMethod') or event.get('requestContext', {}).get('http', {}).get('method')
        path = event.get('path') or event.get('rawPath', '')
        headers = event.get('headers', {})
        body = event.get('body', '{}')
        
        logger.info(f"Processing {http_method} request to {path}")
        
        # Route the request to appropriate handler
        if path == '/auth/validate' and http_method == 'POST':
            return handle_token_validation(body, headers)
        elif path == '/health' and http_method == 'GET':
            return handle_health_check()
        else:
            return create_error_response(404, "Endpoint not found")
            
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return create_error_response(500, "Internal server error")


def handle_token_validation(body: str, headers: Dict[str, str]) -> Dict[str, Any]:
    """
    Handle POST /auth/validate - Validate JWT token and return user context.
    
    Args:
        body: Request body containing token or using Authorization header
        headers: Request headers
        
    Returns:
        API response with validation result and user context
    """
    try:
        # Extract token from body or Authorization header
        token = None
        
        if body and body != '{}':
            request_data = json.loads(body)
            token = request_data.get('token')
        
        if not token:
            auth_header = headers.get('Authorization') or headers.get('authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header[7:]  # Remove 'Bearer ' prefix
        
        if not token:
            return create_error_response(400, "Token is required")
        
        # Validate the JWT token
        validation_result = validate_jwt_token(token)
        
        if validation_result['valid']:
            # Get additional user information from Cognito
            user_info = get_user_info(validation_result['claims'])
            
            return create_success_response({
                'valid': True,
                'user': user_info,
                'claims': validation_result['claims'],
                'expires_at': validation_result['claims'].get('exp')
            })
        else:
            return create_error_response(401, validation_result['error'])
            
    except json.JSONDecodeError:
        return create_error_response(400, "Invalid JSON in request body")
    except Exception as e:
        logger.error(f"Token validation error: {str(e)}")
        return create_error_response(500, "Token validation failed")


def handle_health_check() -> Dict[str, Any]:
    """
    Handle GET /health - Health check endpoint.
    
    Returns:
        API response with service health status
    """
    return create_success_response({
        'status': 'healthy',
        'service': 'dmarc-lens-auth',
        'timestamp': int(time.time())
    })


def validate_jwt_token(token: str) -> Dict[str, Any]:
    """
    Validate a JWT token from Cognito.
    
    Args:
        token: JWT token string
        
    Returns:
        Dictionary with validation result and claims
    """
    try:
        # Get User Pool configuration
        user_pool_id = os.getenv('USER_POOL_ID')
        user_pool_client_id = os.getenv('USER_POOL_CLIENT_ID')
        region = os.getenv('AWS_REGION', 'us-east-1')
        
        if not user_pool_id or not user_pool_client_id:
            logger.error("Missing User Pool configuration")
            return {'valid': False, 'error': 'Authentication service misconfigured'}
        
        # Get JWKS (JSON Web Key Set) from Cognito
        jwks = get_jwks(region, user_pool_id)
        
        # Decode token header to get key ID
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get('kid')
        
        if not kid:
            return {'valid': False, 'error': 'Token missing key ID'}
        
        # Find the correct key in JWKS
        key = None
        for jwk in jwks.get('keys', []):
            if jwk.get('kid') == kid:
                key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
                break
        
        if not key:
            return {'valid': False, 'error': 'Unable to find matching key'}
        
        # Verify and decode the token
        claims = jwt.decode(
            token,
            key,
            algorithms=['RS256'],
            audience=user_pool_client_id,
            issuer=f'https://cognito-idp.{region}.amazonaws.com/{user_pool_id}'
        )
        
        # Additional validation
        current_time = int(time.time())
        
        # Check token expiration
        if claims.get('exp', 0) < current_time:
            return {'valid': False, 'error': 'Token has expired'}
        
        # Check token usage (should be 'access' or 'id')
        token_use = claims.get('token_use')
        if token_use not in ['access', 'id']:
            return {'valid': False, 'error': 'Invalid token usage'}
        
        # Check if token is not used before its valid time
        if claims.get('nbf', 0) > current_time:
            return {'valid': False, 'error': 'Token not yet valid'}
        
        return {'valid': True, 'claims': claims}
        
    except ExpiredSignatureError:
        return {'valid': False, 'error': 'Token has expired'}
    except InvalidTokenError as e:
        logger.warning(f"Invalid token: {str(e)}")
        return {'valid': False, 'error': 'Invalid token'}
    except Exception as e:
        logger.error(f"Token validation error: {str(e)}")
        return {'valid': False, 'error': 'Token validation failed'}


def get_jwks(region: str, user_pool_id: str) -> Dict[str, Any]:
    """
    Get JWKS (JSON Web Key Set) from Cognito with caching.
    
    Args:
        region: AWS region
        user_pool_id: Cognito User Pool ID
        
    Returns:
        JWKS dictionary
    """
    global _jwks_cache, _jwks_cache_expiry
    
    current_time = int(time.time())
    cache_key = f"{region}:{user_pool_id}"
    
    # Check if we have a valid cached JWKS
    if (cache_key in _jwks_cache and 
        current_time < _jwks_cache_expiry):
        return _jwks_cache[cache_key]
    
    try:
        # Fetch JWKS from Cognito
        jwks_url = f'https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json'
        
        with urlopen(jwks_url) as response:
            jwks = json.loads(response.read().decode('utf-8'))
        
        # Cache the JWKS for 1 hour
        _jwks_cache[cache_key] = jwks
        _jwks_cache_expiry = current_time + 3600
        
        return jwks
        
    except URLError as e:
        logger.error(f"Failed to fetch JWKS: {str(e)}")
        raise Exception("Unable to fetch token validation keys")


def get_user_info(claims: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get additional user information from Cognito.
    
    Args:
        claims: JWT token claims
        
    Returns:
        User information dictionary
    """
    try:
        username = claims.get('username') or claims.get('cognito:username')
        
        if not username:
            # For ID tokens, we might have the user info in claims
            return {
                'username': claims.get('sub'),
                'email': claims.get('email'),
                'email_verified': claims.get('email_verified', False),
                'given_name': claims.get('given_name'),
                'family_name': claims.get('family_name'),
                'groups': claims.get('cognito:groups', [])
            }
        
        # Get user details from Cognito
        user_pool_id = os.getenv('USER_POOL_ID')
        
        response = cognito_client.admin_get_user(
            UserPoolId=user_pool_id,
            Username=username
        )
        
        # Extract user attributes
        attributes = {}
        for attr in response.get('UserAttributes', []):
            attributes[attr['Name']] = attr['Value']
        
        return {
            'username': username,
            'email': attributes.get('email'),
            'email_verified': attributes.get('email_verified') == 'true',
            'given_name': attributes.get('given_name'),
            'family_name': attributes.get('family_name'),
            'user_status': response.get('UserStatus'),
            'enabled': response.get('Enabled', True),
            'groups': claims.get('cognito:groups', [])
        }
        
    except ClientError as e:
        logger.warning(f"Failed to get user info: {str(e)}")
        # Return basic info from claims if Cognito call fails
        return {
            'username': claims.get('username') or claims.get('sub'),
            'email': claims.get('email'),
            'groups': claims.get('cognito:groups', [])
        }
    except Exception as e:
        logger.error(f"Error getting user info: {str(e)}")
        return {
            'username': claims.get('username') or claims.get('sub'),
            'groups': []
        }


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
        'body': json.dumps(data)
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
                'timestamp': int(time.time())
            }
        })
    }