locals {
  name = "${var.project_name}-${var.environment}"
  azs  = slice(data.aws_availability_zones.available.names, 0, 2)
  common_tags = {
    Project     = "FailureLab"
    Environment = var.environment
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

resource "random_id" "suffix" {
  byte_length = 3
}

# Network: public subnets host the internal ALB and Fargate tasks. The ALB is
# reachable only from the API Gateway VPC Link security group.
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = { Name = "${local.name}-vpc" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${local.name}-igw" }
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index + 1)
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = true
  tags = { Name = "${local.name}-public-${count.index + 1}" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  tags = { Name = "${local.name}-public-rt" }
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "vpc_link" {
  name        = "${local.name}-vpc-link-sg"
  description = "Egress from API Gateway VPC Link to the private ALB."
  vpc_id      = aws_vpc.main.id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${local.name}-vpc-link-sg" }
}

resource "aws_security_group" "alb" {
  name        = "${local.name}-alb-sg"
  description = "Only API Gateway VPC Link can reach the application listener."
  vpc_id      = aws_vpc.main.id
  ingress {
    description     = "API Gateway VPC Link"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.vpc_link.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${local.name}-alb-sg" }
}

resource "aws_security_group" "tasks" {
  name        = "${local.name}-tasks-sg"
  description = "Backend tasks accept traffic only from the internal ALB."
  vpc_id      = aws_vpc.main.id
  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${local.name}-tasks-sg" }
}

resource "aws_lb" "api" {
  name               = substr("${local.name}-api", 0, 32)
  internal           = true
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
  tags               = { Name = "${local.name}-internal-alb" }
}

resource "aws_lb_target_group" "api" {
  name        = substr("${local.name}-api-tg", 0, 32)
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"
  health_check {
    enabled             = true
    path                = "/health"
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
  tags = { Name = "${local.name}-api-tg" }
}

resource "aws_lb_listener" "api" {
  load_balancer_arn = aws_lb.api.arn
  port              = 8000
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# ECR, ECS Fargate and least-privilege task roles.
resource "aws_ecr_repository" "backend" {
  name                 = "${local.name}-backend"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "AES256" }
}

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${local.name}/backend"
  retention_in_days = 30
}

resource "aws_iam_role" "ecs_execution" {
  name = "${local.name}-ecs-execution"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task" {
  name = "${local.name}-ecs-task"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}

resource "aws_iam_role_policy" "ecs_task" {
  name = "${local.name}-runtime-access"
  role = aws_iam_role.ecs_task.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = concat(
      [
        { Effect = "Allow", Action = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Scan", "dynamodb:DescribeTable"], Resource = [aws_dynamodb_table.experiments.arn, aws_dynamodb_table.resources.arn] },
        { Effect = "Allow", Action = ["s3:PutObject", "s3:GetObject"], Resource = ["${aws_s3_bucket.reports.arn}/*"] },
        { Effect = "Allow", Action = ["states:StartExecution"], Resource = [aws_sfn_state_machine.fis_experiment.arn] },
        { Effect = "Allow", Action = ["sns:Publish"], Resource = [aws_sns_topic.notifications.arn] },
        { Effect = "Allow", Action = ["sqs:SendMessage"], Resource = [aws_sqs_queue.events.arn] },
        { Effect = "Allow", Action = ["cloudwatch:PutMetricData"], Resource = ["*"] }
      ],
      var.bedrock_model_id != "" ? [{
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel"]
        Resource = [startswith(var.bedrock_model_id, "arn:") ? var.bedrock_model_id : "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.bedrock_model_id}"]
      }] : []
    )
  })
}

resource "aws_ecs_cluster" "main" {
  name = "${local.name}-cluster"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_task_definition" "backend" {
  family                   = "${local.name}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.backend_cpu
  memory                   = var.backend_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn
  container_definitions = jsonencode([{
    name      = "failurelab-api"
    image     = "${aws_ecr_repository.backend.repository_url}:${var.backend_image_tag}"
    essential = true
    portMappings = [{ containerPort = 8000, hostPort = 8000, protocol = "tcp" }]
    environment = [
      { name = "APP_ENV", value = var.environment },
      { name = "AWS_MODE", value = "true" },
      { name = "AWS_REGION", value = var.aws_region },
      { name = "DYNAMODB_EXPERIMENTS_TABLE", value = aws_dynamodb_table.experiments.name },
      { name = "DYNAMODB_RESOURCES_TABLE", value = aws_dynamodb_table.resources.name },
      { name = "REPORTS_BUCKET", value = aws_s3_bucket.reports.bucket },
      { name = "SNS_TOPIC_ARN", value = aws_sns_topic.notifications.arn },
      { name = "SQS_QUEUE_URL", value = aws_sqs_queue.events.url },
      { name = "STEP_FUNCTION_ARN", value = aws_sfn_state_machine.fis_experiment.arn },
      { name = "FIS_TEMPLATE_MAP_JSON", value = jsonencode(var.enable_ec2_fis_lab ? { ec2_stop = aws_fis_experiment_template.stop_instance[0].id } : {}) },
      { name = "ENABLE_REAL_FIS", value = tostring(var.enable_real_fis && var.enable_ec2_fis_lab) },
      { name = "CORS_ORIGINS", value = "https://${aws_cloudfront_distribution.frontend.domain_name}" },
      { name = "SIMULATION_TIME_SCALE", value = "1.0" },
      { name = "TESTBED_URL", value = "" },
      { name = "BEDROCK_MODEL_ID", value = var.bedrock_model_id },
      { name = "BEDROCK_REGION", value = var.aws_region }
    ]
    logConfiguration = { logDriver = "awslogs", options = { "awslogs-group" = aws_cloudwatch_log_group.backend.name, "awslogs-region" = var.aws_region, "awslogs-stream-prefix" = "api" } }
    healthCheck = { command = ["CMD-SHELL", "python -c 'import urllib.request; urllib.request.urlopen(\"http://127.0.0.1:8000/health\", timeout=3)'"], interval = 30, timeout = 5, retries = 3, startPeriod = 30 }
  }])
  depends_on = [aws_iam_role_policy_attachment.ecs_execution, aws_iam_role_policy.ecs_task]
}

resource "aws_ecs_service" "backend" {
  count           = var.deploy_backend ? 1 : 0
  name            = "${local.name}-backend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = var.backend_desired_count
  launch_type     = "FARGATE"
  platform_version = "LATEST"
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.tasks.id]
    assign_public_ip = true
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "failurelab-api"
    container_port   = 8000
  }
  depends_on = [aws_lb_listener.api, aws_iam_role_policy.ecs_task]
}

# Application persistence and eventing.
resource "aws_dynamodb_table" "experiments" {
  name         = "${local.name}-experiments"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"
  attribute {
    name = "id"
    type = "S"
  }
  point_in_time_recovery { enabled = true }
  server_side_encryption { enabled = true }
  tags = { Name = "${local.name}-experiments" }
}

resource "aws_dynamodb_table" "resources" {
  name         = "${local.name}-resources"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"
  attribute {
    name = "id"
    type = "S"
  }
  server_side_encryption { enabled = true }
  tags = { Name = "${local.name}-resources" }
}

resource "aws_s3_bucket" "reports" {
  bucket        = "${local.name}-reports-${random_id.suffix.hex}"
  force_destroy = true
}
resource "aws_s3_bucket_public_access_block" "reports" {
  bucket                  = aws_s3_bucket.reports.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_server_side_encryption_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_sns_topic" "notifications" {
  name = "${local.name}-notifications"
}
resource "aws_sqs_queue" "events_dlq" {
  name                      = "${local.name}-events-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}
resource "aws_sqs_queue" "events" {
  name                       = "${local.name}-events"
  visibility_timeout_seconds = 60
  message_retention_seconds  = 345600
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({ deadLetterTargetArn = aws_sqs_queue.events_dlq.arn, maxReceiveCount = 4 })
}

# Dedicated lab EC2 target is opt-in. FIS can stop only instances carrying both tags.
data "aws_ssm_parameter" "al2023_ami" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}
resource "aws_security_group" "lab_instance" {
  name        = "${local.name}-fis-target-sg"
  description = "Dedicated FIS target with no inbound access."
  vpc_id      = aws_vpc.main.id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${local.name}-fis-target-sg" }
}
resource "aws_instance" "fis_target" {
  count                       = var.enable_ec2_fis_lab ? 1 : 0
  ami                         = data.aws_ssm_parameter.al2023_ami.value
  instance_type               = "t3.micro"
  subnet_id                   = aws_subnet.public[0].id
  vpc_security_group_ids      = [aws_security_group.lab_instance.id]
  associate_public_ip_address = true
  monitoring                  = false
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
  root_block_device {
    encrypted   = true
    volume_type = "gp3"
    volume_size = 8
  }
  tags = {
    Name                    = "${local.name}-fis-target"
    FailureLabManaged       = "true"
    FailureLabEnvironment   = "lab"
  }
}

resource "aws_iam_role" "fis_service" {
  name = "${local.name}-fis-service"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "fis.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_iam_role_policy" "fis_service" {
  name = "stop-only-tagged-lab-instance"
  role = aws_iam_role.fis_service.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["ec2:DescribeInstances", "ec2:DescribeInstanceStatus"], Resource = "*" },
    { Effect = "Allow", Action = ["ec2:StopInstances", "ec2:StartInstances"], Resource = "arn:aws:ec2:*:${data.aws_caller_identity.current.account_id}:instance/*", Condition = { StringEquals = { "aws:ResourceTag/FailureLabManaged" = "true", "aws:ResourceTag/FailureLabEnvironment" = "lab" } } }
  ] })
}
resource "aws_fis_experiment_template" "stop_instance" {
  count         = var.enable_ec2_fis_lab ? 1 : 0
  description   = "FailureLab test: stop one dedicated, tagged lab EC2 instance and restart it after two minutes."
  role_arn      = aws_iam_role.fis_service.arn
  stop_condition { source = "none" }
  action {
    name        = "stop-instance"
    action_id   = "aws:ec2:stop-instances"
    description = "Stop one FailureLab-managed test instance and automatically restart it."
    parameter {
      key   = "startInstancesAfterDuration"
      value = "PT2M"
    }
    target {
      key   = "Instances"
      value = "lab-instance"
    }
  }
  target {
    name           = "lab-instance"
    resource_type  = "aws:ec2:instance"
    selection_mode = "COUNT(1)"
    resource_tag {
      key   = "FailureLabManaged"
      value = "true"
    }
    resource_tag {
      key   = "FailureLabEnvironment"
      value = "lab"
    }
    filter {
      path   = "State.Name"
      values = ["running"]
    }
  }
  tags = { Name = "${local.name}-stop-lab-instance" }
  depends_on = [aws_iam_role_policy.fis_service, aws_instance.fis_target]
}

