from typing import Any

def _clamp(value: float, low: float = 0, high: float = 100) -> float:
    return round(max(low, min(high, value)), 1)

def score_resilience(metrics: list[dict[str, Any]], events: list[dict[str, Any]]) -> dict[str, Any]:
    """Transparent project-defined index; it is not an SLA certification."""
    if not metrics:
        return {"score": 0.0, "dimensions": {"availability": 0, "recovery": 0, "error_handling": 0, "stability": 0}}
    availability = min(float(p.get("availability_percent", 100)) for p in metrics)
    error = max(float(p.get("error_rate", 0)) for p in metrics)
    latency = [float(p.get("latency_ms", 0)) for p in metrics]
    baseline = max(1.0, latency[0])
    max_ratio = max(latency) / baseline
    fault_end = min(len(metrics) - 1, int((len(metrics) - 1) * 0.78))
    recovery_idx = next((i for i in range(fault_end + 1, len(metrics))
                         if metrics[i].get("availability_percent", 0) >= 95
                         and metrics[i].get("error_rate", 1) < 0.05), len(metrics) - 1)
    recovery_span = max(1, len(metrics) - fault_end - 1)
    recovery = _clamp(100 - ((recovery_idx - (fault_end + 1)) / recovery_span) * 100)
    dimensions = {"availability": _clamp(availability), "recovery": recovery,
                  "error_handling": _clamp(100-error*100), "stability": _clamp(100-max(0, max_ratio-1)*20)}
    score = _clamp(.35*dimensions["availability"] + .25*dimensions["recovery"] + .25*dimensions["error_handling"] + .15*dimensions["stability"])
    return {"score": score, "dimensions": dimensions}
