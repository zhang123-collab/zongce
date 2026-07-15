from datetime import datetime, timedelta
from fastapi import APIRouter, BackgroundTasks

from zongce.core import *
from zongce.ai.deepseek import ai_config
from zongce.ai.extraction import ocr_available
from zongce.ai.task_service import run_analysis_job
from zongce.ai.application_service import run_application_analysis
from zongce.accounting_service import is_student_finalized
from zongce.batch_service import BATCH_CONFIRMED, BATCH_PARSED


router = APIRouter()


def _can_access_job(db: Session, user: User, job: AiAnalysisJob) -> bool:
    if user.role == ROLE_ADMIN:
        return True
    student = db.query(StudentProfile).filter(StudentProfile.id == job.student_id).first()
    if not student:
        return False
    if user.role == ROLE_STUDENT:
        return student.user_id == user.id
    return bool(user.role == ROLE_TEACHER and user.managed_class and student.class_name == user.managed_class)


def ai_job_data(db: Session, job: AiAnalysisJob) -> dict:
    suggestions = db.query(AiItemSuggestion).filter(
        AiItemSuggestion.job_id == job.id,
    ).order_by(AiItemSuggestion.batch_item_id).all()
    return {
        "id": job.id,
        "batchId": job.batch_id,
        "status": job.status,
        "provider": job.provider,
        "model": job.model,
        "itemCount": job.item_count,
        "completedCount": job.completed_count,
        "errorMessage": job.error_message,
        "createdAt": job.created_at.strftime("%Y-%m-%d %H:%M:%S") if job.created_at else "",
        "completedAt": job.completed_at.strftime("%Y-%m-%d %H:%M:%S") if job.completed_at else "",
        "advisoryOnly": True,
        "suggestions": [{
            "itemId": suggestion.batch_item_id,
            "verificationStatus": suggestion.verification_status,
            "suggestedScore": suggestion.suggested_score,
            "selectedRuleId": suggestion.selected_rule_id,
            "reason": suggestion.reason,
            "evidenceSummary": suggestion.evidence_summary,
        } for suggestion in suggestions],
    }


def application_analysis_data(item: ApplicationAiAnalysis) -> dict:
    return {
        "id": item.id,
        "applicationId": item.application_id,
        "status": item.status,
        "provider": item.provider,
        "model": item.model,
        "verificationStatus": item.verification_status,
        "suggestedScore": item.suggested_score,
        "selectedRuleId": item.selected_rule_id,
        "reason": item.reason,
        "evidenceSummary": item.evidence_summary,
        "errorMessage": item.error_message,
        "advisoryOnly": True,
        "createdAt": item.created_at.strftime("%Y-%m-%d %H:%M:%S") if item.created_at else "",
        "completedAt": item.completed_at.strftime("%Y-%m-%d %H:%M:%S") if item.completed_at else "",
    }


@router.get("/api/ai/status", tags=["👤 4-通用"], summary="查看AI辅助核验配置状态")
def ai_status(current_user: User = Depends(get_current_user)):
    config = ai_config()
    return ApiResponse.success({
        "enabled": config["enabled"],
        "configured": config["configured"],
        "provider": "deepseek",
        "model": config["model"],
        "ocrAvailable": ocr_available(),
        "privacyMode": "本地提取后脱敏，仅发送相关片段",
        "advisoryOnly": True,
    })


