import boto3
from datetime import datetime


def serialize_time(value):
    return value.isoformat() if isinstance(value, datetime) else value

fis = boto3.client("fis")


def handler(event, context):
    experiment_id = event.get("fis_experiment_id")
    if not experiment_id:
        raise ValueError("fis_experiment_id is missing from workflow state")
    result = fis.get_experiment(id=experiment_id)["experiment"]
    event["fis_status"] = result.get("state", {}).get("status", "unknown").lower()
    event["fis_reason"] = result.get("state", {}).get("reason", "")
    event["fis_end_time"] = serialize_time(result.get("endTime", ""))
    event["fis_start_time"] = serialize_time(result.get("startTime", ""))
    return event
