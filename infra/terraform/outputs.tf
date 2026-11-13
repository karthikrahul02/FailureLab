output "frontend_url" {
  description = "CloudFront URL for the FailureLab web application."
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}
output "api_url" {
  description = "Authenticated API Gateway HTTP API URL."
  value       = aws_apigatewayv2_api.main.api_endpoint
}
output "frontend_bucket" { value = aws_s3_bucket.frontend.bucket }
output "backend_ecr_repository_url" { value = aws_ecr_repository.backend.repository_url }
output "backend_cluster_name" { value = aws_ecs_cluster.main.name }
output "backend_service_name" { value = try(aws_ecs_service.backend[0].name, "") }
output "cognito_user_pool_id" { value = aws_cognito_user_pool.main.id }
output "cognito_app_client_id" { value = aws_cognito_user_pool_client.web.id }
output "experiments_table" { value = aws_dynamodb_table.experiments.name }
output "fis_experiment_template_arn" {
  value = try(
    "arn:aws:fis:${var.aws_region}:${data.aws_caller_identity.current.account_id}:experiment-template/${aws_fis_experiment_template.stop_instance[0].id}",
    ""
  )
}
output "fis_lab_instance_id" { value = try(aws_instance.fis_target[0].id, "") }
output "reports_bucket" { value = aws_s3_bucket.reports.bucket }
output "cloudwatch_dashboard_name" { value = aws_cloudwatch_dashboard.main.dashboard_name }
output "aws_region" { value = var.aws_region }
output "cloudfront_distribution_id" { value = aws_cloudfront_distribution.frontend.id }
output "real_fis_enabled" { value = var.enable_real_fis && var.enable_ec2_fis_lab }
