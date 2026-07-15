import json
from datetime import datetime

from zongce.ai.deepseek import call_deepseek_batch
from zongce.ai.extraction import extract_material_text
from zongce.ai.redaction import ensure_private, evidence_snippet, redact_text
from zongce.ai.task_service import _safe_error, _validated_suggestion
from zongce.core import ApplicationAiAnalysis, ScoreApplication, SessionLocal


def run_application_analysis(analysis_id: int) -> None:
    db = SessionLocal()
    try:
        claimed = db.query(ApplicationAiAnalysis).filter(
            ApplicationAiAnalysis.id == analysis_id,
            ApplicationAiAnalysis.status == "pending",
        ).update({
            ApplicationAiAnalysis.status: "running",
            ApplicationAiAnalysis.started_at: datetime.now(),
            ApplicationAiAnalysis.error_message: "",
        }, synchronize_session=False)
        db.commit()
        if claimed != 1:
            return
        analysis = db.query(ApplicationAiAnalysis).filter(ApplicationAiAnalysis.id == analysis_id).first()
        application = db.query(ScoreApplication).filter(ScoreApplication.id == analysis.application_id).first()
        if not application or not application.student or not application.evidence_files:
            raise RuntimeError("申请或证明材料不存在")
        student = application.student
        filenames = [item.file_name for item in application.evidence_files]
        extracted, warnings = [], []
        for material in application.evidence_files:
            result = extract_material_text(material.file_path, material.file_type)
            if result.text:
                extracted.append(result.text)
            if result.warning:
                warnings.append(result.warning)
        student_name = student.user.real_name if student.user else ""
        redacted = redact_text("\n".join(extracted), student_name, student.student_id, filenames)
        terms = [application.project_name, application.project_level, application.description, application.remark]
        snippet = evidence_snippet(redacted, terms)
        if warnings:
            snippet = (snippet + "\n提取提示：" + "；".join(dict.fromkeys(warnings)))[:1600]
        rule = application.rule
        payload = {
            "item_id": application.id,
            "project_name": redact_text(application.project_name, student_name, student.student_id, filenames, 300),
            "project_level": redact_text(application.project_level, student_name, student.student_id, filenames, 100),
            "role_rank": str(application.team_rank),
            "declared_score": application.system_calculated_score,
            "project_date": application.project_date,
            "description": redact_text(application.description, student_name, student.student_id, filenames, 600),
            "evidence_ref": "",
            "candidate_rule": {
                "id": rule.id,
                "category": rule.category,
                "sub_category": rule.sub_category,
                "item_name": rule.item_name,
                "base_score": rule.base_score,
                "max_score": rule.max_score,
                "policy": rule.policy,
            } if rule else None,
            "redacted_evidence": snippet,
        }
        ensure_private(json.dumps(payload, ensure_ascii=False), [student_name, student.student_id, *filenames])
        returned = call_deepseek_batch([payload])
        raw = next((item for item in returned if str(item.get("item_id")) == str(application.id)), {})
        valid = _validated_suggestion(raw, application, rule)
        analysis.status = "completed"
        analysis.verification_status = valid["verification_status"]
        analysis.suggested_score = valid["suggested_score"]
        analysis.selected_rule_id = valid["selected_rule_id"]
        analysis.reason = valid["reason"]
        analysis.evidence_summary = snippet
        analysis.completed_at = datetime.now()
        db.commit()
    except Exception as exc:
        db.rollback()
        analysis = db.query(ApplicationAiAnalysis).filter(ApplicationAiAnalysis.id == analysis_id).first()
        if analysis:
            analysis.status = "failed"
            analysis.error_message = _safe_error(exc)
            analysis.completed_at = datetime.now()
            db.commit()
    finally:
        db.close()
