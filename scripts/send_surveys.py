#!/usr/bin/env python3
"""
Generate and send 500 survey messages to the API Gateway endpoint.
Distribution: 60% positive, 25% neutral, 15% negative
"""

import requests
import uuid
import time
import json
import os
from datetime import datetime, timezone
from typing import Dict, List

# Configuration
TOTAL_MESSAGES = 500
MESSAGES_PER_SECOND = 10

# Survey text templates by sentiment
POSITIVE_TEXTS = [
    "Excellent service! Very satisfied with the experience.",
    "Outstanding quality and great customer support. Highly recommend!",
    "Amazing product, exceeded my expectations. Will definitely buy again.",
    "Fantastic experience from start to finish. Very happy!",
    "Great value for money. The best purchase I've made this year.",
    "Love it! Everything works perfectly and the design is beautiful.",
    "Top-notch service and product quality. Couldn't be happier!",
    "Perfect! Exactly what I was looking for. Great job!",
    "Excellent customer service and fast delivery. Very impressed!",
    "Wonderful experience. The team went above and beyond.",
]

NEUTRAL_TEXTS = [
    "It's okay. Does what it's supposed to do.",
    "Average product. Nothing special but nothing wrong either.",
    "Meets basic expectations. Adequate for the price.",
    "Standard quality. Gets the job done without issues.",
    "Fair value. Not exceptional but acceptable.",
    "Decent product. Would consider buying again if needed.",
    "Average experience. Nothing to complain about.",
    "Functional and reliable. No major issues encountered.",
    "Satisfactory. Meets the minimum requirements.",
    "Okay product. Works as advertised.",
]

NEGATIVE_TEXTS = [
    "Very disappointed. The quality is poor and not worth the price.",
    "Terrible experience. Product broke after just a few uses.",
    "Not satisfied at all. Customer service was unhelpful.",
    "Poor quality. Expected much better for this price point.",
    "Disappointing purchase. Does not meet expectations.",
    "Frustrating experience. Multiple issues with the product.",
    "Waste of money. Product doesn't work as described.",
    "Very poor quality. Would not recommend to anyone.",
    "Unhappy with the purchase. Expected better quality.",
    "Disappointed. The product failed to meet basic requirements.",
]


def generate_survey_message(sentiment_type: str) -> Dict:
    """Generate a survey message with the specified sentiment."""
    survey_id = str(uuid.uuid4())
    customer_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    if sentiment_type == "positive":
        rating = 5 if uuid.uuid4().int % 2 == 0 else 4
        text = POSITIVE_TEXTS[uuid.uuid4().int % len(POSITIVE_TEXTS)]
    elif sentiment_type == "neutral":
        rating = 3
        text = NEUTRAL_TEXTS[uuid.uuid4().int % len(NEUTRAL_TEXTS)]
    else:  # negative
        rating = 1 if uuid.uuid4().int % 2 == 0 else 2
        text = NEGATIVE_TEXTS[uuid.uuid4().int % len(NEGATIVE_TEXTS)]

    return {
        "surveyId": survey_id,
        "customerId": customer_id,
        "rating": rating,
        "text": text,
        "timestamp": timestamp
    }


def send_survey_message(message: Dict, endpoint: str, api_key: str) -> bool:
    """Send a survey message to the API Gateway endpoint."""
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key
    }

    try:
        response = requests.post(
            f"{endpoint}/survey",
            headers=headers,
            json=message,
            timeout=10
        )
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error sending message: {e}")
        return False


def main():
    """Main function to generate and send survey messages."""
    # Get API endpoint and key from environment or prompt
    endpoint = os.environ.get('API_ENDPOINT', '').strip()
    api_key = os.environ.get('API_KEY', '').strip()

    if not endpoint:
        endpoint = input("Enter API Gateway endpoint URL: ").strip()
    if not api_key:
        api_key = input("Enter API key: ").strip()

    if not endpoint or not api_key:
        print("Error: Both endpoint and API key are required")
        return

    # Remove trailing slash if present
    endpoint = endpoint.rstrip('/')

    # Calculate distribution
    positive_count = int(TOTAL_MESSAGES * 0.60)  # 60%
    neutral_count = int(TOTAL_MESSAGES * 0.25)    # 25%
    negative_count = TOTAL_MESSAGES - positive_count - neutral_count  # 15%

    print(f"\nGenerating {TOTAL_MESSAGES} survey messages:")
    print(f"  - Positive: {positive_count} messages")
    print(f"  - Neutral: {neutral_count} messages")
    print(f"  - Negative: {negative_count} messages")
    print(f"\nSending at {MESSAGES_PER_SECOND} messages/second...\n")

    # Generate messages
    messages: List[Dict] = []
    messages.extend([generate_survey_message("positive") for _ in range(positive_count)])
    messages.extend([generate_survey_message("neutral") for _ in range(neutral_count)])
    messages.extend([generate_survey_message("negative") for _ in range(negative_count)])

    # Send messages
    success_count = 0
    failure_count = 0
    delay = 1.0 / MESSAGES_PER_SECOND

    for i, message in enumerate(messages, 1):
        if send_survey_message(message, endpoint, api_key):
            success_count += 1
            if i % 50 == 0:
                print(f"Sent {i}/{TOTAL_MESSAGES} messages...")
        else:
            failure_count += 1

        # Rate limiting
        if i < len(messages):
            time.sleep(delay)

    # Summary
    print(f"\n{'='*50}")
    print(f"Summary:")
    print(f"  Total messages: {TOTAL_MESSAGES}")
    print(f"  Successful: {success_count}")
    print(f"  Failed: {failure_count}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
