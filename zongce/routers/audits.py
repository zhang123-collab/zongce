from fastapi import APIRouter

from zongce.core import *
from zongce.application_service import transition_application
from zongce.accounting_service import calculate_student_accounting, is_student_finalized, sync_score_and_ranks
from zongce.routers.applications import application_detail


router = APIRouter()


class AuditPassReq(BaseModel):
    application_id: int
    opinion: str = ""


@router.post("/api/audit/pass", tags=["👨‍🏫 2-审核端"], summary="审核通过")
def audit_pass(req: AuditPassReq, current_user: User = Depends(require_role(ROLE_TEACHER, ROLE_ADMIN)), db: Session = Depends(get_db)):
    if len(req.opinion.strip()) > 500:
        return ApiResponse.error(400, "审核意见不能超过500字")
    app_rec = db.query(ScoreApplication).filter(ScoreApplication.id == req.application_id).first()
    if not app_rec:
        return ApiResponse.error(404, "申请不存在")
    if is_student_finalized(db, app_rec.student_id):
        return ApiResponse.error(409, "该生综合测评已经终审，不能继续审核")
    if not can_access_application(current_user, app_rec, db):
        return ApiResponse.error(403, "只能审核自己负责班级的申请")
    if app_rec.status != STATUS_PENDING:
        return ApiResponse.error(400, "该申请当前状态不允许审核")
    if not transition_application(
        db, app_rec.id, app_rec.student_id, {STATUS_PENDING}, STATUS_PASSED,
        {ScoreApplication.final_score: app_rec.system_calculated_score},
    ):
        db.rollback()
        return ApiResponse.error(409, "申请状态已被其他审核操作更新，请刷新列表")
    db.expire(app_rec)
    ar = AuditRecord(
        application_id=app_rec.id,
        auditor_id=current_user.id,
        result=AUDIT_PASS,
        opinion=req.opinion.strip()
    )
    db.add(ar)
    student = db.query(StudentProfile).filter(StudentProfile.id == app_rec.student_id).first()
    if student:
        sync_score_and_ranks(db, student, calculate_student_accounting(db, student, use_final_snapshot=False))
    db.commit()
    return ApiResponse.success(message="审核通过成功")


class AuditRejectReq(BaseModel):
    application_id: int
    reject_reason: str
    opinion: str = ""


@router.post("/api/audit/reject", tags=["👨‍🏫 2-审核端"], summary="审核驳回（必须填驳回原因）")
def audit_reject(req: AuditRejectReq, current_user: User = Depends(require_role(ROLE_TEACHER, ROLE_ADMIN)), db: Session = Depends(get_db)):
    if not req.reject_reason.strip():
        return ApiResponse.error(400, "请填写驳回原因")
    if len(req.reject_reason.strip()) > 500 or len(req.opinion.strip()) > 500:
        return ApiResponse.error(400, "驳回原因和审核意见不能超过500字")
    app_rec = db.query(ScoreApplication).filter(ScoreApplication.id == req.application_id).first()
    if not app_rec:
        return ApiResponse.error(404, "申请不存在")
    if is_student_finalized(db, app_rec.student_id):
        return ApiResponse.error(409, "该生综合测评已经终审，不能继续审核")
    if not can_access_application(current_user, app_rec, db):
        return ApiResponse.error(403, "只能审核自己负责班级的申请")
    if app_rec.status != STATUS_PENDING:
        return ApiResponse.error(400, "该申请当前状态不允许审核")
    if not transition_application(
        db, app_rec.id, app_rec.student_id, {STATUS_PENDING}, STATUS_REJECTED,
        {ScoreApplication.reject_reason: req.reject_reason.strip()},
    ):
        db.rollback()
        return ApiResponse.error(409, "申请状态已被其他审核操作更新，请刷新列表")
    db.expire(app_rec)
    ar = AuditRecord(
        application_id=app_rec.id,
        auditor_id=current_user.id,
        result=AUDIT_REJECT,
        opinion=(req.opinion or req.reject_reason).strip()
    )
    db.add(ar)
    db.commit()
    return ApiResponse.success(message="驳回成功")


class AuditModifyReq(BaseModel):
    application_id: int
    modified_score: float
    opinion: str


