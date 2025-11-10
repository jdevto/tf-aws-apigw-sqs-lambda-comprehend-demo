variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name prefix"
  type        = string
  default     = "survey-sentiment"
}

variable "ttl_days" {
  description = "TTL in days for DynamoDB records"
  type        = number
  default     = 365
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 30
}

variable "lambda_memory" {
  description = "Lambda function memory in MB"
  type        = number
  default     = 256
}

variable "sqs_batch_size" {
  description = "SQS batch size for Lambda event source mapping"
  type        = number
  default     = 10
}

variable "sqs_max_receive_count" {
  description = "Maximum receive count before message goes to DLQ"
  type        = number
  default     = 3
}
