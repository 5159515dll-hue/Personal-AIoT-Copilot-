from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auth import api_auth_enabled, is_public_api_path, request_is_authorized
from app.routes import agent, audit_logs, devices, ingest, model_providers, room, rules, sensors, telemetry

app = FastAPI(
    title="个人空间智能物联助手接口",
    version="0.1.0",
    description="面向个人空间智能物联系统的当前版本模拟后端。",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def protect_private_api(request: Request, call_next):
    if (
        api_auth_enabled()
        and request.url.path.startswith("/api/")
        and not is_public_api_path(request.url.path)
        and request.method != "OPTIONS"
        and not request_is_authorized(request)
    ):
        return JSONResponse(
            status_code=401,
            content={"detail": "私有接口需要先通过控制台访问验证。"},
        )
    return await call_next(request)


app.include_router(room.router)
app.include_router(sensors.router)
app.include_router(devices.router)
app.include_router(ingest.router)
app.include_router(rules.router)
app.include_router(agent.router)
app.include_router(audit_logs.router)
app.include_router(model_providers.router)
app.include_router(telemetry.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "个人空间智能物联助手接口"}
