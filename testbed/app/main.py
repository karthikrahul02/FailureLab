"""Small controllable target application used to collect real HTTP observations locally."""
import asyncio
import os
import time
from typing import Literal
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

Scenario = Literal[
    "service_unavailable", "latency_injection", "cpu_stress",
    "database_connection_exhaustion", "traffic_spike", "queue_backlog",
]

class FaultConfig(BaseModel):
    scenario: Scenario | None = None
    active: bool = False
    intensity: int = Field(default=50, ge=1, le=100)

app = FastAPI(title="FailureLab Target Testbed", version="1.0.0")
_state: dict = {"scenario": None, "active": False, "intensity": 50, "request_count": 0, "failed_count": 0, "queue_depth": 0, "active_requests": 0, "max_concurrency": 0}
_cpu_window_start = time.monotonic()
_cpu_window_process = time.process_time()
_control_token = os.getenv("TESTBED_CONTROL_TOKEN", "local-testbed-control-token")


def _require_control_token(token: str | None) -> None:
    if not token or token != _control_token:
        raise HTTPException(status_code=403, detail="Invalid testbed control token")


@app.get("/health")
def health():
    return {"status": "ok", "service": "failurelab-target-testbed"}


@app.get("/metrics")
def metrics():
    global _cpu_window_start, _cpu_window_process
    wall = max(0.001, time.monotonic() - _cpu_window_start)
    cpu = max(0.0, min(100.0, ((time.process_time() - _cpu_window_process) / wall) * 100.0))
    _cpu_window_start = time.monotonic()
    _cpu_window_process = time.process_time()
    return {
        "request_count": _state["request_count"],
        "failed_count": _state["failed_count"],
        "queue_depth": _state["queue_depth"],
        "active_requests": _state["active_requests"],
        "max_concurrency": _state["max_concurrency"],
        "process_cpu_percent": round(cpu, 2),
        "fault": {"scenario": _state["scenario"], "active": _state["active"], "intensity": _state["intensity"]},
    }


@app.get("/control/state")
def control_state(x_lab_control_token: str | None = Header(default=None)):
    _require_control_token(x_lab_control_token)
    return dict(_state)


@app.put("/control/fault")
def configure_fault(payload: FaultConfig, x_lab_control_token: str | None = Header(default=None)):
    _require_control_token(x_lab_control_token)
    _state.update({"scenario": payload.scenario, "active": payload.active, "intensity": payload.intensity})
    if not payload.active:
        _state["queue_depth"] = max(0, int(_state["queue_depth"] * 0.25))
    return {"accepted": True, "fault": {"scenario": _state["scenario"], "active": _state["active"], "intensity": _state["intensity"]}}


@app.post("/control/reset")
def reset_fault(x_lab_control_token: str | None = Header(default=None)):
    _require_control_token(x_lab_control_token)
    _state.update({"scenario": None, "active": False, "intensity": 50, "queue_depth": 0})
    return {"accepted": True, "fault": None}


@app.get("/api/checkout")
async def checkout():
    _state["request_count"] += 1
    _state["active_requests"] += 1
    _state["max_concurrency"] = max(_state["max_concurrency"], _state["active_requests"])
    scenario = _state["scenario"] if _state["active"] else None
    intensity = int(_state["intensity"])
    factor = intensity / 100.0
    sequence = int(_state["request_count"])
    try:
        if scenario == "latency_injection":
            await asyncio.sleep(0.04 + 1.10 * factor)
        elif scenario == "database_connection_exhaustion":
            await asyncio.sleep(0.03 + 0.18 * factor)
        elif scenario == "service_unavailable":
            await asyncio.sleep(0.01)
        elif scenario == "cpu_stress":
            deadline = time.perf_counter() + (0.004 + 0.045 * factor)
            value = 1
            while time.perf_counter() < deadline:
                value = (value * 1664525 + 1013904223) % 4294967296
        elif scenario == "queue_backlog":
            _state["queue_depth"] = min(250, _state["queue_depth"] + 3 + int(15 * factor))
        elif scenario == "traffic_spike":
            _state["queue_depth"] = min(250, _state["queue_depth"] + 1 + int(4 * factor))
            await asyncio.sleep(0.01 + 0.04 * factor)
        if scenario == "queue_backlog" and _state["queue_depth"] > 0:
            _state["queue_depth"] = max(0, _state["queue_depth"] - 1)
        if scenario == "traffic_spike" and _state["queue_depth"] > 0:
            _state["queue_depth"] = max(0, _state["queue_depth"] - 1)

        # Deterministic request sequence makes repeated demonstration runs reproducible.
        failure_percent = 0
        if scenario == "service_unavailable":
            failure_percent = 25 + int(70 * factor)
        elif scenario == "database_connection_exhaustion":
            failure_percent = int(12 + 65 * factor)
        elif scenario == "traffic_spike":
            failure_percent = int(4 + 18 * factor)
        if failure_percent and ((sequence * 37) % 100) < failure_percent:
            _state["failed_count"] += 1
            raise HTTPException(status_code=503, detail=f"Injected {scenario} fault")
        return {"status": "accepted", "order_id": f"demo-{sequence:06d}", "dependency": "payment-service", "fault_active": bool(scenario)}
    finally:
        _state["active_requests"] = max(0, _state["active_requests"] - 1)