@router.post("/api/audit/modify", tags=["👨‍🏫 2-审核端"], summary="修改分数后通过（必须填理由+分数）")
def audit_modify(req: AuditModifyReq, current_user: User = Depends(require_role(ROLE_TEACHER, ROLE_ADMIN)), db: Session = Depends(get_db)):
    if req.modified_score < 0 or req.modified_score > 100:
        return ApiResponse.error(400, "修改后的分数应在0-100之间")
    if not req.opinion.strip():
        return ApiResponse.error(400, "请填写修改分数理由")
    if len(req.opinion.strip()) > 500:
        return ApiResponse.error(400, "修改分数理由不能超过500字")
    app_rec = db.query(ScoreApplication).filter(ScoreApplication.id == req.application_id).first()
    if not app_rec:
        return ApiResponse.error(404, "申请不存在")
    if is_student_finalized(db, app_rec.student_id):
        return ApiResponse.error(409, "该生综合测评已经终审，不能继续审核")
    if not can_access_application(current_user, app_rec, db):
        return ApiResponse.error(403, "只能审核自己负责班级的申请")
    if app_rec.status != STATUS_PENDING:
        return ApiResponse.error(400, "该申请当前状态不允许审核")
    if not transition_application(
        db, app_rec.id, app_rec.student_id, {STATUS_PENDING}, STATUS_PASSED,
        {ScoreApplication.final_score: req.modified_score},
    ):
        db.rollback()
        return ApiResponse.error(409, "申请状态已被其他审核操作更新，请刷新列表")
    db.expire(app_rec)
    ar = AuditRecord(
        application_id=app_rec.id,
        auditor_id=current_user.id,
        result=AUDIT_MODIFY,
        modified_score=req.modified_score,
        opinion=req.opinion.strip()
    )
    db.add(ar)
    student = db.query(StudentProfile).filter(StudentProfile.id == app_rec.student_id).first()
    if student:
        sync_score_and_ranks(db, student, calculate_student_accounting(db, student, use_final_snapshot=False))
    db.commit()
    return ApiResponse.success(message="修改分数通过成功")


@router.get("/api/audit/pending-list", tags=["👨‍🏫 2-审核端"], summary="审核：申请列表（分页+筛选）")
def audit_pending_list(
    page: int = 1, page_size: int = 20,
    class_name: str = "", keyword: str = "",
    category: str = "", sub_category: str = "",
    status: Optional[int] = None,
    current_user: User = Depends(require_role(ROLE_TEACHER, ROLE_ADMIN)),
    db: Session = Depends(get_db)
):
    query = db.query(ScoreApplication).join(StudentProfile).join(User).join(ScoreRule)
    if current_user.role == ROLE_TEACHER:
        if not current_user.managed_class:
            query = query.filter(False)
        else:
            query = query.filter(StudentProfile.class_name == current_user.managed_class)
    if status is not None:
        query = query.filter(ScoreApplication.status == status)
    else:
        query = query.filter(ScoreApplication.status.in_([STATUS_PENDING, STATUS_PASSED, STATUS_REJECTED]))
    if class_name:
        query = query.filter(StudentProfile.class_name == class_name)
    if keyword:
        query = query.filter((User.real_name.contains(keyword)) | (StudentProfile.student_id.contains(keyword)) | (ScoreApplication.project_name.contains(keyword)))
    if category:
        query = query.filter(ScoreRule.category == category)
    if sub_category:
        query = query.filter(ScoreRule.sub_category == sub_category)
    total = query.count()
    items = query.order_by(ScoreApplication.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    rows = []
    for it in items:
        rows.append({
            "id": it.id,
            "studentName": it.student.user.real_name if it.student and it.student.user else "",
            "studentId": it.student.student_id if it.student else "",
            "className": it.student.class_name if it.student else "",
            "category": it.rule.category if it.rule else "",
            "subCategory": it.rule.sub_category if it.rule else "",
            "projectName": it.project_name,
            "projectLevel": it.project_level,
            "systemCalculatedScore": it.system_calculated_score,
            "finalScore": it.final_score,
            "status": it.status,
            "statusName": STATUS_TEXT.get(it.status, "未知"),
            "submittedAt": it.submitted_at.strftime("%Y-%m-%d %H:%M:%S") if it.submitted_at else "",
            "rejectReason": it.reject_reason
        })
    return ApiResponse.success({"total": total, "page": page, "pageSize": page_size, "list": rows})


@router.get("/api/audit/detail/{app_id}", tags=["👨‍🏫 2-审核端"], summary="审核：申请详情（复用详情接口）")
def audit_detail(app_id: int, current_user: User = Depends(require_role(ROLE_TEACHER, ROLE_ADMIN)), db: Session = Depends(get_db)):
    return application_detail(app_id, current_user, db)


@router.get("/api/audit/history/{application_id}", tags=["👤 4-通用"], summary="某申请的审核历史记录")
def audit_history(application_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    application = db.query(ScoreApplication).filter(ScoreApplication.id == application_id).first()
    if not application:
        return ApiResponse.error(404, "申请不存在")
    if not can_access_application(current_user, application, db):
        return ApiResponse.error(403, "无权查看该申请的审核记录")
    items = db.query(AuditRecord).filter(AuditRecord.application_id == application_id).order_by(AuditRecord.id.desc()).all()
    rows = []
    for it in items:
        rows.append({
            "id": it.id,
            "applicationId": it.application_id,
            "auditorId": it.auditor_id,
            "auditorName": it.auditor.real_name if it.auditor else "",
            "result": it.result,
            "resultName": {1: "通过", 2: "驳回", 3: "修改分数"}.get(it.result, "未知"),
            "modifiedScore": it.modified_score,
            "opinion": it.opinion,
            "createdAt": it.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })
    return ApiResponse.success(rows)
