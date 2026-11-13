variable "aws_region" {
  description = "AWS region for the FailureLab environment."
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "lab"
}

variable "project_name" {
  description = "Short project identifier used in resource names."
  type        = string
  default     = "failurelab"
}

variable "vpc_cidr" {
  type        = string
  default     = "10.42.0.0/16"
  description = "VPC address range."
}

variable "deploy_backend" {
  type        = bool
  default     = false
  description = "Create the ECS service after pushing the backend image to ECR."
}

variable "backend_image_tag" {
  type        = string
  default     = "v1"
  description = "Immutable tag to deploy from the FailureLab backend ECR repository."
}

variable "backend_cpu" {
  type        = number
  default     = 512
  description = "Fargate task CPU units."
}

variable "backend_memory" {
  type        = number
  default     = 1024
  description = "Fargate task memory in MiB."
}

variable "backend_desired_count" {
  type        = number
  default     = 1
}

variable "enable_ec2_fis_lab" {
  type        = bool
  default     = false
  description = "Create a dedicated, tagged EC2 target and AWS FIS stop/restart template. Disabled by default."
}

variable "enable_real_fis" {
  type        = bool
  default     = false
  description = "Allow the API to start the dedicated AWS FIS experiment. Keep false until the lab is reviewed."
}

variable "api_allowed_origins" {
  type        = list(string)
  default     = []
  description = "Additional browser origins allowed by API Gateway. The CloudFront origin is added automatically."
}

variable "frontend_env_name" {
  type        = string
  default     = "lab"
}

variable "bedrock_model_id" {
  type        = string
  default     = ""
  description = "Optional Converse-compatible Amazon Bedrock model ID or inference-profile ARN for supplemental experiment analysis."
}
