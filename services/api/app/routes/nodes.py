from fastapi import APIRouter

from app.device_connections import list_nodes
from app.models import NodeSummary

router = APIRouter(prefix="/api", tags=["nodes"])


@router.get("/nodes", response_model=list[NodeSummary])
def get_nodes() -> list[NodeSummary]:
    """真实接入节点 + 各自传感器一览（前端"节点→传感器"视图的数据源）。"""
    return list_nodes()