# FIS orchestration workers and Step Functions state machine.
data "archive_file" "start_fis" {
  type        = "zip"
  source_file = "${path.module}/../lambda/start_fis.py"
  output_path = "${path.module}/start_fis.zip"
}
data "archive_file" "poll_fis" {
  type        = "zip"
  source_file = "${path.module}/../lambda/poll_fis.py"
  output_path = "${path.module}/poll_fis.zip"
}
data "archive_file" "finalize_experiment" {
  type        = "zip"
  source_file = "${path.module}/../lambda/finalize_experiment.py"
  output_path = "${path.module}/finalize_experiment.zip"
}
data "archive_file" "consume_events" {
  type        = "zip"
  source_file = "${path.module}/../lambda/consume_events.py"
  output_path = "${path.module}/consume_events.zip"
}

resource "aws_iam_role" "lambda_execution" {
  name = "${local.name}-lambda-execution"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
resource "aws_iam_role_policy" "lambda_runtime" {
  role = aws_iam_role.lambda_execution.id
  name = "${local.name}-fis-worker-access"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = concat(
      [
        { Effect = "Allow", Action = ["fis:GetExperiment"], Resource = "*" },
        { Effect = "Allow", Action = ["dynamodb:UpdateItem"], Resource = aws_dynamodb_table.experiments.arn },
        { Effect = "Allow", Action = ["sns:Publish"], Resource = aws_sns_topic.notifications.arn },
        { Effect = "Allow", Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"], Resource = aws_sqs_queue.events.arn }
      ],
      var.enable_ec2_fis_lab ? [{ Effect = "Allow", Action = ["fis:StartExperiment"], Resource = aws_fis_experiment_template.stop_instance[0].arn }] : []
    )
  })
}

