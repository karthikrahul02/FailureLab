# FailureLab AWS infrastructure

Terraform provisions a complete, deliberately small AWS deployment:

- VPC across two Availability Zones, internal ALB and API Gateway VPC Link.
- API Gateway HTTP API with Cognito JWT authorizer.
- ECS Fargate control-plane service and ECR repository.
- DynamoDB experiments/resources tables.
- Private S3 buckets for PDF reports and static frontend.
- CloudFront + S3 Origin Access Control for the frontend.
- SNS completion topic and SQS event queue + DLQ.
- CloudWatch log group and dashboard.
- Lambda workers + Step Functions for AWS FIS orchestration.
- Optional tagged EC2 FIS lab target and stop/restart template.

## Prerequisites

Terraform >= 1.6, AWS CLI v2, Docker, npm/Node.js 20+, and an AWS principal allowed to provision these resources. Use a dedicated sandbox AWS account and set a billing budget first.

## Two-stage deployment

The ECS task definition points at an ECR image, so the image must be pushed before the ECS service is created.

1. Copy this file to `terraform.tfvars` and review the values:

   ```bash
   cp terraform.tfvars.example terraform.tfvars
   terraform init
   terraform plan -var-file=terraform.tfvars -var=deploy_backend=false
   terraform apply -var-file=terraform.tfvars -var=deploy_backend=false
   ```

2. Build and push the backend image:

   ```bash
   ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
   REGION=$(terraform output -raw aws_region)
   REPO=$(terraform output -raw backend_ecr_repository_url)
   aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
   docker build -t "$REPO:v1" ../../backend
   docker push "$REPO:v1"
   ```

3. Create the service and publish the frontend:

   ```bash
   terraform apply -var-file=terraform.tfvars -var=deploy_backend=true -var=backend_image_tag=v1
   ```

   Then use `scripts/deploy_aws.sh` for the complete two-stage deployment/build/upload/invalidation workflow. The script presents a saved Terraform plan for review before each apply. Set `CONFIRM_AWS_DEPLOY=YES` only for a non-interactive run after reviewing the plan; use a new `BACKEND_TAG` for each backend release because ECR tags are immutable.

## Optional Amazon Bedrock advisory

The application includes an optional Bedrock Converse advisory. It is disabled by default. To enable it, set `bedrock_model_id` in `terraform.tfvars` to a model ID or a supported inference-profile ARN, verify that the model is enabled for the selected account/Region, and review the generated `bedrock:InvokeModel` permission in the ECS task role. The application sends only experiment labels, aggregate metric summaries, and deterministic findings/recommendations; it does not send raw logs or credentials. The deterministic analysis remains available if Bedrock is not configured or the call fails. Model invocation is billable.

## Real FIS lab (optional)

The first deployment should keep:

```hcl
enable_ec2_fis_lab = false
enable_real_fis    = false
```

For a separate FIS demonstration, review `docs/SAFETY.md`, then use a new plan with both options true. This adds one billable t3.micro EC2 instance and an FIS experiment template. The template is scoped to the two FailureLab tags, the IAM policy checks those tags for both stop and restart permissions, and the FIS action requests restart after two minutes. The application UI exposes the real FIS scenario only when the frontend build receives `VITE_ENABLE_REAL_FIS=true`.

Do not run the experiment on production resources. Do not add broad EC2 permissions. Confirm the instance has no important data or workload before testing. Destroy the FIS lab when finished.

## Outputs

`terraform output` lists the CloudFront URL, API URL, ECR repository URL, Cognito IDs, DynamoDB table, report bucket, and optional FIS template/instance IDs. Create a user with `USER_POOL_ID="$(terraform output -raw cognito_user_pool_id)" USER_EMAIL="you@example.com" AWS_REGION="$(terraform output -raw aws_region)" ../../scripts/create_cognito_user.sh` (the script securely prompts for the password). The helper suppresses invitation mail and sets a permanent password so the web sign-in flow can authenticate immediately. Do not commit or paste the password into chat.

## Destroy

Export any reports and screenshots first, then:

```bash
terraform destroy -var-file=terraform.tfvars -var=deploy_backend=true
```

S3 buckets are configured for Terraform-managed cleanup. `force_destroy=true` means objects inside the FailureLab buckets can be deleted during destroy. Remove `terraform.tfvars` and state files from shared folders; they can contain infrastructure metadata.

## Notes

- The current VPC uses public subnets for Fargate tasks with public IP assignment to avoid NAT Gateway charges. Task ingress is restricted to the internal ALB security group; API clients cannot directly access task ENIs on port 8000.
- The ALB is internal and its security group accepts traffic from the VPC Link security group only.
- CloudFront uses the default CloudFront certificate. Custom domains/ACM certificates are intentionally left out of this student deployment baseline.
- Review the Terraform plan and current AWS pricing before applying. A deployed ALB, API Gateway, VPC Link, CloudFront and Fargate service can incur recurring charges even at low traffic.
