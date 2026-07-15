import json
from datetime import datetime

from zongce.core import (
    AiAnalysisJob, AiItemSuggestion, ScoreRule, SessionLocal, StudentProfile,
    SubmissionBatchItem, SubmissionBatchMaterial,
)
from zongce.ai.deepseek import call_deepseek_batch
from zongce.ai.extraction import extract_material_text
from zongce.ai.redaction import ensure_private, evidence_snippet, redact_text


AI_CHUNK_SIZE = 10
VALID_VERIFICATION_STATUSES = {"匹配", "不匹配", "模糊"}


def _safe_error(exc: Exception) -> str:
    message = str(exc).strip()
    allowed = (
        "AI辅助核验已关闭", "未配置 DEEPSEEK_API_KEY", "无法连接DeepSeek服务",
        "DeepSeek服务返回HTTP", "DeepSeek返回内容格式不正确", "脱敏安全检查未通过",
    )
    return message[:500] if message.startswith(allowed) else "AI分析失败，请稍后重试或人工核验"


def _payload_item(item, rule, redacted_material: str, warnings: list[str], student_name: str, student_id: str, filenames: list[str]) -> tuple[dict, str]:
    terms = [item.project_name, item.project_level, item.role_rank, item.description, item.evidence_ref]
    snippet = evidence_snippet(redacted_material, terms)
    if warnings:
        snippet = (snippet + "\n提取提示：" + "；".join(dict.fromkeys(warnings)))[:1600]
    candidate = None
    if rule:
        candidate = {
            "id": rule.id,
            "category": rule.category,
            "sub_category": rule.sub_category,
            "item_name": rule.item_name,
            "base_score": rule.base_score,
            "max_score": rule.max_score,
            "policy": rule.policy,
        }
    payload = {
        "item_id": item.id,
        "project_name": redact_text(item.project_name, student_name, student_id, filenames, 300),
        "project_level": redact_text(item.project_level, student_name, student_id, filenames, 100),
        "role_rank": redact_text(item.role_rank, student_name, student_id, filenames, 150),
        "declared_score": item.declared_score,
        "project_date": item.project_date,
        "description": redact_text(item.description, student_name, student_id, filenames, 600),
        "evidence_ref": redact_text(item.evidence_ref, student_name, student_id, filenames, 600),
        "candidate_rule": candidate,
        "redacted_evidence": snippet,
    }
    return payload, snippet


def _validated_suggestion(raw: dict, item, rule) -> dict:
    status = str(raw.get("verification_status", "模糊")).strip()
    if status not in VALID_VERIFICATION_STATUSES:
        status = "模糊"
    try:
        score = float(raw["suggested_score"]) if raw.get("suggested_score") is not None else None
        if score is not None and not 0 <= score <= 100:
            score = None
    except (TypeError, ValueError):
        score = None
    try:
        selected_rule_id = int(raw["selected_rule_id"]) if raw.get("selected_rule_id") is not None else None
    except (TypeError, ValueError):
        selected_rule_id = None
    if not rule or selected_rule_id != rule.id:
        selected_rule_id = None
    reason = str(raw.get("reason", "证据不足，建议人工核验")).strip()[:500]
    return {
        "verification_status": status,
        "suggested_score": score,
        "selected_rule_id": selected_rule_id,
        "reason": reason or "证据不足，建议人工核验",
    }


def run_analysis_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        claimed = db.query(AiAnalysisJob).filter(
            AiAnalysisJob.id == job_id,
            AiAnalysisJob.status == "pending",
        ).update({
            AiAnalysisJob.status: "running",
            AiAnalysisJob.started_at: datetime.now(),
            AiAnalysisJob.error_message: "",
        }, synchronize_session=False)
        db.commit()
        if claimed != 1:
            return
        job = db.query(AiAnalysisJob).filter(AiAnalysisJob.id == job_id).first()
        db.query(AiItemSuggestion).filter(AiItemSuggestion.job_id == job.id).delete()
        db.commit()

        student = db.query(StudentProfile).filter(StudentProfile.id == job.student_id).first()
        items = db.query(SubmissionBatchItem).filter(
            SubmissionBatchItem.batch_id == job.batch_id,
            SubmissionBatchItem.status == "valid",
        ).order_by(SubmissionBatchItem.row_number).all()
        materials = db.query(SubmissionBatchMaterial).filter(
            SubmissionBatchMaterial.batch_id == job.batch_id,
            SubmissionBatchMaterial.is_active == True,
        ).order_by(SubmissionBatchMaterial.id).all()
        filenames = [material.original_name for material in materials]
        extracted, warnings = [], []
        for material in materials:
            result = extract_material_text(material.stored_path, material.file_type)
            if result.text:
                extracted.append(result.text)
            if result.warning:
                warnings.append(result.warning)
        student_name = student.user.real_name if student and student.user else ""
        student_id = student.student_id if student else ""
        redacted_material = redact_text("\n".join(extracted), student_name, student_id, filenames)

        payloads, snippets, by_id, rules = [], {}, {}, {}
        for item in items:
            rule = db.query(ScoreRule).filter(ScoreRule.id == item.rule_id).first() if item.rule_id else None
            payload, snippet = _payload_item(item, rule, redacted_material, warnings, student_name, student_id, filenames)
            payloads.append(payload)
            snippets[item.id] = snippet
            by_id[item.id] = item
            rules[item.id] = rule

        # 序列化后的完整外发载荷再次检查，发现疑似隐私残留就中止任务。
        outbound_json = json.dumps(payloads, ensure_ascii=False)
        ensure_private(outbound_json, [student_name, student_id, *filenames])

        raw_results = []
        for start in range(0, len(payloads), AI_CHUNK_SIZE):
            raw_results.extend(call_deepseek_batch(payloads[start:start + AI_CHUNK_SIZE]))
        returned = {}
        for raw in raw_results:
            if not isinstance(raw, dict):
                continue
            try:
                item_id = int(raw.get("item_id"))
            except (TypeError, ValueError):
                continue
            if item_id in by_id:
                returned[item_id] = raw
        for item_id, item in by_id.items():
            raw = returned.get(item_id, {"verification_status": "模糊", "reason": "模型未返回该项目，需人工核验"})
            valid = _validated_suggestion(raw, item, rules[item_id])
            db.add(AiItemSuggestion(
                job_id=job.id,
                batch_item_id=item.id,
                evidence_summary=snippets[item.id],
                response_json=json.dumps(valid, ensure_ascii=False),
                **valid,
            ))
        job.status = "completed"
        job.completed_count = len(by_id)
        job.completed_at = datetime.now()
        db.commit()
    except Exception as exc:
        db.rollback()
        job = db.query(AiAnalysisJob).filter(AiAnalysisJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = _safe_error(exc)
            job.completed_at = datetime.now()
            db.commit()
    finally:
        db.close()
