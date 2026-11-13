from typing import Literal
from pydantic import BaseModel, Field

Scenario = Literal["service_unavailable", "latency_injection", "cpu_stress", "database_connection_exhaustion", "traffic_spike", "queue_backlog", "ec2_stop"]

class ExperimentCreate(BaseModel):
    name: str = Field(min_length=3, max_length=90)
    target: str = Field(min_length=2, max_length=60)
    scenario: Scenario
    duration_seconds: int = Field(default=30, ge=10, le=180)
    intensity: int = Field(default=50, ge=1, le=100)
    hypothesis: str = Field(default="The service should recover without losing accepted work.", max_length=500)
    acknowledge_real_aws_impact: bool = False

class CompareRequest(BaseModel):
    experiment_ids: list[str] = Field(min_length=2, max_length=5)