resource "aws_lambda_function" "start_fis" {
  function_name    = "${local.name}-start-fis"
  role             = aws_iam_role.lambda_execution.arn
  runtime          = "python3.12"
  handler          = "start_fis.handler"
  filename         = data.archive_file.start_fis.output_path
  source_code_hash = data.archive_file.start_fis.output_base64sha256
  timeout          = 30
  environment {
    variables = {
      EXPERIMENTS_TABLE = aws_dynamodb_table.experiments.name
    }
  }
  depends_on = [aws_iam_role_policy_attachment.lambda_basic, aws_iam_role_policy.lambda_runtime]
}
resource "aws_lambda_function" "poll_fis" {
  function_name    = "${local.name}-poll-fis"
  role             = aws_iam_role.lambda_execution.arn
  runtime          = "python3.12"
  handler          = "poll_fis.handler"
  filename         = data.archive_file.poll_fis.output_path
  source_code_hash = data.archive_file.poll_fis.output_base64sha256
  timeout          = 30
  depends_on       = [aws_iam_role_policy_attachment.lambda_basic, aws_iam_role_policy.lambda_runtime]
}
resource "aws_lambda_function" "finalize_experiment" {
  function_name    = "${local.name}-finalize-experiment"
  role             = aws_iam_role.lambda_execution.arn
  runtime          = "python3.12"
  handler          = "finalize_experiment.handler"
  filename         = data.archive_file.finalize_experiment.output_path
  source_code_hash = data.archive_file.finalize_experiment.output_base64sha256
  timeout          = 30
  environment {
    variables = {
      EXPERIMENTS_TABLE = aws_dynamodb_table.experiments.name
      SNS_TOPIC_ARN     = aws_sns_topic.notifications.arn
    }
  }
  depends_on = [aws_iam_role_policy_attachment.lambda_basic, aws_iam_role_policy.lambda_runtime]
}

