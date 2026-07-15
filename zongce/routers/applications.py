from fastapi import APIRouter, Form
from uuid import uuid4

from zongce.core import *
from zongce.application_service import (
    EDITABLE_STATUSES,
    normalize_pagination,
    transition_application,
    validate_application_fields,
)
from zongce.accounting_service import is_student_finalized

router = APIRouter()

class ApplicationCreate(BaseModel):
    model_config = ConfigDict(extra="allow")

    rule_id: int
    project_name: str
    project_level: str = ""
    team_rank: int = 1
    team_total: int = 1
    project_date: str = ""
    description: str = ""
    remark: str = ""
    submit_now: bool = False
    apply_score: Optional[float] = None

@router.post("/api/application/create", tags=["🎓 1-学生端"], summary="学生：创建加分申请（草稿或提交）")
def create_application(req: ApplicationCreate, current_user: User = Depends(require_role(ROLE_STUDENT)), db: Session = Depends(get_db)):
    validation_error = validate_application_fields(
        req.project_name, req.team_rank, req.team_total,
        req.project_date, req.description, req.remark,
    )
    if validation_error:
        return ApiResponse.error(400, validation_error)
    if req.submit_now:
        return ApiResponse.error(400, "请先保存草稿并上传证明材料，再提交审核")
    if not req.rule_id:
        return ApiResponse.error(400, "请选择加分类别")
    rule = db.query(ScoreRule).filter(ScoreRule.id == req.rule_id).first()
    if not rule or not rule.is_active:
        return ApiResponse.error(400, "该加分规则不存在或已停用")
    sp = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not sp:
        return ApiResponse.error(400, "学生信息不存在")
    if is_student_finalized(db, sp.id):
        return ApiResponse.error(409, "综合测评结果已经终审，不能新增申请")
    duplicate = db.query(ScoreApplication).filter(
        ScoreApplication.student_id == sp.id,
        ScoreApplication.rule_id == req.rule_id,
        ScoreApplication.project_name == req.project_name.strip(),
        ScoreApplication.status != STATUS_WITHDRAWN,
    ).first()
    rank_coef = 1.0
    if rule.rank_coefficient:
        try:
            coef_map = json_lib.loads(rule.rank_coefficient)
            rank_coef = float(coef_map.get(str(req.team_rank), coef_map.get("default", 1.0)))
        except Exception:
            rank_coef = 1.0
    system_score = round(rule.base_score * rank_coef, 2)
    app_rec = ScoreApplication(
        student_id=sp.id,
        rule_id=req.rule_id,
        project_name=req.project_name.strip(),
        project_level=req.project_level,
        team_rank=req.team_rank,
        team_total=req.team_total,
        project_date=req.project_date,
        description=req.description,
        status=STATUS_DRAFT,
        system_calculated_score=system_score,
        final_score=system_score,
        remark=req.remark,
        submitted_at=None
    )
    db.add(app_rec)
    db.commit()
    db.refresh(app_rec)
    return ApiResponse.success({
        "id": app_rec.id,
        "status": app_rec.status,
        "systemCalculatedScore": app_rec.system_calculated_score,
        "duplicateWarning": "存在同名同规则申请，请确认是否重复填报" if duplicate else "",
    }, "草稿已保存")

@router.put("/api/application/submit/{app_id}", tags=["🎓 1-学生端"], summary="学生：草稿申请提交为待审核")
def submit_application(app_id: int, current_user: User = Depends(require_role(ROLE_STUDENT)), db: Session = Depends(get_db)):
    sp = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not sp:
        return ApiResponse.error(404, "学生信息不存在")
    if is_student_finalized(db, sp.id):
        return ApiResponse.error(409, "综合测评结果已经终审，不能提交申请")
    app_rec = db.query(ScoreApplication).filter(ScoreApplication.id == app_id).first()
    if not app_rec:
        return ApiResponse.error(404, "申请不存在")
    if app_rec.student_id != sp.id:
        return ApiResponse.error(403, "无操作权限")
    if app_rec.status not in EDITABLE_STATUSES:
        return ApiResponse.error(400, "该申请当前状态不允许提交")
    if len(app_rec.evidence_files) == 0:
        return ApiResponse.error(400, "请至少上传1份证明材料")
    changed = transition_application(
        db, app_rec.id, sp.id, EDITABLE_STATUSES, STATUS_PENDING,
        {
            ScoreApplication.reject_reason: "",
            ScoreApplication.submitted_at: datetime.now(),
        },
    )
    if not changed:
        db.rollback()
        return ApiResponse.error(409, "申请状态已发生变化，请刷新后重试")
    db.commit()
    return ApiResponse.success(message="提交成功，请等待审核")

