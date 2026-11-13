from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.security import require_api_key
from app.db import init_db
from app.routers import dashboard, experiments

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield

app=FastAPI(title="FailureLab API",version="1.0.0",description="Cloud resilience experiments, telemetry analysis and reports",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origin_list,allow_credentials=True,allow_methods=["GET","POST","OPTIONS"],allow_headers=["Authorization","Content-Type","X-API-Key"])
app.include_router(dashboard.router,prefix="/api/v1",dependencies=[Depends(require_api_key)])
app.include_router(experiments.router,prefix="/api/v1",dependencies=[Depends(require_api_key)])

@app.get("/health",tags=["Health"])
def health():
    return {"status":"ok","service":"failurelab-api","mode":"AWS" if settings.aws_mode else "LOCAL SIMULATION"}
