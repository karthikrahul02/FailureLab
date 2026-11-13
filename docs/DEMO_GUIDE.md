# Demo walkthrough (8–10 minutes)

1. **Problem (1 min):** distributed applications fail in partial ways; standard health checks can miss cascading effects.
2. **Topology (1 min):** show the sample API, order, payment, database, queue and notification dependencies.
3. **Experiment design (1 min):** state the hypothesis for a payment latency experiment.
4. **Execution (2 min):** create and run the experiment; show queued/running/completed transitions and the fault window.
5. **Observability (1 min):** inspect latency, errors, availability, CPU and queue-depth graphs plus the event timeline.
6. **Analysis (1 min):** explain the IsolationForest anomaly signal, scenario-aware findings, and resilience dimensions.
7. **Engineering improvement (1 min):** explain a proposed circuit breaker/timeout change, then compare a before/after rerun.
8. **Cloud architecture (1 min):** show Terraform AWS architecture, Cognito, ECS, DynamoDB, CloudWatch, S3 and the optional FIS path. Be explicit about which demonstrations were local simulations and which were real AWS observations.

Do not enable the real FIS experiment during a presentation unless the dedicated lab target has been created, tagged, and verified immediately beforehand.