class ApplicationUpdate(BaseModel):
    model_config = ConfigDict(extra="allow")

    rule_id: Optional[int] = None
    project_name: Optional[str] = None
    project_level: Optional[str] = None
    team_rank: Optional[int] = None
    team_total: Optional[int] = None
    project_date: Optional[str] = None
    description: Optional[str] = None
    remark: Optional[str] = None
    submit_now: Optional[bool] = None
    apply_score: Optional[float] = None

@router.put("/api/application/update/{app_id}", tags=["🎓 1-学生端"], summary="学生：修改草稿申请（可直接改完提交）")
def update_application(
    app_id: int, req: ApplicationUpdate,
    current_user: User = Depends(require_role(ROLE_STUDENT)), db: Session = Depends(get_db)
):
    sp = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not sp:
        return ApiResponse.error(404, "学生信息不存在")
    if is_student_finalized(db, sp.id):
        return ApiResponse.error(409, "综合测评结果已经终审，不能修改申请")
    app_rec = db.query(ScoreApplication).filter(ScoreApplication.id == app_id).first()
    if not app_rec:
        return ApiResponse.error(404, "申请不存在")
    if app_rec.student_id != sp.id:
        return ApiResponse.error(403, "无操作权限")
    if app_rec.status not in EDITABLE_STATUSES:
        return ApiResponse.error(400, "仅草稿、未通过或已撤回的申请可以修改")
    next_name = req.project_name if req.project_name is not None else app_rec.project_name
    next_rank = req.team_rank if req.team_rank is not None else app_rec.team_rank
    next_total = req.team_total if req.team_total is not None else app_rec.team_total
    validation_error = validate_application_fields(
        next_name, next_rank, next_total,
        req.project_date if req.project_date is not None else app_rec.project_date,
        req.description if req.description is not None else app_rec.description,
        req.remark if req.remark is not None else app_rec.remark,
    )
    if validation_error:
        return ApiResponse.error(400, validation_error)
    if req.rule_id is not None:
        rule = db.query(ScoreRule).filter(ScoreRule.id == req.rule_id).first()
        if not rule or not rule.is_active:
            return ApiResponse.error(400, "该加分规则不存在或已停用")
        app_rec.rule_id = req.rule_id
        rank_coef = 1.0
        if rule.rank_coefficient:
            try:
                coef_map = json_lib.loads(rule.rank_coefficient)
                tr = req.team_rank if req.team_rank is not None else app_rec.team_rank
                rank_coef = float(coef_map.get(str(tr), coef_map.get("default", 1.0)))
            except Exception:
                rank_coef = 1.0
        app_rec.system_calculated_score = round(rule.base_score * rank_coef, 2)
        app_rec.final_score = app_rec.system_calculated_score
    else:
        if req.team_rank is not None:
            rule = db.query(ScoreRule).filter(ScoreRule.id == app_rec.rule_id).first()
            if rule and rule.rank_coefficient:
                try:
                    coef_map = json_lib.loads(rule.rank_coefficient)
                    rank_coef = float(coef_map.get(str(req.team_rank), coef_map.get("default", 1.0)))
                    app_rec.system_calculated_score = round(rule.base_score * rank_coef, 2)
                    app_rec.final_score = app_rec.system_calculated_score
                except Exception:
                    pass
    if req.project_name is not None:
        if not req.project_name.strip():
            return ApiResponse.error(400, "项目名称不能为空")
        app_rec.project_name = req.project_name.strip()
    for fld, val in [
        ("project_level", req.project_level),
        ("team_rank", req.team_rank),
        ("team_total", req.team_total),
        ("project_date", req.project_date),
        ("description", req.description),
        ("remark", req.remark),
    ]:
        if val is not None:
            setattr(app_rec, fld, val)
    # 编辑未通过/已撤回申请时先恢复为草稿，保留审核历史但清除旧驳回提示。
    app_rec.status = STATUS_DRAFT
    app_rec.reject_reason = ""
    if req.submit_now:
        if len(app_rec.evidence_files) == 0:
            return ApiResponse.error(400, "请至少上传1份证明材料")
        app_rec.status = STATUS_PENDING
        app_rec.submitted_at = datetime.now()
    db.commit()
    return ApiResponse.success({
        "id": app_rec.id,
        "status": app_rec.status,
        "systemCalculatedScore": app_rec.system_calculated_score
    }, "已提交，请等待审核" if req.submit_now else "修改已保存")

