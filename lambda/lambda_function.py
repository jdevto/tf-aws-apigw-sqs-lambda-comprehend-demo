import json
import os
import time
from datetime import datetime, timedelta
from decimal import Decimal
import boto3
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
comprehend = boto3.client('comprehend')

# Get environment variables
TABLE_NAME = os.environ['TABLE_NAME']
TTL_DAYS = int(os.environ.get('TTL_DAYS', '365'))


def lambda_handler(event, context):
    """
    Process SQS events containing survey data.
    Analyzes sentiment using Comprehend and stores results in DynamoDB.
    Supports partial batch failure reporting.
    """
    batch_item_failures = []

    for record in event.get('Records', []):
        try:
            # Parse SQS message body
            message_body = json.loads(record['body'])

            # Extract survey data
            survey_id = message_body.get('surveyId')
            customer_id = message_body.get('customerId')
            rating = message_body.get('rating')
            text = message_body.get('text')
            timestamp = message_body.get('timestamp')

            # Validate required fields
            if not all([survey_id, customer_id, rating, text]):
                logger.error(f"Missing required fields in message: {message_body}")
                batch_item_failures.append({
                    'itemIdentifier': record['messageId']
                })
                continue

            # Analyze sentiment with Comprehend
            try:
                sentiment_response = comprehend.detect_sentiment(
                    Text=text,
                    LanguageCode='en'
                )

                sentiment = sentiment_response['Sentiment']
                sentiment_scores = sentiment_response['SentimentScore']

            except Exception as e:
                logger.error(f"Comprehend error for survey {survey_id}: {str(e)}")
                batch_item_failures.append({
                    'itemIdentifier': record['messageId']
                })
                continue

            # Calculate TTL (expiresAt)
            created_at = int(time.time())
            expires_at = created_at + (TTL_DAYS * 24 * 60 * 60)

            # Prepare DynamoDB item
            item = {
                'pk': f'SURVEY#{survey_id}',
                'customerId': customer_id,
                'surveyId': survey_id,
                'rating': Decimal(str(rating)),
                'text': text,
                'sentiment': sentiment,
                'score': json.dumps(sentiment_scores),  # Store as JSON string
                'createdAt': created_at,
                'expiresAt': expires_at,
                'originalTimestamp': timestamp
            }

            # Write to DynamoDB
            try:
                table = dynamodb.Table(TABLE_NAME)
                table.put_item(Item=item)
                logger.info(f"Successfully processed survey {survey_id} with sentiment {sentiment}")

            except Exception as e:
                logger.error(f"DynamoDB error for survey {survey_id}: {str(e)}")
                batch_item_failures.append({
                    'itemIdentifier': record['messageId']
                })
                continue

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            batch_item_failures.append({
                'itemIdentifier': record['messageId']
            })
            continue
        except Exception as e:
            logger.error(f"Unexpected error processing record: {str(e)}")
            batch_item_failures.append({
                'itemIdentifier': record['messageId']
            })
            continue

    # Return batch item failures if any
    if batch_item_failures:
        return {
            'batchItemFailures': batch_item_failures
        }

    return {
        'statusCode': 200,
        'body': json.dumps('Successfully processed all records')
    }
