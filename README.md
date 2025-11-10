# AWS Survey Sentiment Analysis Pipeline

Demo pipeline: API Gateway → SQS → Lambda → Comprehend → DynamoDB with TTL.

## Architecture

```plaintext
Client → API Gateway HTTP API → SQS → Lambda → Comprehend → DynamoDB (TTL)
                                              ↓
                                            DLQ (for failures)
```

### Components

- **API Gateway HTTP API**: POST `/survey` endpoint with API key authentication
- **SQS Queues**: Main queue and Dead Letter Queue (DLQ) with redrive policy
- **Lambda Functions**:
  - Processor: Processes SQS messages, calls Comprehend, writes to DynamoDB
  - Authorizer: Validates API key from SSM Parameter Store
- **DynamoDB**: Stores survey results with TTL (365 days) and GSI on customerId
- **CloudWatch Logs**: Log groups for both Lambda functions with 1-day retention

## Prerequisites

- AWS CLI configured with appropriate credentials
- Terraform >= 1.0
- Python 3.12+ (for scripts)
- AWS region: `ap-southeast-2` (configurable in `versions.tf`)

## Deployment

### 1. Initialize Terraform

```bash
terraform init
```

### 2. Review and Customize Variables (Optional)

Edit `variables.tf` to customize:

- `project_name`: Default is `survey-sentiment`
- `environment`: Default is `dev`
- `ttl_days`: Default is `365`
- `lambda_timeout`: Default is `30` seconds
- `lambda_memory`: Default is `256` MB
- `sqs_batch_size`: Default is `10`
- `sqs_max_receive_count`: Default is `3`

### 3. Plan and Apply

```bash
# Review the plan
terraform plan

# Apply the infrastructure
terraform apply
```

### 4. Get Outputs

After deployment, retrieve the API endpoint and key:

```bash
# Get API endpoint
terraform output api_gateway_endpoint

# Get API key (sensitive)
terraform output -raw api_key_value

# Get DynamoDB table name
terraform output dynamodb_table_name
```

## Usage

### Setup Python Environment

Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

Install script dependencies:

```bash
pip install -r scripts/requirements.txt
```

### 1. Send Survey Messages

Set environment variables from Terraform outputs:

```bash
export API_ENDPOINT=$(terraform output -raw api_gateway_endpoint)
export API_KEY=$(terraform output -raw api_key_value)
```

Run the script to generate and send 500 survey messages:

```bash
python scripts/send_surveys.py
```

Alternatively, the script will prompt for these values if environment variables are not set.

**Message Distribution:**

- 60% positive (ratings 4-5)
- 25% neutral (rating 3)
- 15% negative (ratings 1-2)

Messages are sent at 10 messages/second.

### 2. View Results Dashboard

Start the Streamlit dashboard (ensure virtual environment is activated):

```bash
export DYNAMODB_TABLE_NAME=$(terraform output -raw dynamodb_table_name)
export AWS_REGION=ap-southeast-2  # Or your configured region
streamlit run scripts/dashboard.py
```

Or specify the table name in the dashboard sidebar.

The dashboard shows:

- Total surveys and average rating
- Sentiment distribution (pie/bar charts)
- Rating distribution
- Sentiment over time
- Interactive data table with filters
- Sentiment score breakdowns

### 3. Monitor the Pipeline

**CloudWatch Logs:**

- Lambda processor: `/aws/lambda/{name_prefix}-processor`
- Lambda authorizer: `/aws/lambda/{name_prefix}-authorizer`

**SQS Monitoring:**

- Check queue depth in AWS Console
- Monitor DLQ for failed messages

**DynamoDB:**

- View items in the table
- Check TTL values (expiresAt field)

## Resource Naming

All resources use the naming convention: `{project_name}-{environment}-{resource_type}`

Example: `survey-sentiment-dev-processor`, `survey-sentiment-dev-queue`

## IAM Permissions

IAM roles and permissions:

- **API Gateway → SQS**: `sqs:SendMessage` only
- **Lambda → SQS**: `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:GetQueueAttributes`
- **Lambda → Comprehend**: `comprehend:DetectSentiment`
- **Lambda → DynamoDB**: `dynamodb:PutItem` only
- **Lambda Authorizer → SSM**: `ssm:GetParameter` for API key

## Cleanup

To destroy all resources:

```bash
terraform destroy
```

CloudWatch log groups will be deleted. DynamoDB items with expired TTL are automatically deleted by AWS.

## Troubleshooting

### API Gateway Returns 401

- Verify API key is correct: `terraform output -raw api_key_value`
- Check authorizer Lambda logs in CloudWatch
- Ensure SSM parameter exists: `terraform output api_key_ssm_parameter`

### Messages Not Processing

- Check Lambda processor logs in CloudWatch
- Verify SQS event source mapping is active
- Check DLQ for failed messages
- Verify DynamoDB table exists and IAM permissions are correct

### Dashboard Shows No Data

- Ensure survey messages were sent successfully
- Check DynamoDB table for items
- Verify table name matches: `terraform output dynamodb_table_name`
- Check AWS credentials have DynamoDB read permissions

## File Structure

```plaintext
.
├── main.tf              # All AWS resources
├── variables.tf         # Input variables
├── outputs.tf           # Output values
├── locals.tf            # Common tags and naming
├── versions.tf          # Provider configuration
├── lambda/
│   ├── lambda_function.py    # SQS processor
│   └── authorizer.py         # API key authorizer
└── scripts/
    ├── send_surveys.py       # Demo workload generator
    ├── dashboard.py           # Streamlit visualization
    └── requirements.txt       # Python dependencies
```

## Implementation Summary

- API key authentication (Lambda authorizer)
- Request validation
- Partial batch failure handling
- Dead Letter Queue
- DynamoDB TTL (365 days)
- CloudWatch log groups (1 day retention)
- IAM policies with SIDs
- Resource tagging
- Streamlit dashboard

## License

See LICENSE file for details.