@router.put("/api/application/withdraw/{app_id}", tags=["🎓 1-学生端"], summary="学生：撤回审核中/已驳回的申请（状态改为已撤回）")
def withdraw_application(app_id: int, current_user: User = Depends(require_role(ROLE_STUDENT)), db: Session = Depends(get_db)):
    sp = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not sp:
        return ApiResponse.error(404, "学生信息不存在")
    if is_student_finalized(db, sp.id):
        return ApiResponse.error(409, "综合测评结果已经终审，不能撤回申请")
    app_rec = db.query(ScoreApplication).filter(ScoreApplication.id == app_id).first()
    if not app_rec:
        return ApiResponse.error(404, "申请不存在")
    if app_rec.student_id != sp.id:
        return ApiResponse.error(403, "无操作权限")
    if app_rec.status != STATUS_PENDING:
        return ApiResponse.error(400, "该申请当前状态不允许撤回")
    changed = transition_application(
        db, app_rec.id, sp.id, {STATUS_PENDING}, STATUS_WITHDRAWN
    )
    if not changed:
        db.rollback()
        return ApiResponse.error(409, "申请状态已发生变化，请刷新后重试")
    ar = AuditRecord(
        application_id=app_rec.id, auditor_id=current_user.id,
        result=AUDIT_MODIFY,
        opinion=f"学生{current_user.real_name}撤回申请，状态变为已撤回"
    )
    db.add(ar)
    db.commit()
    return ApiResponse.success(message="已撤回，该申请不再审核")

@router.delete("/api/application/delete/{app_id}", tags=["🎓 1-学生端"], summary="学生：删除草稿申请")
def delete_application(app_id: int, current_user: User = Depends(require_role(ROLE_STUDENT)), db: Session = Depends(get_db)):
    sp = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not sp:
        return ApiResponse.error(404, "学生信息不存在")
    if is_student_finalized(db, sp.id):
        return ApiResponse.error(409, "综合测评结果已经终审，不能删除申请")
    app_rec = db.query(ScoreApplication).filter(ScoreApplication.id == app_id).first()
    if not app_rec:
        return ApiResponse.error(404, "申请不存在")
    if app_rec.student_id != sp.id:
        return ApiResponse.error(403, "无操作权限")
    if app_rec.status != STATUS_DRAFT:
        return ApiResponse.error(400, "仅草稿状态可删除")
    db.delete(app_rec)
    db.commit()
    return ApiResponse.success(message="删除成功")