@router.post("/api/ai/batch/{batch_id}/analyze", tags=["🎓 1-学生端"], summary="学生：对批次材料发起AI辅助核验")
def start_batch_analysis(
    batch_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_role(ROLE_STUDENT)),
    db: Session = Depends(get_db),
):
    config = ai_config()
    if not config["enabled"]:
        return ApiResponse.error(503, "AI辅助核验已关闭")
    if not config["configured"]:
        return ApiResponse.error(503, "未配置DeepSeek API密钥，请管理员在本机.env中配置")
    student = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    batch = db.query(SubmissionBatch).filter(SubmissionBatch.id == batch_id).first()
    if not student or not batch or batch.student_id != student.id:
        return ApiResponse.error(404, "批次不存在")
    if batch.status not in {BATCH_PARSED, BATCH_CONFIRMED} or batch.error_count:
        return ApiResponse.error(409, "批次仍有解析错误，暂不能进行AI辅助核验")
    if is_student_finalized(db, student.id, batch.assessment_year):
        return ApiResponse.error(409, "综合测评结果已经终审，不能新建AI分析任务")
    active = db.query(AiAnalysisJob).filter(
        AiAnalysisJob.batch_id == batch.id,
        AiAnalysisJob.status.in_(["pending", "running"]),
    ).order_by(AiAnalysisJob.id.desc()).first()
    if active:
        if active.status == "pending":
            # 服务在任务入队前退出时，下一次访问可以安全补发；任务服务使用原子认领防止重复执行。
            background_tasks.add_task(run_analysis_job, active.id)
            return ApiResponse.success(ai_job_data(db, active), "该批次正在等待分析")
        if active.started_at and active.started_at < datetime.now() - timedelta(minutes=15):
            active.status = "failed"
            active.error_message = "AI任务执行中断，已允许重新创建任务"
            active.completed_at = datetime.now()
            db.commit()
        else:
            return ApiResponse.success(ai_job_data(db, active), "该批次正在分析")
    job = AiAnalysisJob(
        batch_id=batch.id,
        student_id=student.id,
        status="pending",
        model=config["model"],
        item_count=batch.valid_count,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(run_analysis_job, job.id)
    return ApiResponse.success(ai_job_data(db, job), "AI辅助核验任务已创建")


@router.get("/api/ai/job/{job_id}", tags=["👤 4-通用"], summary="按权限查看AI辅助核验结果")
def get_analysis_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.query(AiAnalysisJob).filter(AiAnalysisJob.id == job_id).first()
    if not job or not _can_access_job(db, current_user, job):
        return ApiResponse.error(404, "AI分析任务不存在")
    return ApiResponse.success(ai_job_data(db, job))


@router.post("/api/ai/application/{application_id}/analyze", tags=["👤 4-通用"], summary="按权限对单条申请材料发起AI辅助核验")
def start_application_analysis(
    application_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config = ai_config()
    if not config["enabled"] or not config["configured"]:
        return ApiResponse.error(503, "AI辅助核验未启用或未配置DeepSeek API密钥")
    application = db.query(ScoreApplication).filter(ScoreApplication.id == application_id).first()
    if not application or not can_access_application(current_user, application, db):
        return ApiResponse.error(404, "申请不存在")
    if not application.evidence_files:
        return ApiResponse.error(409, "请先上传至少一份证明材料")
    if is_student_finalized(db, application.student_id):
        return ApiResponse.error(409, "综合测评结果已经终审，不能新建AI分析任务")
    active = db.query(ApplicationAiAnalysis).filter(
        ApplicationAiAnalysis.application_id == application.id,
        ApplicationAiAnalysis.status.in_(["pending", "running"]),
    ).order_by(ApplicationAiAnalysis.id.desc()).first()
    if active:
        if active.status == "pending":
            background_tasks.add_task(run_application_analysis, active.id)
        elif active.started_at and active.started_at < datetime.now() - timedelta(minutes=15):
            active.status = "failed"
            active.error_message = "AI任务执行中断，已允许重新创建任务"
            active.completed_at = datetime.now()
            db.commit()
            active = None
        else:
            return ApiResponse.success(application_analysis_data(active), "该申请正在分析")
    if active:
        return ApiResponse.success(application_analysis_data(active), "该申请正在等待分析")
    item = ApplicationAiAnalysis(
        application_id=application.id,
        student_id=application.student_id,
        model=config["model"],
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    background_tasks.add_task(run_application_analysis, item.id)
    return ApiResponse.success(application_analysis_data(item), "单条申请AI辅助核验任务已创建")


@router.get("/api/ai/application/{application_id}/latest", tags=["👤 4-通用"], summary="查看单条申请最新AI核验建议")
def latest_application_analysis(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    application = db.query(ScoreApplication).filter(ScoreApplication.id == application_id).first()
    if not application or not can_access_application(current_user, application, db):
        return ApiResponse.error(404, "申请不存在")
    item = db.query(ApplicationAiAnalysis).filter(
        ApplicationAiAnalysis.application_id == application.id,
    ).order_by(ApplicationAiAnalysis.id.desc()).first()
    return ApiResponse.success(application_analysis_data(item) if item else None)
