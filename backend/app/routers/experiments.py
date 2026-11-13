from uuid import uuid4
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import Response
from app.core.config import settings
from app.db import create_experiment, get_experiment, list_experiments, update_experiment
from app.schemas.experiment import CompareRequest, ExperimentCreate
from app.services.reports import build_pdf_report, save_local_report
from app.services.simulator import run_simulated_experiment, now_iso

router=APIRouter(prefix="/experiments",tags=["Experiments"])

@router.get("")
def get_experiments(limit: int=Query(default=50,ge=1,le=200)):
    return list_experiments(limit)

@router.post("",status_code=202)
async def create_new_experiment(payload: ExperimentCreate, background_tasks: BackgroundTasks):
    if payload.scenario == "ec2_stop":
        if not settings.aws_mode: raise HTTPException(400,"EC2 stop is an AWS-only scenario. Use a simulated scenario locally.")
        if not settings.enable_real_fis: raise HTTPException(403,"Real AWS FIS is disabled. Enable it only after reviewing the lab safety guide.")
        if not payload.acknowledge_real_aws_impact: raise HTTPException(400,"Explicit acknowledgement is required for real AWS fault injection.")
        if not settings.fis_template_map.get("ec2_stop"): raise HTTPException(503,"No EC2 stop FIS template is configured.")
    item={"id":str(uuid4()),"name":payload.name,"target":payload.target,"scenario":payload.scenario,"duration_seconds":payload.duration_seconds,"intensity":payload.intensity,"hypothesis":payload.hypothesis,"status":"QUEUED","mode":"AWS_FIS" if settings.aws_mode else "SIMULATED","created_at":now_iso(),"events":[],"metrics":[],"findings":[],"recommendations":[]}
    saved=create_experiment(item)
    if payload.scenario == "ec2_stop":
        try:
            from app.services.aws_adapters import start_workflow
            execution_arn = start_workflow({**saved, "template_id": settings.fis_template_map["ec2_stop"]})
            update_experiment(saved["id"], {"status": "RUNNING", "execution_arn": execution_arn, "started_at": now_iso()})
        except Exception as exc:
            update_experiment(saved["id"], {"status": "FAILED", "completed_at": now_iso(), "summary": f"Could not start AWS workflow: {type(exc).__name__}"})
            raise HTTPException(502, "AWS experiment workflow could not be started. Check Step Functions and IAM configuration.") from exc
    else:
        # Ordinary scenarios remain safe, isolated simulations even when the control plane
        # itself is deployed on AWS and stores records in DynamoDB.
        background_tasks.add_task(run_simulated_experiment, saved["id"])
    return get_experiment(saved["id"])

@router.get("/{experiment_id}")
def get_experiment_by_id(experiment_id: str):
    item=get_experiment(experiment_id)
    if not item: raise HTTPException(404,"Experiment not found")
    return item

@router.post("/{experiment_id}/cancel")
def cancel_experiment(experiment_id: str):
    item=get_experiment(experiment_id)
    if not item: raise HTTPException(404,"Experiment not found")
    if item.get("status") not in {"QUEUED","RUNNING"}: raise HTTPException(409,"Only queued or running experiments can be cancelled")
    if item.get("mode") == "AWS_FIS":
        raise HTTPException(409,"Manual cancellation is disabled for a live FIS stop/restart run so its timed recovery action is not interrupted. Monitor the FIS experiment; the dedicated lab instance is configured to restart automatically.")
    update_experiment(experiment_id,{"status":"ABORTED","completed_at":now_iso()})
    return get_experiment(experiment_id)

@router.post("/compare")
def compare_experiments(payload: CompareRequest):
    items=[get_experiment(i) for i in payload.experiment_ids]
    if any(item is None for item in items): raise HTTPException(404,"One or more experiments were not found")
    return [{"id":x["id"],"name":x["name"],"scenario":x["scenario"],"target":x["target"],"status":x["status"],"resilience_score":x.get("resilience_score"),"anomaly_score":x.get("anomaly_score"),"summary":x.get("summary")} for x in items]

@router.get("/{experiment_id}/report.pdf")
def download_report(experiment_id: str):
    item=get_experiment(experiment_id)
    if not item: raise HTTPException(404,"Experiment not found")
    if item.get("status") not in {"COMPLETED","FAILED","ABORTED"}: raise HTTPException(409,"Report is available after the experiment finishes")
    content=build_pdf_report(item)
    if not settings.aws_mode: save_local_report(experiment_id,content)
    else:
        from app.services.aws_adapters import save_report
        save_report(experiment_id,content,"application/pdf")
    return Response(content,media_type="application/pdf",headers={"Content-Disposition":f"attachment; filename=failurelab-{experiment_id}.pdf"})

@router.get("/{experiment_id}/report.json")
def download_json_report(experiment_id: str):
    item=get_experiment(experiment_id)
    if not item: raise HTTPException(404,"Experiment not found")
    return item
