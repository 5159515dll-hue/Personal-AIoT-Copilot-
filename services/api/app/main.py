from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import agent, audit_logs, devices, model_providers, room, rules, sensors

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

app.include_router(room.router)
app.include_router(sensors.router)
app.include_router(devices.router)
app.include_router(rules.router)
app.include_router(agent.router)
app.include_router(audit_logs.router)
app.include_router(model_providers.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "个人空间智能物联助手接口"}
