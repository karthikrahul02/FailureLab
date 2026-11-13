"""Start the pre-approved FIS template and persist its AWS experiment ID."""
import os
from datetime import datetime, timezone

import boto3

fis = boto3.client("fis")

def handler(event, context):
    experiment = event["experiment"]
    template_id = experiment.get("template_id") or os.environ.get("FIS_TEMPLATE_ID", "")
    if not template_id:
        raise ValueError("No FIS experiment template ID was supplied")

    response = fis.start_experiment(
        experimentTemplateId=template_id,
        clientToken=experiment["id"],
        tags={
            "ManagedBy": "FailureLab",
            "FailureLabExperimentId": experiment["id"],
            "Environment": "lab",
        },
    )
    fis_experiment = response["experiment"]
    experiment["fis_experiment_id"] = fis_experiment["id"]
    experiment["fis_status"] = fis_experiment.get("state", {}).get("status", "initiating").lower()
    experiment["fis_start_time"] = datetime.now(timezone.utc).isoformat()

    table_name = os.environ.get("EXPERIMENTS_TABLE", "")
    if table_name:
        table = boto3.resource("dynamodb").Table(table_name)
        table.update_item(
            Key={"id": experiment["id"]},
            UpdateExpression="SET fis_experiment_id = :fis, started_at = :started",
            ExpressionAttributeValues={
                ":fis": experiment["fis_experiment_id"],
                ":started": experiment["fis_start_time"],
            },
        )
    return experiment
