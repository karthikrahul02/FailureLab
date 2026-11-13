from fastapi import APIRouter
from app.db import list_experiments
from app.core.config import settings

router=APIRouter(prefix="/dashboard",tags=["Dashboard"])
SAMPLE_SERVICES=[
 {"id":"api-gateway","name":"API Gateway","type":"entry","status":"healthy","cpu":18,"latency":42,"depends_on":[]},
 {"id":"orders","name":"Order Service","type":"service","status":"healthy","cpu":34,"latency":118,"depends_on":["api-gateway","postgres"]},
 {"id":"payments","name":"Payment Service","type":"service","status":"healthy","cpu":29,"latency":164,"depends_on":["orders","postgres"]},
 {"id":"postgres","name":"PostgreSQL","type":"database","status":"healthy","cpu":41,"latency":12,"depends_on":[]},
 {"id":"notifications","name":"Notification Worker","type":"worker","status":"healthy","cpu":22,"latency":76,"depends_on":["orders","queue"]},
 {"id":"queue","name":"Message Queue","type":"queue","status":"healthy","cpu":12,"latency":8,"depends_on":[]},
]
@router.get("/summary")
def summary():
    experiments=list_experiments(200); completed=[x for x in experiments if x.get("status")=="COMPLETED"]
    scores=[float(x["resilience_score"]) for x in completed if x.get("resilience_score") is not None]
    return {"total_experiments":len(experiments),"completed_experiments":len(completed),"running_experiments":sum(x.get("status")=="RUNNING" for x in experiments),"failed_experiments":sum(x.get("status")=="FAILED" for x in experiments),"average_resilience":round(sum(scores)/len(scores),1) if scores else 0,"healthy_services":len(SAMPLE_SERVICES),"mode":"AWS" if settings.aws_mode else "LOCAL SIMULATION","recent_experiments":experiments[:6]}
@router.get("/infrastructure")
def infrastructure():
    return {"environment":"FailureLab Demo Environment","services":SAMPLE_SERVICES,"edges":[{"source":x["id"],"target":dep} for x in SAMPLE_SERVICES for dep in x["depends_on"]]}
