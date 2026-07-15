from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from zongce.accounting_service import calculate_ranked_accounting, log_operation
from zongce.core import *


router = APIRouter()
VALID_SCOPES = {"all", "class", "major", "grade"}
VALID_OBJECTION_TYPES = {"分数计算错误", "类别归类错误", "材料未被认可", "其他"}
VALID_RESOLUTIONS = {"accepted", "rejected", "need_more"}


def _announcement_status(item: Announcement) -> str:
    now = datetime.now()
    if not item.is_active:
        return "closed"
    if now < item.starts_at:
        return "upcoming"
    if now > item.ends_at:
        return "ended"
    return "active"


def _student_in_scope(student: StudentProfile, item: Announcement) -> bool:
    if item.scope_type == "all":
        return True
    mapping = {"class": student.class_name, "major": student.major, "grade": student.grade}
    return str(mapping.get(item.scope_type, "")) == str(item.scope_value or "")


def _can_view_announcement(db: Session, user: User, item: Announcement) -> bool:
    if user.role == ROLE_ADMIN:
        return True
    if user.role == ROLE_TEACHER:
        return item.scope_type == "all" or (item.scope_type == "class" and item.scope_value == user.managed_class)
    student = get_student_for_user(db, user)
    return bool(student and _student_in_scope(student, item))


def _announcement_data(item: Announcement) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "scopeType": item.scope_type,
        "scopeValue": item.scope_value,
        "description": item.description,
        "startsAt": item.starts_at.isoformat(timespec="minutes"),
        "endsAt": item.ends_at.isoformat(timespec="minutes"),
        "status": _announcement_status(item),
        "isActive": item.is_active,
        "createdAt": item.created_at.strftime("%Y-%m-%d %H:%M:%S") if item.created_at else "",
    }


class AnnouncementReq(BaseModel):
    title: str
    scope_type: str = "all"
    scope_value: str = ""
    description: str = ""
    starts_at: datetime
    ends_at: datetime


