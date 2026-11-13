# FailureLab build and verification status

## Included in this source package

- React + Vite + TypeScript dashboard with Cognito and demo sign-in modes.
- FastAPI control plane with experiment lifecycle, dashboard/topology APIs, comparison APIs, PDF/JSON exports, and local SQLite persistence.
- Isolated FastAPI target testbed with token-protected fault controls and measurable HTTP behaviour for service-unavailable, latency, CPU, database-pressure, traffic-spike, and queue-backlog experiments.
- Scikit-learn IsolationForest anomaly signal, rule-based diagnostic hypotheses, a transparent project-defined resilience index, event timelines, and an opt-in Amazon Bedrock narrative advisory.
- Boto3 adapters for DynamoDB, S3, CloudWatch, SNS, SQS, and Step Functions.
- Terraform for VPC, internal ALB, API Gateway private integration + Cognito JWT authorizer, ECS Fargate, ECR, DynamoDB, private S3 + CloudFront, SNS, SQS, Lambda workers, Step Functions, CloudWatch dashboard, and an optional tag-restricted EC2/AWS FIS test.
- Docker Compose, deployment and Cognito-user scripts, GitHub Actions CI, Postman collection, PRD, architecture, safety, test, and demo documentation.

## Verification performed in the build environment

- Backend tests: **10 passed** (including Bedrock response parsing and validation; no live Bedrock call).
- Target testbed tests: **2 passed**.
- Python compile checks: passed for backend, testbed, Lambda workers, and scripts.
- TypeScript/TSX syntax transpilation: passed for all 16 frontend source files. Full TypeScript type-check/lint/build still requires installing the frontend dependencies.
- Postman collection JSON syntax: passed.
- Shell syntax checks: passed for the Bash scripts.
- Live HTTP integration check: passed; the backend drove the isolated testbed, collected 12 measured HTTP samples, and observed injected request failures.

## Not executed here

- Docker Compose build/run: Docker is not installed in this environment.
- Terraform format/validate/plan/apply: Terraform CLI is not installed in this environment.
- AWS provisioning or deployment: AWS CLI and account credentials were not available. No AWS resources were created.
- Amazon Bedrock inference: not invoked. Configure a Converse-compatible model or inference-profile ARN, enable access in the selected AWS account/Region, and review the optional IAM permission before use.
- Frontend npm install, lint, and production build: package installation could not be completed because package-registry/network access was unavailable in this environment. The source and CI workflow are included, but the frontend build remains to be verified on a machine with npm registry access.

## Important operating boundaries

- Local Docker Compose runs the application against the isolated target testbed. API-only local development without `TESTBED_URL` uses explicitly labelled synthetic telemetry.
- AWS-hosted non-FIS experiments use the simulator and AWS persistence/telemetry integrations. Only the optional `ec2_stop` scenario starts a real AWS FIS experiment.
- Both `enable_ec2_fis_lab` and `enable_real_fis` default to `false`. Keep them disabled until the safety guide and Terraform plan have been reviewed in a dedicated sandbox account.
- The IsolationForest baseline and resilience weights are project-defined demonstration methods. Validate them with repeated controlled experiments before presenting numerical results as research findings.
