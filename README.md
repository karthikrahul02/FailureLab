# FailureLab

**FailureLab — Cloud Resilience Engineering & Chaos Experiment Platform**

FailureLab lets engineers run bounded failure experiments against an isolated demo topology, observe service-level telemetry, calculate a transparent resilience index, detect anomalous metric samples, review evidence-linked findings, compare reruns, and export experiment reports.

The repository is designed as a final-year engineering project, not just a static dashboard. It includes a working local simulation mode, a FastAPI control plane, a React dashboard, a reproducible AWS/Terraform deployment, and an opt-in AWS Fault Injection Service (FIS) workflow that is restricted to a dedicated, tagged lab EC2 instance.

> **Safety default:** the application starts in local simulation mode. No AWS resources are changed unless AWS mode is configured, the dedicated FIS lab is provisioned, `ENABLE_REAL_FIS=true` is explicitly enabled, and the user acknowledges the real experiment in the UI/API.

## What is implemented

- **Experiments:** service unavailability, latency injection, CPU stress, database connection exhaustion, traffic spike, and queue backlog scenarios.
- **Telemetry:** Docker Compose runs a protected target testbed. The local experiment runner drives real HTTP requests through it and measures observed latency, error rate, availability, process CPU and queue depth. Without `TESTBED_URL`, the API uses a clearly labelled synthetic telemetry model.
- **Analysis:** Scikit-learn IsolationForest anomaly signal, scenario-aware diagnostic hypotheses, practical recommendations, a transparent weighted resilience index, and an optional Amazon Bedrock advisory grounded in aggregate measured telemetry.
- **Experiment lifecycle:** queued/running/completed/failed/aborted states, event timeline, cancellation, history, and multi-run comparison.
- **Reports:** PDF and JSON experiment reports.
- **Dashboard:** overview, service topology, experiment creation, metric charts, diagnostics, compare view, and report download.
- **Local persistence:** SQLite database and local report storage.
- **AWS persistence and integrations:** DynamoDB, S3 reports, CloudWatch custom metrics, SNS notifications, SQS event messages, and Step Functions.
- **Actual fault injection (opt-in):** AWS FIS stops and automatically restarts one EC2 instance carrying both `FailureLabManaged=true` and `FailureLabEnvironment=lab` tags. The IAM policy also enforces those tags.
- **Cloud deployment:** Terraform provisions VPC, internal ALB, API Gateway HTTP API + private VPC Link, Cognito JWT authorizer, ECS Fargate, ECR, DynamoDB, S3, CloudFront, SNS, SQS, Lambda workers, Step Functions, CloudWatch dashboard, and optional FIS test infrastructure.

## Architecture

```text
Browser
  └── CloudFront ── private S3 frontend
        │
        └── API Gateway HTTP API ── Cognito JWT authorizer
              └── VPC Link ── internal ALB ── ECS Fargate / FastAPI
                                                ├── DynamoDB (experiments/resources)
                                                ├── S3 (PDF reports)
                                                ├── CloudWatch (custom telemetry)
                                                ├── SQS (event messages)
                                                ├── SNS (completion notifications)
                                                └── Step Functions (real FIS workflow)
                                                      ├── Lambda: start FIS
                                                      ├── Lambda: poll FIS
                                                      ├── Lambda: finalise experiment
                                                      └── AWS FIS ── tagged lab EC2 target
```

In local Docker Compose mode, the FastAPI control plane writes to SQLite and drives an isolated target testbed over HTTP. If no testbed URL is configured (for example, when running only the API in a developer shell), it uses deterministic synthetic telemetry. In AWS mode, simulated scenarios still use the simulation engine but store data in DynamoDB and publish metrics/events to AWS services. When `BEDROCK_MODEL_ID` is configured, an optional Bedrock Converse call adds a supplemental narrative advisory based on aggregate experiment metrics and deterministic findings; the deterministic analysis remains the fallback. The `ec2_stop` scenario is a separate real AWS FIS path.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/PRD.md](docs/PRD.md), [docs/SAFETY.md](docs/SAFETY.md), [build and verification status](docs/BUILD_STATUS.md), and the [Postman API collection](postman/FailureLab.postman_collection.json).

## Quick start — Docker Compose

Requirements: Docker Engine and Docker Compose plugin.

```bash
cd FailureLab
docker compose up --build
```

Open:

- Web dashboard: http://localhost:8080
- API health: http://localhost:8000/health
- Swagger API docs: http://localhost:8000/docs

The local workspace uses demo sign-in; click **Enter demo workspace**. Docker Compose starts an isolated target testbed and the experiment runner measures real HTTP responses from that testbed. No AWS account or credentials are required. The testbed is reachable only on the Compose network and its fault-control endpoints require an internal token.

