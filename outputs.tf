output "api_gateway_endpoint" {
  description = "API Gateway HTTP API endpoint URL"
  value       = aws_apigatewayv2_api.http_api.api_endpoint
}

output "api_key_value" {
  description = "API key value for authentication (stored in SSM)"
  value       = random_password.api_key.result
  sensitive   = true
}

output "api_key_ssm_parameter" {
  description = "SSM parameter name for API key"
  value       = aws_ssm_parameter.api_key.name
}

output "sqs_queue_url" {
  description = "Main SQS queue URL"
  value       = aws_sqs_queue.main.url
}

output "sqs_queue_arn" {
  description = "Main SQS queue ARN"
  value       = aws_sqs_queue.main.arn
}

output "sqs_dlq_url" {
  description = "Dead Letter Queue URL"
  value       = aws_sqs_queue.dlq.url
}

output "dynamodb_table_name" {
  description = "DynamoDB table name"
  value       = aws_dynamodb_table.survey_results.name
}

output "dynamodb_table_arn" {
  description = "DynamoDB table ARN"
  value       = aws_dynamodb_table.survey_results.arn
}

output "lambda_function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.process_survey.function_name
}

output "lambda_function_arn" {
  description = "Lambda function ARN"
  value       = aws_lambda_function.process_survey.arn
}
