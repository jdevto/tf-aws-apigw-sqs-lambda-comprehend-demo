# Data source for current AWS region
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# SQS Dead Letter Queue
resource "aws_sqs_queue" "dlq" {
  name                      = "${local.name_prefix}-dlq"
  message_retention_seconds = 1209600 # 14 days

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-dlq"
  })
}

# SQS Main Queue
resource "aws_sqs_queue" "main" {
  name                      = "${local.name_prefix}-queue"
  message_retention_seconds = 1209600 # 14 days

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.sqs_max_receive_count
  })

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-queue"
  })
}

# DynamoDB Table
resource "aws_dynamodb_table" "survey_results" {
  name         = "${local.name_prefix}-results"
  billing_mode = "PAY_PER_REQUEST"

  hash_key = "pk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "customerId"
    type = "S"
  }

  ttl {
    attribute_name = "expiresAt"
    enabled        = true
  }

  global_secondary_index {
    name            = "customerId-index"
    hash_key        = "customerId"
    projection_type = "ALL"
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-results"
  })
}

# IAM Role for API Gateway to send messages to SQS
resource "aws_iam_role" "api_gateway_sqs" {
  name = "${local.name_prefix}-apigw-sqs-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "apigateway.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-apigw-sqs-role"
  })
}

resource "aws_iam_role_policy" "api_gateway_sqs" {
  name = "${local.name_prefix}-apigw-sqs-policy"
  role = aws_iam_role.api_gateway_sqs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowSQSSendMessage"
        Effect = "Allow"
        Action = [
          "sqs:SendMessage"
        ]
        Resource = aws_sqs_queue.main.arn
      }
    ]
  })
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda" {
  name = "${local.name_prefix}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-lambda-role"
  })
}

resource "aws_iam_role_policy" "lambda_sqs" {
  name = "${local.name_prefix}-lambda-sqs-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowSQSRead"
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.main.arn
      },
      {
        Sid    = "AllowSQSWrite"
        Effect = "Allow"
        Action = [
          "sqs:DeleteMessage"
        ]
        Resource = aws_sqs_queue.main.arn
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_comprehend" {
  name = "${local.name_prefix}-lambda-comprehend-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowComprehendDetectSentiment"
        Effect = "Allow"
        Action = [
          "comprehend:DetectSentiment"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_dynamodb" {
  name = "${local.name_prefix}-lambda-dynamodb-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowDynamoDBWrite"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem"
        ]
        Resource = aws_dynamodb_table.survey_results.arn
      }
    ]
  })
}

# CloudWatch Logs policy for Lambda
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# CloudWatch Log Group for Lambda processor
resource "aws_cloudwatch_log_group" "lambda_processor" {
  name              = "/aws/lambda/${local.name_prefix}-processor"
  retention_in_days = 1

  lifecycle {
    prevent_destroy = false
  }

  tags = merge(local.common_tags, {
    Name = "/aws/lambda/${local.name_prefix}-processor"
  })
}

# Lambda function
resource "aws_lambda_function" "process_survey" {
  filename      = data.archive_file.lambda_zip.output_path
  function_name = "${local.name_prefix}-processor"
  role          = aws_iam_role.lambda.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.13"
  timeout       = var.lambda_timeout
  memory_size   = var.lambda_memory

  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.survey_results.name
      TTL_DAYS   = var.ttl_days
    }
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-processor"
  })

  depends_on = [aws_cloudwatch_log_group.lambda_processor]
}

# Archive Lambda function code
# Note: No dependencies needed - boto3 is included in Python 3.13 runtime
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda"
  output_path = "${path.module}/lambda.zip"
}

# SQS Event Source Mapping for Lambda
resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  event_source_arn = aws_sqs_queue.main.arn
  function_name    = aws_lambda_function.process_survey.arn
  batch_size       = var.sqs_batch_size

  function_response_types = ["ReportBatchItemFailures"]
}