@router.get("/api/application/list", tags=["👤 4-通用"], summary="查看申请列表（学生看自己，老师/管理员看全部，支持按状态/姓名学号关键词筛选）")
def application_list(
    page: int = 1, page_size: int = 200, status: Optional[int] = None, keyword: str = "",
    status_group: Optional[str] = None,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    page, page_size = normalize_pagination(page, page_size)
    query = db.query(ScoreApplication)
    if current_user.role == ROLE_STUDENT:
        sp = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
        if not sp:
            return ApiResponse.error(404, "学生信息不存在")
        query = query.filter(ScoreApplication.student_id == sp.id)
    elif current_user.role == ROLE_TEACHER:
        if not current_user.managed_class:
            query = query.filter(False)
        else:
            query = query.join(ScoreApplication.student).filter(
                StudentProfile.class_name == current_user.managed_class
            )
    # keyword: 学生姓名/学号模糊搜（老师/管理员用）
    if keyword and current_user.role != ROLE_STUDENT:
        query = query.join(ScoreApplication.student).join(StudentProfile.user).filter(
            (StudentProfile.student_id.like(f"%{keyword}%")) |
            (User.real_name.like(f"%{keyword}%"))
        )
    # 状态分组：pending = 待处理；handled = 已处理（含通过/驳回/撤回）
    if status_group == "pending":
        query = query.filter(ScoreApplication.status == STATUS_PENDING)
    elif status_group == "handled":
        query = query.filter(ScoreApplication.status.in_([STATUS_PASSED, STATUS_REJECTED, STATUS_WITHDRAWN]))
    elif status is not None:
        query = query.filter(ScoreApplication.status == status)
    total = query.count()
    items = query.order_by(ScoreApplication.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    rows = []
    for it in items:
        rule = it.rule
        sp_rec = it.student
        user_rec = sp_rec.user if sp_rec else None
        rows.append({
            "id": it.id,
            "projectName": it.project_name,
            "category": rule.category if rule else "",
            "subCategory": rule.sub_category if rule else "",
            "itemName": rule.item_name if rule else "",
            "projectLevel": it.project_level,
            "systemCalculatedScore": it.system_calculated_score,
            "finalScore": it.final_score,
            "status": it.status,
            "statusName": STATUS_TEXT.get(it.status, "未知"),
            "rejectReason": it.reject_reason,
            "submittedAt": it.submitted_at.strftime("%Y-%m-%d %H:%M:%S") if it.submitted_at else "",
            "createdAt": it.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "evidenceCount": len(it.evidence_files),
            "studentName": user_rec.real_name if user_rec else "",
            "studentId": sp_rec.student_id if sp_rec else "",
            "className": sp_rec.class_name if sp_rec else "",
            "isWithdrawn": it.status == STATUS_WITHDRAWN,
        })
    return ApiResponse.success({"total": total, "page": page, "pageSize": page_size, "list": rows})

@router.get("/api/application/detail/{app_id}", tags=["👤 4-通用"], summary="申请详情（撤回的申请老师禁止看详情）")
def application_detail(app_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    app_rec = db.query(ScoreApplication).filter(ScoreApplication.id == app_id).first()
    if not app_rec:
        return ApiResponse.error(404, "申请不存在")
    sp_rec = app_rec.student
    user_rec = sp_rec.user if sp_rec else None
    if not can_access_application(current_user, app_rec, db):
        return ApiResponse.error(403, "无权查看该申请")
    # 撤回的申请：老师仅返回概要
    if app_rec.status == STATUS_WITHDRAWN and current_user.role == ROLE_TEACHER:
        return ApiResponse.success({
            "id": app_rec.id,
            "projectName": app_rec.project_name,
            "status": STATUS_WITHDRAWN,
            "statusName": STATUS_TEXT[STATUS_WITHDRAWN],
            "studentName": user_rec.real_name if user_rec else "",
            "studentId": sp_rec.student_id if sp_rec else "",
            "withdrawnForbidden": True,
        })
    rule = app_rec.rule
    ev_files = [{
        "id": f.id,
        "fileName": f.file_name,
        "filePath": f"/api/file/{f.id}",
        "fileUrl": f"/api/file/{f.id}",
        "fileSize": f.file_size,
        "fileType": f.file_type,
        "uploadedAt": f.uploaded_at.strftime("%Y-%m-%d %H:%M:%S") if f.uploaded_at else ""
    } for f in app_rec.evidence_files]
    audits = [{
        "auditorId": ar.auditor_id,
        "auditorName": ar.auditor.real_name if ar.auditor else "",
        "result": ar.result,
        "modifiedScore": ar.modified_score,
        "opinion": ar.opinion,
        "createdAt": ar.created_at.strftime("%Y-%m-%d %H:%M:%S") if ar.created_at else ""
    } for ar in app_rec.audit_records]
    return ApiResponse.success({
        "id": app_rec.id,
        "ruleId": app_rec.rule_id,
        "projectName": app_rec.project_name,
        "projectLevel": app_rec.project_level,
        "teamRank": app_rec.team_rank,
        "teamTotal": app_rec.team_total,
        "projectDate": app_rec.project_date,
        "description": app_rec.description,
        "remark": app_rec.remark,
        "category": rule.category if rule else "",
        "subCategory": rule.sub_category if rule else "",
        "itemName": rule.item_name if rule else "",
        "baseScore": rule.base_score if rule else 0,
        "policy": rule.policy if rule else 1,
        "systemCalculatedScore": app_rec.system_calculated_score,
        "finalScore": app_rec.final_score,
        "status": app_rec.status,
        "statusName": STATUS_TEXT.get(app_rec.status, "未知"),
        "rejectReason": app_rec.reject_reason,
        "submittedAt": app_rec.submitted_at.strftime("%Y-%m-%d %H:%M:%S") if app_rec.submitted_at else "",
        "evidenceFiles": ev_files,
        "auditRecords": audits,
        "studentName": user_rec.real_name if user_rec else "",
        "studentId": sp_rec.student_id if sp_rec else "",
        "className": sp_rec.class_name if sp_rec else ""
    })

@router.post("/api/file/upload", tags=["🎓 1-学生端"], summary="学生：为自己的可编辑申请上传证明材料")
async def upload_file(
    application_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(require_role(ROLE_STUDENT)),
    db: Session = Depends(get_db)
):
    app_rec = db.query(ScoreApplication).filter(ScoreApplication.id == application_id).first()
    if not app_rec:
        return ApiResponse.error(404, "申请不存在")
    if is_student_finalized(db, app_rec.student_id):
        return ApiResponse.error(409, "综合测评结果已经终审，不能上传材料")
    if not can_access_application(current_user, app_rec, db):
        return ApiResponse.error(403, "只能为自己的申请上传材料")
    if app_rec.status not in [STATUS_DRAFT, STATUS_REJECTED, STATUS_WITHDRAWN]:
        return ApiResponse.error(400, "该申请当前状态不允许上传材料")
    if len(app_rec.evidence_files) >= 5:
        return ApiResponse.error(400, "每个申请最多上传5份证明材料")
    original_name = os.path.basename((file.filename or "").replace("\\", "/"))
    if not original_name:
        return ApiResponse.error(400, "文件名不能为空")
    if len(original_name) > 255:
        return ApiResponse.error(400, "文件名不能超过255个字符")
    allowed_exts = [".jpg", ".jpeg", ".png", ".pdf"]
    ext = os.path.splitext(original_name)[1].lower()
    if ext not in allowed_exts:
        return ApiResponse.error(400, "仅支持JPG、PNG、PDF格式文件")
    content = await file.read()
    if not content:
        return ApiResponse.error(400, "不能上传空文件")
    if len(content) > 10 * 1024 * 1024:
        return ApiResponse.error(400, "文件大小不能超过10MB")
    signatures = {
        ".pdf": (b"%PDF",),
        ".png": (b"\x89PNG\r\n\x1a\n",),
        ".jpg": (b"\xff\xd8\xff",),
        ".jpeg": (b"\xff\xd8\xff",),
    }
    if not any(content.startswith(signature) for signature in signatures[ext]):
        return ApiResponse.error(400, "文件内容与扩展名不匹配")
    media_types = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }
    content_hash = hashlib.sha256(content).hexdigest()
    duplicate_files = db.query(EvidenceFile).filter(
        EvidenceFile.content_hash == content_hash,
        EvidenceFile.content_hash != "",
    ).all()
    file_dir = os.path.join(UPLOAD_DIR, datetime.now().strftime('%Y%m%d'))
    os.makedirs(file_dir, exist_ok=True)
    safe_name = f"{uuid4().hex}{ext}"
    file_path = os.path.join(file_dir, safe_name)
    with open(file_path, "wb") as f:
        f.write(content)
    ef = EvidenceFile(
        application_id=application_id,
        file_name=original_name,
        file_path=file_path,
        file_size=len(content),
        file_type=media_types[ext],
        content_hash=content_hash,
    )
    try:
        db.add(ef)
        db.commit()
        db.refresh(ef)
    except Exception:
        db.rollback()
        if os.path.isfile(file_path):
            os.remove(file_path)
        raise
    return ApiResponse.success({
        "id": ef.id,
        "filename": original_name,
        "url": f"/api/file/{ef.id}",
        "size": len(content),
        "fileType": media_types[ext],
        "duplicateWarning": bool(duplicate_files),
        "duplicateCount": len(duplicate_files),
    }, "上传成功")

@router.get("/api/file/{file_id}", tags=["👤 4-通用"], summary="按权限查看或下载证明材料")
def get_evidence_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    evidence = db.query(EvidenceFile).filter(EvidenceFile.id == file_id).first()
    if not evidence or not evidence.application:
        return ApiResponse.error(404, "证明材料不存在")
    if not can_access_application(current_user, evidence.application, db):
        return ApiResponse.error(403, "无权查看该证明材料")
    if not os.path.isfile(evidence.file_path):
        return ApiResponse.error(404, "证明材料文件已丢失")
    return FileResponse(
        evidence.file_path,
        media_type=evidence.file_type or "application/octet-stream",
        filename=evidence.file_name,
        content_disposition_type="inline"
    )


@router.get("/api/evidence/duplicates", tags=["👨‍🏫 2-审核端"], summary="教师/管理员：查看重复证明材料摘要")
def duplicate_evidence_groups(
    current_user: User = Depends(require_role(ROLE_TEACHER, ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    hashes = db.query(EvidenceFile.content_hash).filter(
        EvidenceFile.content_hash != "",
    ).group_by(EvidenceFile.content_hash).having(func.count(EvidenceFile.id) > 1).all()
    groups = []
    for (content_hash,) in hashes:
        files = db.query(EvidenceFile).filter(EvidenceFile.content_hash == content_hash).all()
        visible = []
        for evidence in files:
            application = evidence.application
            if not application or not can_access_application(current_user, application, db):
                continue
            student = application.student
            visible.append({
                "fileId": evidence.id,
                "fileName": evidence.file_name,
                "applicationId": application.id,
                "projectName": application.project_name,
                "studentId": student.student_id if student else "",
                "studentName": student.user.real_name if student and student.user else "",
                "className": student.class_name if student else "",
            })
        if len(visible) > 1:
            groups.append({"fingerprint": content_hash[:12], "count": len(visible), "files": visible})
    return ApiResponse.success({"groups": groups, "groupCount": len(groups)})