@router.post("/api/admin/announcement", tags=["🛡️ 3-管理端"], summary="管理员：发布成绩公示")
def create_announcement(
    req: AnnouncementReq,
    current_user: User = Depends(require_role(ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    title = req.title.strip()
    if not title or len(title) > 200:
        return ApiResponse.error(400, "公示标题长度应为1-200字")
    if req.scope_type not in VALID_SCOPES:
        return ApiResponse.error(400, "公示范围类型不正确")
    if req.scope_type != "all" and not req.scope_value.strip():
        return ApiResponse.error(400, "请选择具体公示范围")
    if req.ends_at <= req.starts_at:
        return ApiResponse.error(400, "公示结束时间必须晚于开始时间")
    item = Announcement(
        title=title,
        scope_type=req.scope_type,
        scope_value=req.scope_value.strip(),
        description=req.description.strip()[:2000],
        starts_at=req.starts_at,
        ends_at=req.ends_at,
        created_by=current_user.id,
    )
    db.add(item)
    db.flush()
    log_operation(db, current_user.id, "发布成绩公示", entity_type="announcement", entity_id=item.id, detail=title)
    db.commit()
    db.refresh(item)
    return ApiResponse.success(_announcement_data(item), "公示已发布")


@router.get("/api/announcement/list", tags=["👤 4-通用"], summary="按权限查看成绩公示")
def list_announcements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = db.query(Announcement).order_by(Announcement.id.desc()).all()
    visible = [_announcement_data(item) for item in items if _can_view_announcement(db, current_user, item)]
    return ApiResponse.success({"list": visible})


@router.get("/api/announcement/{announcement_id}", tags=["👤 4-通用"], summary="查看公示成绩详情")
def announcement_detail(
    announcement_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not item or not _can_view_announcement(db, current_user, item):
        return ApiResponse.error(404, "公示不存在")
    query = db.query(StudentProfile)
    if item.scope_type != "all":
        query = query.filter(getattr(StudentProfile, f"{item.scope_type}_name", None) == item.scope_value) if item.scope_type == "class" else query.filter(getattr(StudentProfile, item.scope_type) == item.scope_value)
    students = query.all()
    if current_user.role == ROLE_STUDENT:
        students = [student for student in students if student.user_id == current_user.id]
    elif current_user.role == ROLE_TEACHER:
        students = [student for student in students if student.class_name == current_user.managed_class]
    results = calculate_ranked_accounting(db, students)
    return ApiResponse.success({"announcement": _announcement_data(item), "results": results})


@router.delete("/api/admin/announcement/{announcement_id}", tags=["🛡️ 3-管理端"], summary="管理员：结束成绩公示")
def close_announcement(
    announcement_id: int,
    current_user: User = Depends(require_role(ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    item = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not item:
        return ApiResponse.error(404, "公示不存在")
    item.is_active = False
    log_operation(db, current_user.id, "结束成绩公示", entity_type="announcement", entity_id=item.id, detail=item.title)
    db.commit()
    return ApiResponse.success(None, "公示已结束")


class ObjectionReq(BaseModel):
    announcement_id: int
    score_item: str = "综合测评总分"
    objection_type: str
    description: str


@router.post("/api/objection", tags=["🎓 1-学生端"], summary="学生：在公示期内提交异议")
def create_objection(
    req: ObjectionReq,
    current_user: User = Depends(require_role(ROLE_STUDENT)),
    db: Session = Depends(get_db),
):
    student = get_student_for_user(db, current_user)
    item = db.query(Announcement).filter(Announcement.id == req.announcement_id).first()
    if not student or not item or not _student_in_scope(student, item):
        return ApiResponse.error(404, "公示不存在")
    if _announcement_status(item) != "active":
        return ApiResponse.error(409, "当前不在公示期内，无法提交异议")
    description = req.description.strip()
    if req.objection_type not in VALID_OBJECTION_TYPES:
        return ApiResponse.error(400, "异议类型不正确")
    if not description or len(description) > 500:
        return ApiResponse.error(400, "异议说明长度应为1-500字")
    duplicate = db.query(ScoreObjection).filter(
        ScoreObjection.announcement_id == item.id,
        ScoreObjection.student_id == student.id,
        ScoreObjection.score_item == req.score_item.strip(),
        ScoreObjection.status == "pending",
    ).first()
    if duplicate:
        return ApiResponse.error(409, "该分数项已有异议正在处理中")
    objection = ScoreObjection(
        announcement_id=item.id,
        student_id=student.id,
        score_item=req.score_item.strip()[:100] or "综合测评总分",
        objection_type=req.objection_type,
        description=description,
    )
    db.add(objection)
    db.commit()
    db.refresh(objection)
    return ApiResponse.success({"id": objection.id}, "异议已提交")


def _objection_data(db: Session, item: ScoreObjection) -> dict:
    student = db.query(StudentProfile).filter(StudentProfile.id == item.student_id).first()
    announcement = db.query(Announcement).filter(Announcement.id == item.announcement_id).first()
    return {
        "id": item.id,
        "announcementId": item.announcement_id,
        "announcementTitle": announcement.title if announcement else "",
        "studentId": student.student_id if student else "",
        "studentName": student.user.real_name if student and student.user else "",
        "className": student.class_name if student else "",
        "scoreItem": item.score_item,
        "type": item.objection_type,
        "description": item.description,
        "status": item.status,
        "resolution": item.resolution,
        "createdAt": item.created_at.strftime("%Y-%m-%d %H:%M:%S") if item.created_at else "",
        "handledAt": item.handled_at.strftime("%Y-%m-%d %H:%M:%S") if item.handled_at else "",
    }


@router.get("/api/objection/list", tags=["👤 4-通用"], summary="按权限查看异议记录")
def list_objections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(ScoreObjection).order_by(ScoreObjection.id.desc())
    if current_user.role == ROLE_STUDENT:
        student = get_student_for_user(db, current_user)
        query = query.filter(ScoreObjection.student_id == (student.id if student else -1))
    elif current_user.role == ROLE_TEACHER:
        student_ids = [row.id for row in db.query(StudentProfile.id).filter(StudentProfile.class_name == current_user.managed_class).all()]
        query = query.filter(ScoreObjection.student_id.in_(student_ids or [-1]))
    return ApiResponse.success({"list": [_objection_data(db, item) for item in query.all()]})


class ObjectionHandleReq(BaseModel):
    resolution_status: str
    resolution: str


@router.post("/api/admin/objection/{objection_id}/handle", tags=["🛡️ 3-管理端"], summary="管理员：处理学生异议")
def handle_objection(
    objection_id: int,
    req: ObjectionHandleReq,
    current_user: User = Depends(require_role(ROLE_ADMIN)),
    db: Session = Depends(get_db),
):
    item = db.query(ScoreObjection).filter(ScoreObjection.id == objection_id).first()
    if not item:
        return ApiResponse.error(404, "异议不存在")
    resolution = req.resolution.strip()
    if req.resolution_status not in VALID_RESOLUTIONS or not resolution:
        return ApiResponse.error(400, "请选择处理结论并填写处理意见")
    item.status = req.resolution_status
    item.resolution = resolution[:1000]
    item.handled_by = current_user.id
    item.handled_at = datetime.now()
    log_operation(db, current_user.id, "处理成绩异议", student_id=item.student_id, entity_type="objection", entity_id=item.id, detail=resolution)
    db.commit()
    return ApiResponse.success(_objection_data(db, item), "异议已处理")
