"""Minimal SQS consumer: structured logging makes telemetry events searchable in CloudWatch."""
import json


def handler(event, context):
    failures = []
    for record in event.get("Records", []):
        try:
            payload = json.loads(record.get("body", "{}"))
            print(json.dumps({
                "component": "failurelab-event-consumer",
                "message_id": record.get("messageId"),
                "event_type": payload.get("event_type", "unknown"),
                "experiment_id": payload.get("experiment_id"),
                "target": payload.get("target"),
            }))
        except Exception:
            failures.append({"itemIdentifier": record.get("messageId", "unknown")})
    return {"batchItemFailures": failures}