Stop the stack:

```bash
docker compose down
```

To remove the persisted local DB and generated reports too:

```bash
docker compose down -v
```

## Quick start — development mode

### Backend

```bash
cd backend
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # Windows: Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```

### Frontend (second terminal)

```bash
cd frontend
npm install
cp .env.example .env.local  # Windows: Copy-Item .env.example .env.local
npm run dev
```

Open http://localhost:5173. The frontend uses the demo auth mode by default.

## Run tests and lint

```bash
cd backend
PYTHONPATH=. pytest -q
```

```bash
cd frontend
npm run lint
npm run build
```

The backend test suite covers health, dashboard, experiment creation/completion, metrics and PDF export, validation, and the local-mode guard that rejects real EC2 fault injection.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Health probe |
| GET | `/api/v1/dashboard/summary` | Dashboard aggregates |
| GET | `/api/v1/dashboard/infrastructure` | Demo dependency topology |
| GET | `/api/v1/experiments` | List experiment runs |
| POST | `/api/v1/experiments` | Start a simulation or explicitly approved FIS run |
| GET | `/api/v1/experiments/{id}` | Retrieve experiment and telemetry |
| POST | `/api/v1/experiments/{id}/cancel` | Abort an in-progress run |
| POST | `/api/v1/experiments/compare` | Compare 2–5 runs |
| GET | `/api/v1/experiments/{id}/report.pdf` | Download PDF report |
| GET | `/api/v1/experiments/{id}/report.json` | Retrieve JSON report |

## AWS deployment

AWS deployment is intentionally a two-stage operation. Terraform creates the cloud foundation and ECR first; after the backend image has been pushed, a second Terraform apply creates the ECS service. This avoids deploying a service before its image exists.

**Prerequisites:** AWS account, configured AWS CLI profile, Docker, Node.js 20+, Terraform 1.6+, and an IAM principal allowed to create the resources in `infra/terraform`.

1. Read [infra/terraform/README.md](infra/terraform/README.md) and [docs/SAFETY.md](docs/SAFETY.md).
2. Run `scripts/deploy_aws.sh` from a Bash-compatible shell with the required environment variables. The script displays and requires approval of each Terraform plan before applying it; for a reviewed non-interactive run, set `CONFIRM_AWS_DEPLOY=YES`.
3. Create a Cognito user with `USER_POOL_ID`, `USER_EMAIL`, and `AWS_REGION` environment variables, then run `scripts/create_cognito_user.sh`; the script prompts for the permanent password without echoing it. The helper creates a verified user with a permanent password so the web sign-in flow works immediately.
4. Use the CloudFront URL printed by the deployment script.

AWS mode is not activated by local `.env` settings. The ECS task receives its AWS configuration from Terraform and uses an ECS task role; do not place AWS access keys in environment files or source code.

### Real AWS FIS experiments are opt-in

The default Terraform values are `enable_ec2_fis_lab=false` and `enable_real_fis=false`. For a deliberate lab deployment, set both to `true`, read the safety guide, and review all plan output before applying. This creates a billable EC2 instance and FIS template. The API will only permit the `ec2_stop` experiment when it has a configured template and the UI/API request includes explicit acknowledgement.

## Important limitations and research notes

- Docker Compose scenarios measure responses from the dedicated FailureLab target testbed. API-only development mode can use the synthetic model; the report includes the telemetry source. Neither mode represents measurements from a third-party production system.
- The AWS FIS path executes a real stop/restart experiment against the dedicated tagged test instance. The initial version records FIS lifecycle events and gives operational recommendations; it does not claim to infer an application root cause from a single infrastructure event.
- The IsolationForest model is trained against a reproducible generated healthy baseline. Report anomaly scores as comparative signals, not a clinically/operationally validated probability.
- The resilience score is a project-defined index. Its formula and weights should be disclosed in the final report and validated through repeated experiments.
- This project is an engineering prototype. It is not a production chaos platform until there is multi-tenant authorization, per-user data isolation, stronger audit retention, cost controls, deployment testing, and an independently validated experiment-safety model.

## Suggested final-year evaluation

Run at least three repeated experiments for each scenario and compare a baseline architecture against one or more resilience patterns (timeouts, retries with jitter, circuit breakers, bounded worker concurrency, and queue-based decoupling). Report latency percentiles, error rate, availability, recovery time, queue depth, anomaly flag ratio, and the resilience index. Keep workload, duration, and intensity identical when comparing variants.

## License

For academic use and extension. Add your institution's required license/attribution before public distribution.
