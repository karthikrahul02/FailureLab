import json
import os
from datetime import datetime, timezone
from decimal import Decimal
import boto3


def iso_now():
    return datetime.now(timezone.utc).isoformat()


def to_decimal(value):
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: to_decimal(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_decimal(v) for v in value]
    return value


def handler(event, context):
    table_name = os.environ["EXPERIMENTS_TABLE"]
    table = boto3.resource("dynamodb").Table(table_name)
    fis_status = event.get("fis_status", "failed").lower()
    status = "COMPLETED" if fis_status == "completed" else "ABORTED" if fis_status in {"cancelled", "stopped"} else "FAILED"
    reason = event.get("fis_reason") or ("AWS FIS experiment completed." if status == "COMPLETED" else "AWS FIS experiment did not complete successfully.")
    events = [
        {"timestamp": event.get("fis_start_time") or iso_now(), "level": "info", "message": "AWS Fault Injection Service experiment started."},
        {"timestamp": event.get("fis_end_time") or iso_now(), "level": "success" if status == "COMPLETED" else "error", "message": reason},
    ]
    findings = ["AWS FIS executed a tagged EC2 stop/recovery experiment. Review CloudWatch metrics and the FIS event timeline before attributing an application-level root cause."]
    recommendations = ["Verify that the workload is spread across independent failure domains and that health checks remove stopped instances from service.", "Rerun the experiment after implementing resilience changes and compare recovery observations."]
    table.update_item(
        Key={"id": event["id"]},
        UpdateExpression="SET #s = :s, completed_at = :c, events = :e, findings = :f, recommendations = :r, summary = :m",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues=to_decimal({
            ":s": status,
            ":c": iso_now(),
            ":e": events,
            ":f": findings,
            ":r": recommendations,
            ":m": f"AWS FIS status: {fis_status}. {reason}",
        }),
    )
    topic = os.environ.get("SNS_TOPIC_ARN", "")
    if topic:
        boto3.client("sns").publish(
            TopicArn=topic,
            Subject=f"FailureLab experiment {status.lower()}",
            Message=json.dumps({"experiment_id": event["id"], "status": status, "reason": reason}),
        )
    return {"experiment_id": event["id"], "status": status, "fis_status": fis_status}
