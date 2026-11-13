import asyncio
import math
import statistics
import httpx
from datetime import datetime, timezone
from typing import Any
from app.core.config import settings
from app.db import update_experiment
from app.services.analyzer import analyze_experiment
from app.services.resilience import score_resilience

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _metric_point(i: int, total: int, scenario: str, intensity: int) -> dict[str, Any]:
    progress = i / max(1, total-1); active = .25 < progress < .78; factor = intensity / 100
    latency=170+16*math.sin(i/2); error=.004+.002*abs(math.sin(i)); cpu=31+5*math.sin(i/3); availability=99.9; queue=2+(i%3)
    if active:
        if scenario == "latency_injection": latency += 900*factor
        elif scenario == "service_unavailable": latency += 1450*factor; error += .55*factor; availability -= 42*factor
        elif scenario == "cpu_stress": cpu += 68*factor; latency += 430*factor; error += .08*factor
        elif scenario == "database_connection_exhaustion": latency += 800*factor; error += .32*factor; availability -= 22*factor
        elif scenario == "traffic_spike": cpu += 48*factor; latency += 520*factor; error += .17*factor; queue += int(65*factor)
        elif scenario == "queue_backlog": queue += int(100*factor); latency += 160*factor
    elif progress >= .78:
        recovery=min(1,(progress-.78)/.22)
        latency=170+(latency-170)*(1-recovery); error=.004+(error-.004)*(1-recovery)
        cpu=31+(cpu-31)*(1-recovery); availability=99.9+(availability-99.9)*(1-recovery); queue=max(2,int(queue*(1-recovery)))
    return {"timestamp":now_iso(),"latency_ms":round(latency,1),"error_rate":round(min(.99,error),4),"cpu_percent":round(min(100,cpu),1),"availability_percent":round(max(0,availability),2),"queue_depth":max(0,queue)}

async def _sample_testbed(client: httpx.AsyncClient, item: dict[str, Any], fault_active: bool) -> dict[str, Any]:
    """Drive the isolated target testbed and measure observed HTTP outcomes."""
    control_response = await client.put("/control/fault", json={
        "scenario": item["scenario"],
        "active": fault_active,
        "intensity": item["intensity"],
    })
    control_response.raise_for_status()
    concurrency = 6
    if item["scenario"] == "traffic_spike":
        concurrency = min(20, 6 + int(14 * item["intensity"] / 100))

    async def one_request() -> tuple[int, float]:
        started = asyncio.get_running_loop().time()
        try:
            response = await client.get("/api/checkout")
            return response.status_code, (asyncio.get_running_loop().time() - started) * 1000
        except httpx.RequestError:
            return 599, (asyncio.get_running_loop().time() - started) * 1000

    results = await asyncio.gather(*(one_request() for _ in range(concurrency)))
    measured = [latency for _, latency in results]
    failed = sum(1 for code, _ in results if code >= 500)
    observed = (await client.get("/metrics")).json()
    return {
        "timestamp": now_iso(),
        "latency_ms": round(statistics.mean(measured), 1) if measured else 0,
        "error_rate": round(failed / max(1, len(results)), 4),
        "cpu_percent": round(float(observed.get("process_cpu_percent", 0)), 1),
        "availability_percent": round((len(results) - failed) / max(1, len(results)) * 100, 2),
        "queue_depth": int(observed.get("queue_depth", 0)),
        "request_count": len(results),
        "failed_requests": failed,
        "measurement_source": "live_testbed_http",
    }