# API Gateway HTTP API
resource "aws_apigatewayv2_api" "http_api" {
  name          = "${local.name_prefix}-api"
  protocol_type = "HTTP"
  description   = "Survey sentiment analysis API"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["POST", "OPTIONS"]
    allow_headers = ["content-type", "x-api-key"]
    max_age       = 300
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-api"
  })
}

# API Gateway Stage
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_rate_limit  = 100
    throttling_burst_limit = 200
  }
}

# API Gateway Integration
resource "aws_apigatewayv2_integration" "sqs" {
  api_id           = aws_apigatewayv2_api.http_api.id
  integration_type = "AWS_PROXY"

  credentials_arn = aws_iam_role.api_gateway_sqs.arn

  integration_subtype = "SQS-SendMessage"

  request_parameters = {
    "QueueUrl"    = aws_sqs_queue.main.url
    "MessageBody" = "$request.body"
  }

  payload_format_version = "1.0"
}

# API Gateway Route
resource "aws_apigatewayv2_route" "survey" {
  api_id             = aws_apigatewayv2_api.http_api.id
  route_key          = "POST /survey"
  authorization_type = "CUSTOM"
  authorizer_id      = aws_apigatewayv2_authorizer.api_key.id

  target = "integrations/${aws_apigatewayv2_integration.sqs.id}"
}

# API Key (stored as SSM parameter for Lambda authorizer)
resource "aws_ssm_parameter" "api_key" {
  name        = "/${local.name_prefix}/api-key"
  description = "API key for survey API"
  type        = "SecureString"
  value       = random_password.api_key.result

  tags = merge(local.common_tags, {
    Name = "/${local.name_prefix}/api-key"
  })
}

# Generate random API key
resource "random_password" "api_key" {
  length  = 32
  special = true
}

# CloudWatch Log Group for Lambda authorizer
resource "aws_cloudwatch_log_group" "lambda_authorizer" {
  name              = "/aws/lambda/${local.name_prefix}-authorizer"
  retention_in_days = 1

  lifecycle {
    prevent_destroy = false
  }

  tags = merge(local.common_tags, {
    Name = "/aws/lambda/${local.name_prefix}-authorizer"
  })
}

# Lambda Authorizer for API key validation
resource "aws_lambda_function" "api_authorizer" {
  filename      = data.archive_file.authorizer_zip.output_path
  function_name = "${local.name_prefix}-authorizer"
  role          = aws_iam_role.lambda_authorizer.arn
  handler       = "authorizer.lambda_handler"
  runtime       = "python3.13"
  timeout       = 5
  memory_size   = 128

  source_code_hash = data.archive_file.authorizer_zip.output_base64sha256

  environment {
    variables = {
      API_KEY_PARAM = aws_ssm_parameter.api_key.name
    }
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-authorizer"
  })

  depends_on = [aws_cloudwatch_log_group.lambda_authorizer]
}

# IAM Role for Lambda Authorizer
resource "aws_iam_role" "lambda_authorizer" {
  name = "${local.name_prefix}-authorizer-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-authorizer-role"
  })
}

resource "aws_iam_role_policy" "lambda_authorizer_ssm" {
  name = "${local.name_prefix}-authorizer-ssm-policy"
  role = aws_iam_role.lambda_authorizer.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowSSMRead"
        Effect = "Allow"
        Action = [
          "ssm:GetParameter"
        ]
        Resource = aws_ssm_parameter.api_key.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_authorizer_logs" {
  role       = aws_iam_role.lambda_authorizer.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Archive authorizer code
data "archive_file" "authorizer_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda/authorizer.py"
  output_path = "${path.module}/authorizer.zip"
}

# API Gateway Authorizer
resource "aws_apigatewayv2_authorizer" "api_key" {
  api_id                            = aws_apigatewayv2_api.http_api.id
  authorizer_type                   = "REQUEST"
  authorizer_uri                    = aws_lambda_function.api_authorizer.invoke_arn
  identity_sources                  = ["$request.header.x-api-key"]
  name                              = "api-key-authorizer"
  authorizer_payload_format_version = "2.0"
}

# Grant API Gateway permission to invoke authorizer
resource "aws_lambda_permission" "api_gateway_authorizer" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api_authorizer.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}
