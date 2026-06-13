from __future__ import annotations

import json
import os
from pathlib import Path

from app.models import CompanionSafetyEvaluationReport, ResearchEvaluationMetric
from app.storage import data_dir
from app.time_utils import now


def report_path() -> Path:
    configured = os.getenv("AIOT_EVAL_REPORT_PATH")
    if configured:
        return Path(configured)
    return data_dir() / "companion_safety_evaluation_report.json"


def get_companion_safety_report() -> CompanionSafetyEvaluationReport:
    path = report_path()
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return CompanionSafetyEvaluationReport.model_validate(payload)
        except Exception:
            pass
    return _fallback_report()


def _fallback_report() -> CompanionSafetyEvaluationReport:
    metrics = [
        ResearchEvaluationMetric(
            id="misoperation_rate",
            label="误操作率",
            value=0,
            unit="rate",
            status="missing",
            description="尚未生成服务器评测报告，不能证明误操作率。",
        ),
        ResearchEvaluationMetric(
            id="unauthorized_call_rate",
            label="越权率",
            value=0,
            unit="rate",
            status="missing",
            description="尚未生成服务器评测报告，不能证明越权率。",
        ),
        ResearchEvaluationMetric(
            id="tool_success_rate",
            label="工具成功率",
            value=0,
            unit="rate",
            status="missing",
            description="尚未生成服务器评测报告，不能证明工具调用成功率。",
        ),
        ResearchEvaluationMetric(
            id="multi_turn_consistency_rate",
            label="多轮一致性",
            value=0,
            unit="rate",
            status="missing",
            description="尚未生成服务器评测报告，不能证明多轮一致性。",
        ),
    ]
    return CompanionSafetyEvaluationReport(
        generated_at=now(),
        source="fallback",
        total_cases=0,
        passed_cases=0,
        failed_cases=0,
        misoperation_rate=0,
        unauthorized_call_rate=0,
        tool_success_rate=0,
        multi_turn_consistency_rate=0,
        metrics=metrics,
        cases=[],
        summary="还没有找到服务器情感陪伴安全评测报告，请先运行 npm run eval:companion-safety。",
    )
