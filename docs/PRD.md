# Product requirements document — FailureLab

## 1. Product goal

Provide an educational cloud-resilience workbench where an engineer can define a failure hypothesis, run a bounded experiment in an isolated test environment, observe telemetry, review analysis, and compare the result with subsequent engineering changes.

## 2. Users

- Student developer demonstrating distributed-systems resilience concepts.
- Backend/platform engineer validating timeout, retry, failover and queueing behaviour.
- Evaluator reviewing experimental method, measured outputs and repeatability.

## 3. Functional requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| FR-01 | Show aggregate experiment metrics | Dashboard summary endpoint and overview cards |
| FR-02 | Show a service dependency topology | Infrastructure endpoint and topology page |
| FR-03 | Create controlled failure experiments | Form validation and 202 response |
| FR-04 | Record time-series telemetry | Metric samples visible on experiment detail page |
| FR-05 | Record an experiment event timeline | Events visible in chronological order |
| FR-06 | Calculate a resilience index | Score and component dimensions persisted |
| FR-07 | Identify anomalous metric samples | IsolationForest anomaly signal persisted |
| FR-08 | Generate diagnostic findings and recommendations | Scenario-specific report sections |
| FR-09 | Cancel queued/running local experiments | Cancel endpoint changes the state to ABORTED |
| FR-10 | Compare 2–5 completed experiments | Compare endpoint returns runs and scores |
| FR-11 | Export PDF/JSON reports | PDF starts with `%PDF`; JSON contains complete record |
| FR-12 | Persist locally | SQLite survives API restarts when volume is retained |
| FR-13 | Persist in AWS deployment | DynamoDB, S3, CloudWatch, SNS and SQS integration |
| FR-14 | Execute guarded EC2 FIS experiment | Dedicated FIS template, tags, acknowledgement and Step Functions |

## 4. Non-functional requirements

- **Safety:** local simulation by default; explicit acknowledgement and separate opt-in for real EC2 FIS.
- **Security:** Cognito JWT at API Gateway, task-role credentials, private S3, scoped FIS policy.
- **Repeatability:** deterministic baseline generation and fixed sampling strategy.
- **Observability:** store metrics and events with timestamps.
- **Maintainability:** separate API, services, frontend, infrastructure and tests.
- **Portability:** Docker Compose for local demonstration and Terraform for AWS deployment.

## 5. Experiment workflow

1. Choose a target and scenario.
2. Record the expected behaviour (hypothesis).
3. Configure duration and intensity.
4. Run the experiment.
5. Observe baseline, fault and recovery samples.
6. Inspect telemetry, events, anomaly signal and resilience dimensions.
7. Apply an engineering improvement outside FailureLab.
8. Repeat the same scenario and compare the two runs.

## 6. Out of scope for this academic release

- Arbitrary execution of shell commands on customer infrastructure.
- Unrestricted attack/fault injection against production resources.
- Multi-tenant billing or commercial SLA certification.
- Automatic code modification of the target application.
- Claiming that an anomaly score is a calibrated failure probability.
