# FailureLab safety and operational guardrails

## Safe-by-default operating modes

**Local simulation (default):** all faults are generated as controlled telemetry in the FailureLab process. No AWS resources are touched.

**AWS-hosted simulation:** ordinary scenarios still generate synthetic telemetry, while storing state in DynamoDB and publishing custom CloudWatch metrics/events. This does not inject faults into the deployed AWS control plane.

**AWS FIS mode (explicit opt-in):** one purpose-built EC2 target is created and tagged. The FIS template targets that tag pair and the FIS role has matching resource-tag conditions on `ec2:StopInstances` and the timed recovery `ec2:StartInstances` action.

## Before enabling FIS

1. Use a separate AWS account or dedicated sandbox account.
2. Read the generated Terraform plan; verify only the FailureLab lab resources are included.
3. Set `enable_ec2_fis_lab=true` to create the dedicated EC2 test target and FIS template.
4. Set `enable_real_fis=true` only after verifying the target and policy.
5. Confirm the target has no user data, production workloads, or irreplaceable state.
6. Keep the FIS action's automatic restart duration enabled.
7. Monitor the FIS experiment and confirm the instance returns to service.
8. Destroy the target and template when the project demonstration is finished.

## Permission boundaries

The generated FIS role allows `DescribeInstances` and `DescribeInstanceStatus`, and allows `StopInstances` and the timed recovery `StartInstances` only when both resource tags match the FailureLab lab tags. Do not broaden this role to all EC2 instances. The dedicated target has no inbound security-group rules and requires IMDSv2.

## Cost controls

- AWS resources incur charges while provisioned; CloudFront, API Gateway, load balancers, Fargate, EC2, S3, DynamoDB, and CloudWatch may each contribute to cost.
- The optional EC2 FIS target is disabled by default.
- Use low-cost Fargate sizing and small data volumes for academic tests.
- Set an AWS Budget and billing alert before deployment.
- Run `terraform destroy` after exporting required project evidence.

## Evidence and academic integrity

Distinguish synthetic local telemetry from real AWS FIS observations in screenshots, tables and the report. Synthetic observations must never be described as production measurements. The resilience score is an internally defined comparison metric, not an external certification or availability SLA.