resource "aws_lambda_function" "consume_events" {
  function_name    = "${local.name}-consume-events"
  role             = aws_iam_role.lambda_execution.arn
  runtime          = "python3.12"
  handler          = "consume_events.handler"
  filename         = data.archive_file.consume_events.output_path
  source_code_hash = data.archive_file.consume_events.output_base64sha256
  timeout          = 30
  depends_on       = [aws_iam_role_policy_attachment.lambda_basic, aws_iam_role_policy.lambda_runtime]
}
resource "aws_lambda_event_source_mapping" "events_queue" {
  event_source_arn                   = aws_sqs_queue.events.arn
  function_name                      = aws_lambda_function.consume_events.arn
  batch_size                         = 10
  function_response_types            = ["ReportBatchItemFailures"]
  maximum_batching_window_in_seconds = 5
  enabled                            = true
}

resource "aws_iam_role" "step_functions" {
  name = "${local.name}-step-functions"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "states.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_iam_role_policy" "step_functions" {
  name = "${local.name}-invoke-fis-workers"
  role = aws_iam_role.step_functions.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = ["lambda:InvokeFunction"], Resource = [aws_lambda_function.start_fis.arn, aws_lambda_function.poll_fis.arn, aws_lambda_function.finalize_experiment.arn] }] })
}
resource "aws_sfn_state_machine" "fis_experiment" {
  name     = "${local.name}-fis-experiment"
  role_arn = aws_iam_role.step_functions.arn
  type     = "STANDARD"
  definition = jsonencode({
    Comment = "Start a guarded AWS FIS experiment, poll its state, and persist the outcome.",
    StartAt = "StartFis",
    TimeoutSeconds = 7200,
    States = {
      StartFis = { Type = "Task", Resource = aws_lambda_function.start_fis.arn, Next = "WaitBeforePoll", Retry = [{ ErrorEquals = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"], IntervalSeconds = 2, MaxAttempts = 3, BackoffRate = 2.0 }] },
      WaitBeforePoll = { Type = "Wait", Seconds = 15, Next = "PollFis" },
      PollFis = { Type = "Task", Resource = aws_lambda_function.poll_fis.arn, Next = "CheckFisStatus", Retry = [{ ErrorEquals = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"], IntervalSeconds = 3, MaxAttempts = 3, BackoffRate = 2.0 }] },
      CheckFisStatus = { Type = "Choice", Choices = [
        { Variable = "$.fis_status", StringEquals = "completed", Next = "Finalize" },
        { Variable = "$.fis_status", StringEquals = "failed", Next = "Finalize" },
        { Variable = "$.fis_status", StringEquals = "cancelled", Next = "Finalize" },
        { Variable = "$.fis_status", StringEquals = "stopped", Next = "Finalize" }
      ], Default = "WaitBeforePoll" },
      Finalize = { Type = "Task", Resource = aws_lambda_function.finalize_experiment.arn, End = true }
    }
  })
  depends_on = [aws_iam_role_policy.step_functions]
}

# Amazon Cognito issues browser tokens; API Gateway validates JWTs before forwarding requests.
resource "aws_cognito_user_pool" "main" {
  name = "${local.name}-users"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    temporary_password_validity_days = 7
  }
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }
}
resource "aws_cognito_user_pool_client" "web" {
  name                                 = "${local.name}-web-client"
  user_pool_id                         = aws_cognito_user_pool.main.id
  generate_secret                      = false
  prevent_user_existence_errors        = "ENABLED"
  explicit_auth_flows                  = ["ALLOW_USER_SRP_AUTH", "ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  supported_identity_providers         = ["COGNITO"]
  access_token_validity                = 60
  id_token_validity                    = 60
  refresh_token_validity               = 30
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}

resource "aws_apigatewayv2_vpc_link" "main" {
  name               = "${local.name}-vpc-link"
  security_group_ids = [aws_security_group.vpc_link.id]
  subnet_ids         = aws_subnet.public[*].id
}
resource "aws_apigatewayv2_api" "main" {
  name          = "${local.name}-http-api"
  protocol_type = "HTTP"
  cors_configuration {
    allow_origins = concat(["https://${aws_cloudfront_distribution.frontend.domain_name}"], var.api_allowed_origins)
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["authorization", "content-type", "x-api-key"]
    expose_headers = ["content-disposition"]
    max_age       = 300
  }
}
resource "aws_apigatewayv2_authorizer" "cognito" {
  api_id           = aws_apigatewayv2_api.main.id
  authorizer_type  = "JWT"
  name             = "${local.name}-cognito-jwt"
  identity_sources = ["$request.header.Authorization"]
  jwt_configuration {
    audience = [aws_cognito_user_pool_client.web.id]
    issuer   = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.main.id}"
  }
}
resource "aws_apigatewayv2_integration" "private_alb" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "HTTP_PROXY"
  integration_method     = "ANY"
  integration_uri        = aws_lb_listener.api.arn
  connection_type        = "VPC_LINK"
  connection_id          = aws_apigatewayv2_vpc_link.main.id
  payload_format_version = "1.0"
  timeout_milliseconds   = 29000
  request_parameters     = { "overwrite:path" = "$request.path" }
}
resource "aws_apigatewayv2_route" "proxy" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "ANY /{proxy+}"
  target             = "integrations/${aws_apigatewayv2_integration.private_alb.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}
resource "aws_apigatewayv2_route" "root" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "ANY /"
  target             = "integrations/${aws_apigatewayv2_integration.private_alb.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true
}

# Private S3 static site behind CloudFront Origin Access Control.
resource "aws_s3_bucket" "frontend" {
  bucket        = "${local.name}-web-${random_id.suffix.hex}"
  force_destroy = true
}
resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${local.name}-frontend-oac"
  description                       = "Private S3 origin access for FailureLab frontend."
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}
resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  comment             = "FailureLab frontend"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"
  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "failurelab-frontend-s3"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }
  default_cache_behavior {
    target_origin_id       = "failurelab-frontend-s3"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true
    cache_policy_id        = "658327ea-f89d-4fab-a63d-7e88639e58f6" # Managed-CachingOptimized
  }
  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }
  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
  viewer_certificate {
    cloudfront_default_certificate = true
  }
  depends_on = [aws_s3_bucket_public_access_block.frontend]
}
resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Sid = "AllowCloudFrontReadOnly", Effect = "Allow", Principal = { Service = "cloudfront.amazonaws.com" }, Action = ["s3:GetObject"], Resource = "${aws_s3_bucket.frontend.arn}/*", Condition = { StringEquals = { "AWS:SourceArn" = aws_cloudfront_distribution.frontend.arn } } }] })
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${local.name}-operations"
  dashboard_body = jsonencode({ widgets = [
    { type = "metric", x = 0, y = 0, width = 12, height = 6, properties = { title = "Backend CPU", view = "timeSeries", region = var.aws_region, metrics = [["AWS/ECS", "CPUUtilization", "ClusterName", aws_ecs_cluster.main.name, "ServiceName", "${local.name}-backend"]], period = 300 } },
    { type = "metric", x = 12, y = 0, width = 12, height = 6, properties = { title = "Backend memory", view = "timeSeries", region = var.aws_region, metrics = [["AWS/ECS", "MemoryUtilization", "ClusterName", aws_ecs_cluster.main.name, "ServiceName", "${local.name}-backend"]], period = 300 } }
  ] })
}
