import json
import os
import boto3

ssm = boto3.client('ssm')

# Required fields for survey message
REQUIRED_FIELDS = ['surveyId', 'customerId', 'rating', 'text', 'timestamp']


def lambda_handler(event, context):
    """
    Lambda authorizer to validate API key from x-api-key header.
    Also performs basic request validation for required fields.
    """
    # Get API key from SSM parameter
    api_key_param = os.environ.get('API_KEY_PARAM', '')

    try:
        response = ssm.get_parameter(Name=api_key_param, WithDecryption=True)
        valid_api_key = response['Parameter']['Value']
    except Exception as e:
        print(f"Error retrieving API key from SSM: {str(e)}")
        return generate_policy('user', 'Deny', event.get('routeArn', event.get('methodArn', '*')))

    # Get API key from request headers (HTTP API v2 format)
    headers = event.get('headers', {}) or event.get('requestContext', {}).get('http', {}).get('headers', {})
    # Headers can be case-insensitive, so check both cases
    api_key = headers.get('x-api-key') or headers.get('X-Api-Key') or headers.get('X-API-Key')

    if not api_key or api_key != valid_api_key:
        route_arn = event.get('routeArn', event.get('methodArn', '*'))
        return generate_policy('user', 'Deny', route_arn)

    # Basic request body validation (if body is available)
    # Note: For HTTP APIs, body might not always be available in authorizer
    # Full validation happens in the Lambda processor
    body = event.get('body')
    if body:
        try:
            body_json = json.loads(body) if isinstance(body, str) else body
            missing_fields = [field for field in REQUIRED_FIELDS if field not in body_json]
            if missing_fields:
                print(f"Missing required fields: {missing_fields}")
                # Still allow, but log the issue - full validation in processor
        except (json.JSONDecodeError, TypeError):
            print("Invalid JSON in request body")
            # Still allow - let the processor handle it

    # API key is valid
    route_arn = event.get('routeArn', event.get('methodArn', '*'))
    return generate_policy('user', 'Allow', route_arn)


def generate_policy(principal_id, effect, resource):
    """Generate IAM policy for API Gateway."""
    policy = {
        'principalId': principal_id,
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': 'execute-api:Invoke',
                    'Effect': effect,
                    'Resource': resource
                }
            ]
        }
    }
    return policy
