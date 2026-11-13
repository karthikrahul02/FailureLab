# FailureLab architecture

## Logical modules

1. **Web workspace** — React + TypeScript single-page app for topology, experiment setup, telemetry charts, diagnostics and comparisons.
2. **Control plane** — FastAPI validates experiment parameters, persists experiment state, starts local runs or Step Functions, and serves reports.
3. **Experiment driver/testbed** — a protected FastAPI target service accepts scoped fault controls. The driver creates concurrent HTTP requests and measures the response outcomes. A deterministic synthetic telemetry mode is available when the testbed is not configured.
4. **Analysis engine** — IsolationForest anomaly signal plus scenario-specific diagnostic rules; findings are labelled as hypotheses. An optional Amazon Bedrock Converse advisory can provide a bounded narrative summary and recommendations using only aggregate telemetry and deterministic findings.
5. **Resilience index** — weighted availability, recovery, error-handling and stability dimensions.
6. **Persistence adapters** — SQLite locally; DynamoDB in AWS mode.
7. **AWS integration** — S3 reports, CloudWatch telemetry, SNS notifications, SQS event messages, Step Functions, AWS FIS, and optional Amazon Bedrock inference.

## Local execution sequence

```text
Browser -> FastAPI -> SQLite (QUEUED)
                 -> Background task (RUNNING)
                    -> protected target testbed HTTP workload
                    -> SQLite observed metrics/events
                    -> IsolationForest + rule analysis
                    -> optional Bedrock advisory (AWS only, opt-in)
                    -> resilience index
                    -> SQLite (COMPLETED)
                    -> PDF report on request
```

The local simulator samples 12 observations. The injected fault is active through the middle of the time series, followed by a recovery window. The experiment duration is a configured label/observation parameter in this prototype; the sample count and delay are controlled by the simulator settings.

## AWS simulated scenarios

When the backend runs with `AWS_MODE=true`, non-FIS scenarios still use the isolated simulator but persist experiment documents in DynamoDB. Each sample is also published to the `FailureLab/Lab` CloudWatch namespace and sent as an event message to SQS. Completion emits an SNS notification. Reports are written to the private S3 reports bucket.

## Real AWS FIS sequence

```text
FastAPI -> Step Functions -> Lambda start_fis -> AWS FIS
                                      ^              |
                                      |              v
                           Lambda poll_fis <- Wait / Choice loop
                                      |
                                      v
                           Lambda finalize_experiment
                                      |
                           DynamoDB + SNS notification
```

The Terraform FIS template targets only one EC2 instance carrying **both** `FailureLabManaged=true` and `FailureLabEnvironment=lab`. The FIS role policy repeats those resource-tag conditions for `ec2:StopInstances`. The action restarts the target after two minutes. The FIS template and target instance are not created by default.

## Cloud delivery path

```text
CloudFront -> private S3 bucket (OAC)
API Gateway HTTP API -> Cognito JWT authorizer -> VPC Link -> internal ALB -> ECS Fargate
```

API Gateway's private integration forwards to the ALB listener. Fargate tasks accept inbound port 8000 only from the ALB security group. The frontend S3 bucket is private and readable through CloudFront Origin Access Control.

## Data model

An experiment record is keyed by `id` and contains:

- Identity: `id`, `name`, `target`, `scenario`, `hypothesis`
- Configuration: `duration_seconds`, `intensity`, `mode`
- State: `status`, `created_at`, `started_at`, `completed_at`, `execution_arn`
- Assessment: `resilience_score`, `anomaly_score`, `summary`, `findings`, `recommendations`
- Evidence: `metrics[]`, `events[]`

Metric fields: `timestamp`, `latency_ms`, `error_rate`, `cpu_percent`, `availability_percent`, `queue_depth`.

## Security boundaries

- Demo login is only for localhost/demo; AWS frontend uses Cognito.
- API Gateway validates Cognito JWTs before forwarding requests.
- Backend runs with an ECS task role; no access keys are embedded in containers.
- S3 buckets block public access and use server-side encryption.
- FIS is disabled by default and uses tag-based allow conditions.
- Local simulation is the default and does not call AWS APIs.
