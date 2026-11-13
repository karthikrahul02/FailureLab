# Test plan

## Automated API tests

Run `cd backend && PYTHONPATH=. pytest -q`.

| Test | Expected result |
|---|---|
| Health endpoint | 200 and service status `ok` |
| Dashboard summary | 200 and expected demo topology count |
| Create latency experiment | 202 and experiment ID |
| Experiment lifecycle | reaches COMPLETED within the test timeout |
| Telemetry | has metric samples for all key indicators |
| Resilience analysis | has a numeric score |
| PDF report | HTTP 200 and `%PDF` signature |
| FIS guard | `ec2_stop` rejected in local mode |
| Input validation | invalid name/duration rejected with 422 |

## Manual UI acceptance

1. Enter the demo workspace.
2. Confirm overview cards render.
3. Open Infrastructure and verify the six-node service graph.
4. Create a latency experiment (30 seconds, moderate intensity).
5. Open the detail page and observe charts and timeline updating.
6. Verify findings, recommended actions, and scores after completion.
7. Export the PDF report.
8. Create a second run with a different scenario and compare both completed experiments.
9. Restart Docker Compose without deleting volumes and verify history remains.

## AWS acceptance (only after deliberate provisioning)

- Cognito login supplies a valid JWT.
- API Gateway rejects missing/invalid JWTs.
- ECS task passes its health check through the internal ALB.
- Local-style simulation in AWS mode writes to DynamoDB, CloudWatch, and SQS.
- Completion publishes an SNS notification.
- PDF report is written to the private S3 reports bucket.
- If and only if the dedicated FIS lab is enabled, run the acknowledged `ec2_stop` experiment and verify FIS state reaches a terminal status and EC2 automatically restarts.

## Measurement protocol for the final-year report

For a fair comparison, hold target, scenario, duration, and intensity constant. Run each variant at least three times. Record latency, error rate, minimum availability, peak CPU, queue depth, and observed recovery time. Compare baseline implementation with one improvement at a time (timeouts, retries with jitter, circuit breaker, bounded consumer concurrency). Report median and spread across runs, not only the best run.