async def run_simulated_experiment(experiment_id: str) -> None:
    from app.db import get_experiment
    item=get_experiment(experiment_id)
    if not item: return
    start=now_iso(); events=[{"timestamp":start,"level":"info","message":"Experiment execution started in isolated target mode." if settings.testbed_url else "Experiment execution started in synthetic simulation mode."},{"timestamp":now_iso(),"level":"info","message":f"Target {item['target']} baseline telemetry collection started."}]
    update_experiment(experiment_id,{"status":"RUNNING","started_at":start,"events":events})
    metrics=[]; total=12
    client_context = httpx.AsyncClient(
        base_url=settings.testbed_url.rstrip("/"),
        timeout=8.0,
        headers={"x-lab-control-token": settings.testbed_control_token},
    ) if settings.testbed_url else None
    run_started = asyncio.get_running_loop().time()
    interval_seconds = (float(item.get("duration_seconds", 30)) / total) * max(0.0, settings.simulation_time_scale)
    try:
        if client_context:
            await client_context.__aenter__()
        for i in range(total):
            current=get_experiment(experiment_id)
            if current and current.get("status")=="ABORTED":
                events.append({"timestamp":now_iso(),"level":"warning","message":"Experiment cancelled by user."})
                update_experiment(experiment_id,{"events":events,"completed_at":now_iso()}); return
            progress=i/max(1,total-1)
            fault_active=.25 < progress < .78
            if client_context:
                point=await _sample_testbed(client_context,item,fault_active)
            else:
                point=_metric_point(i,total,item["scenario"],item["intensity"])
                point["measurement_source"]="synthetic_model"
            metrics.append(point)
            if i==3: events.append({"timestamp":now_iso(),"level":"warning","message":f"Fault window opened: {item['scenario'].replace('_',' ')} on {item['target']}."})
            if point["error_rate"]>.08 or point["latency_ms"]>800: events.append({"timestamp":now_iso(),"level":"error","message":f"Threshold breach: latency {point['latency_ms']:.0f} ms, error rate {point['error_rate']*100:.1f}%."})
            if i==9: events.append({"timestamp":now_iso(),"level":"success","message":"Fault window closed; recovery observation started."})
            update_experiment(experiment_id,{"metrics":metrics,"events":events})
            if settings.aws_mode:
                from app.services.aws_adapters import put_cloudwatch_metrics, enqueue_event
                put_cloudwatch_metrics(experiment_id, item["target"], point)
                enqueue_event({"event_type": "telemetry.sample", "experiment_id": experiment_id, "target": item["target"], "metric": point})
            # Pace samples across the configured observation window. A scale of 0 is used only by tests.
            target_elapsed = (i + 1) * interval_seconds
            remaining = target_elapsed - (asyncio.get_running_loop().time() - run_started)
            if remaining > 0:
                await asyncio.sleep(remaining)
    except Exception as exc:
        events.append({"timestamp":now_iso(),"level":"error","message":f"Target testbed failed: {type(exc).__name__}. No synthetic fallback was used."})
        update_experiment(experiment_id,{"status":"FAILED","completed_at":now_iso(),"summary":"Experiment failed because the configured target testbed could not be measured.","events":events,"metrics":metrics})
        return
    finally:
        if client_context:
            try:
                await client_context.put("/control/fault",json={"scenario":item["scenario"],"active":False,"intensity":item["intensity"]})
                await client_context.__aexit__(None,None,None)
            except Exception:
                pass
    analysis=analyze_experiment(item["scenario"],item["target"],metrics,events)
    if settings.bedrock_model_id:
        try:
            from app.services.llm_advisor import generate_bedrock_advisory
            advisory = await asyncio.to_thread(generate_bedrock_advisory, item, metrics, analysis)
            if advisory:
                analysis["summary"] = advisory["summary"] or analysis["summary"]
                analysis["findings"] = list(dict.fromkeys(analysis["findings"] + advisory["findings"]))[:8]
                analysis["recommendations"] = list(dict.fromkeys(analysis["recommendations"] + advisory["recommendations"]))[:8]
                events.append({"timestamp":now_iso(),"level":"success","message":"Amazon Bedrock generated a supplemental telemetry advisory."})
            else:
                events.append({"timestamp":now_iso(),"level":"warning","message":"Bedrock returned an unusable advisory; deterministic analysis was retained."})
        except Exception as exc:
            events.append({"timestamp":now_iso(),"level":"warning","message":f"Bedrock advisor unavailable ({type(exc).__name__}); deterministic analysis was retained."})
    score=score_resilience(metrics,events)
    source = metrics[0].get("measurement_source", "synthetic_model") if metrics else "unknown"
    events.append({"timestamp":now_iso(),"level":"info","message":f"Telemetry source: {source}."})
    events.append({"timestamp":now_iso(),"level":"success","message":f"Experiment completed. Resilience score: {score['score']:.1f}/100."})
    update_experiment(experiment_id,{"status":"COMPLETED","completed_at":now_iso(),"resilience_score":score["score"],"anomaly_score":analysis["anomaly_score"],"summary":analysis["summary"],"findings":analysis["findings"],"recommendations":analysis["recommendations"],"events":events,"metrics":metrics})
    if settings.aws_mode:
        from app.services.aws_adapters import enqueue_event, publish_notification
        enqueue_event({"event_type": "experiment.completed", "experiment_id": experiment_id, "resilience_score": score["score"]})
        publish_notification("FailureLab experiment completed", f"Experiment {item['name']} completed with resilience score {score['score']}/100.")
