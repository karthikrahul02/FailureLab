terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.70, < 7.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.6, < 4.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = ">= 2.6, < 3.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "FailureLab"
      ManagedBy   = "Terraform"
      Environment = var.environment
    }
  }
}
