import numpy as np
from sklearn.ensemble import IsolationForest

FEATURES = ["latency_ms", "error_rate", "cpu_percent", "availability_percent", "queue_depth"]

def _value(point: dict, key: str, default: float = 0) -> float:
    try: return float(point.get(key, default))
    except (TypeError, ValueError): return default

def analyze_experiment(scenario: str, target: str, metrics: list[dict], events: list[dict]) -> dict:
    if not metrics:
        return {"anomaly_score": 0.0, "findings": ["No metric samples were collected."],
                "recommendations": ["Verify telemetry collection before rerunning the experiment."],
                "summary": "The experiment completed without telemetry; no reliable diagnosis is available."}
    matrix = np.array([[_value(p, k, 0) for k in FEATURES] for p in metrics], dtype=float)
    rng = np.random.default_rng(41)
    baseline = np.column_stack([rng.normal(180,25,220), rng.uniform(0,.015,220), rng.normal(32,8,220), rng.normal(99.8,.15,220), rng.poisson(2,220)])
    baseline[:,0] = np.clip(baseline[:,0],50,400); baseline[:,1] = np.clip(baseline[:,1],0,.03)
    baseline[:,2] = np.clip(baseline[:,2],1,65); baseline[:,3] = np.clip(baseline[:,3],98.5,100); baseline[:,4] = np.clip(baseline[:,4],0,12)
    model = IsolationForest(n_estimators=120, contamination=.12, random_state=41).fit(baseline)
    anomaly_ratio = float(np.mean(model.predict(matrix) == -1))
    severity = float(np.mean(np.clip(-model.score_samples(matrix), 0, 1)))
    anomaly_score = round(min(100, 100*(.65*anomaly_ratio + .35*severity)), 1)
    peak_latency=max(_value(p,"latency_ms") for p in metrics); peak_error=max(_value(p,"error_rate") for p in metrics)
    min_avail=min(_value(p,"availability_percent",100) for p in metrics); peak_cpu=max(_value(p,"cpu_percent") for p in metrics); peak_queue=max(_value(p,"queue_depth") for p in metrics)
    findings=[]; recommendations=[]
    if peak_latency > 800:
        findings.append(f"Elevated latency observed: peak response time reached {peak_latency:.0f} ms.")
        recommendations.append("Set explicit request timeouts and bounded retries with exponential backoff and jitter.")
    if peak_error > .08:
        findings.append(f"Elevated request failure rate observed: peak error rate was {peak_error*100:.1f}%.")
        recommendations.append("Use circuit breakers and graceful degradation so one failing dependency does not cascade.")
    if min_avail < 95:
        findings.append(f"Availability dropped to {min_avail:.1f}% during the experiment window.")
        recommendations.append("Add health checks, redundancy, and a tested failover path for the affected dependency.")
    if peak_cpu > 80:
        findings.append(f"CPU pressure reached {peak_cpu:.0f}%.")
        recommendations.append("Profile hot paths and configure capacity limits/autoscaling from measured demand.")
    if peak_queue > 50:
        findings.append(f"Queue backlog reached {peak_queue} messages.")
        recommendations.append("Use queue age and depth alarms, idempotent consumers, and controlled worker concurrency.")
    rules = {
      "database_connection_exhaustion": ("Database connection pressure likely propagated to dependent requests.", "Use a bounded connection pool, shorter connection lifetimes, and load shedding."),
      "service_unavailable": ("The target service outage affected dependent application paths.", "Isolate the dependency with a circuit breaker and provide a meaningful fallback response."),
      "latency_injection": ("Injected latency increased end-to-end response time.", "Define latency budgets and enforce downstream timeouts."),
      "cpu_stress": ("Compute saturation reduced service headroom.", "Set resource requests/limits and scale on saturation and queueing signals."),
      "traffic_spike": ("The workload spike stressed the request path.", "Apply rate limits, autoscaling, caching, and load shedding."),
      "queue_backlog": ("Asynchronous work accumulated faster than consumers drained it.", "Scale consumers using queue age/depth and make processing idempotent."),
      "ec2_stop": ("An EC2 stop/restart experiment was requested; inspect the AWS FIS event and recovery timeline.", "Verify multi-instance redundancy and that the workload can reschedule onto a healthy target.")}
    if scenario in rules:
        findings.append(rules[scenario][0]); recommendations.append(rules[scenario][1])
    if not findings:
        findings.append("No severe threshold breach was detected in the sampled metrics.")
        recommendations.append("Repeat the experiment with a longer observation window and compare against a baseline run.")
    if anomaly_ratio > .25:
        findings.append(f"IsolationForest flagged {anomaly_ratio*100:.0f}% of metric samples as anomalous versus the generated healthy baseline.")
        recommendations.append("Review the time-aligned metric and event timeline before assigning a root cause.")
    findings=list(dict.fromkeys(findings)); recommendations=list(dict.fromkeys(recommendations))
    summary=f"{target} was tested with {scenario.replace('_',' ')}. Minimum availability was {min_avail:.1f}%, peak latency was {peak_latency:.0f} ms, and the telemetry anomaly score was {anomaly_score:.1f}/100. These are experiment observations, not proof of a single root cause."
    return {"anomaly_score": anomaly_score, "findings": findings, "recommendations": recommendations, "summary": summary}
