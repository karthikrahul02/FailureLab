"""AWS adapters. Clients are lazy so local mode requires no AWS credentials."""
import json
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any
import boto3
from app.core.config import settings

def _client(service: str):
    return boto3.client(service, region_name=settings.aws_region)

def _resource(service: str):
    return boto3.resource(service, region_name=settings.aws_region)

def _to_dynamodb(value: Any) -> Any:
    """Convert Python floats recursively because boto3 DynamoDB rejects float values."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: _to_dynamodb(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_dynamodb(item) for item in value]
    if isinstance(value, tuple):
        return [_to_dynamodb(item) for item in value]
    return value


def _from_dynamodb(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _from_dynamodb(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_from_dynamodb(item) for item in value]
    return value


class AwsStore:
    def __init__(self):
        if not settings.dynamodb_experiments_table:
            raise RuntimeError("DYNAMODB_EXPERIMENTS_TABLE is not configured")
        self.table = _resource("dynamodb").Table(settings.dynamodb_experiments_table)
    def create_experiment(self, item: dict[str, Any]) -> dict[str, Any]:
        record = dict(item)
        record.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        record.setdefault("status", "QUEUED"); record.setdefault("mode", "AWS_FIS")
        for key in ("events", "metrics", "findings", "recommendations"): record.setdefault(key, [])
        self.table.put_item(Item=_to_dynamodb(record), ConditionExpression="attribute_not_exists(id)")
        return record
    def update_experiment(self, experiment_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        names={}; values={}; sets=[]
        for idx,(key,value) in enumerate(patch.items()):
            names[f"#k{idx}"]=key; values[f":v{idx}"]=value; sets.append(f"#k{idx} = :v{idx}")
        if not sets: return self.get_experiment(experiment_id)
        result=self.table.update_item(Key={"id":experiment_id}, UpdateExpression="SET "+", ".join(sets), ExpressionAttributeNames=names, ExpressionAttributeValues=_to_dynamodb(values), ReturnValues="ALL_NEW")
        attrs = result.get("Attributes")
        return _from_dynamodb(attrs) if attrs else None
    def get_experiment(self, experiment_id: str) -> dict[str, Any] | None:
        item = self.table.get_item(Key={"id":experiment_id}, ConsistentRead=True).get("Item")
        return _from_dynamodb(item) if item else None
    def list_experiments(self, limit: int = 50) -> list[dict[str, Any]]:
        items=self.table.scan(Limit=limit).get("Items", [])
        return sorted((_from_dynamodb(item) for item in items), key=lambda x:x.get("created_at", ""), reverse=True)[:limit]

aws_store = AwsStore() if settings.aws_mode else None

def start_workflow(experiment: dict[str, Any]) -> str:
    if not settings.step_function_arn: raise RuntimeError("STEP_FUNCTION_ARN is not configured")
    response=_client("stepfunctions").start_execution(
        stateMachineArn=settings.step_function_arn,
        name=f"failurelab-{experiment['id']}"[:80],
        input=json.dumps({"experiment": experiment}, default=str),
    )
    return response["executionArn"]

def save_report(experiment_id: str, content: bytes, content_type: str) -> str:
    if not settings.reports_bucket: raise RuntimeError("REPORTS_BUCKET is not configured")
    key=f"reports/{experiment_id}/report.pdf"
    _client("s3").put_object(Bucket=settings.reports_bucket, Key=key, Body=content, ContentType=content_type, ServerSideEncryption="AES256")
    return f"s3://{settings.reports_bucket}/{key}"

def publish_notification(subject: str, message: str) -> None:
    if settings.sns_topic_arn:
        _client("sns").publish(TopicArn=settings.sns_topic_arn, Subject=subject[:100], Message=message)

def enqueue_event(payload: dict[str, Any]) -> None:
    if settings.sqs_queue_url:
        _client("sqs").send_message(QueueUrl=settings.sqs_queue_url, MessageBody=json.dumps(payload, default=str))


def put_cloudwatch_metrics(experiment_id: str, target: str, point: dict[str, Any]) -> None:
    """Publish one simulated telemetry sample to the FailureLab namespace in AWS mode."""
    _client("cloudwatch").put_metric_data(
        Namespace=settings.cloudwatch_namespace,
        MetricData=[
            {"MetricName": "LatencyMs", "Dimensions": [{"Name": "ExperimentId", "Value": experiment_id}, {"Name": "Target", "Value": target}], "Value": float(point.get("latency_ms", 0)), "Unit": "Milliseconds"},
            {"MetricName": "ErrorRate", "Dimensions": [{"Name": "ExperimentId", "Value": experiment_id}, {"Name": "Target", "Value": target}], "Value": float(point.get("error_rate", 0)), "Unit": "None"},
            {"MetricName": "CpuPercent", "Dimensions": [{"Name": "ExperimentId", "Value": experiment_id}, {"Name": "Target", "Value": target}], "Value": float(point.get("cpu_percent", 0)), "Unit": "Percent"},
            {"MetricName": "AvailabilityPercent", "Dimensions": [{"Name": "ExperimentId", "Value": experiment_id}, {"Name": "Target", "Value": target}], "Value": float(point.get("availability_percent", 0)), "Unit": "Percent"},
            {"MetricName": "QueueDepth", "Dimensions": [{"Name": "ExperimentId", "Value": experiment_id}, {"Name": "Target", "Value": target}], "Value": float(point.get("queue_depth", 0)), "Unit": "Count"},
        ],
    )
