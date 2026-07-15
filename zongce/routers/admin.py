from fastapi import APIRouter

from zongce.core import *
from zongce.accounting_service import calculate_student_accounting, is_student_finalized, sync_score_and_ranks


router = APIRouter()


def normalize_class_name(value: str) -> Optional[str]:
    name = (value or "").strip()
    if not re.fullmatch(r"[\w\u4e00-\u9fff（）()·. -]{1,50}", name):
        return None
    return name


# ========== 通用用户信息（教师/管理员 profile，学生也可用） ==========






# ========== 教师端班级学生管理 ==========
@router.get("/api/teacher/class/students", tags=["👨‍🏫 2-审核端"], summary="教师：查看自己班级的学生（含搜索）")
def teacher_class_students(
    keyword: str = "", current_user: User = Depends(require_role(ROLE_TEACHER, ROLE_ADMIN)),
    db: Session = Depends(get_db)
):
    cls = current_user.managed_class if current_user.role == ROLE_TEACHER else None
    query = db.query(StudentProfile)
    if current_user.role == ROLE_TEACHER:
        query = query.filter(StudentProfile.class_name == cls) if cls else query.filter(False)
    if keyword:
        kw = f"%{keyword}%"
        query = query.join(StudentProfile.user).filter(
            (StudentProfile.student_id.like(kw)) |
            (User.real_name.like(kw))
        )
    rows = []
    for sp in query.order_by(StudentProfile.class_name, StudentProfile.student_id).all():
        u = sp.user
        rows.append({
            "id": sp.id,
            "userId": u.id,
            "studentId": sp.student_id,
            "realName": u.real_name,
            "className": sp.class_name,
            "major": sp.major,
            "grade": sp.grade,
            "moralScore": sp.moral_score,
            "academicScore": sp.academic_score,
            "email": u.email,
            "phone": u.phone,
            "age": u.age,
        })
    return ApiResponse.success({"list": rows, "managedClass": cls or ""})


class TeacherUpdateAcademicReq(BaseModel):
    student_id: str
    academic_score: float


@router.post("/api/teacher/student/update_academic", tags=["👨‍🏫 2-审核端"], summary="教师：修改学生学业成绩")
def teacher_update_academic(
    req: TeacherUpdateAcademicReq,
    current_user: User = Depends(require_role(ROLE_TEACHER, ROLE_ADMIN)),
    db: Session = Depends(get_db)
):
    sp = db.query(StudentProfile).filter(StudentProfile.student_id == req.student_id).first()
    if not sp:
        return ApiResponse.error(404, "学生不存在")
    if current_user.role == ROLE_TEACHER:
        if not current_user.managed_class or sp.class_name != current_user.managed_class:
            return ApiResponse.error(403, "只能修改自己负责班级学生的成绩")
    if is_student_finalized(db, sp.id):
        return ApiResponse.error(409, "该生综合测评已经终审，不能修改学业成绩")
    if req.academic_score < 0 or req.academic_score > 100:
        return ApiResponse.error(400, "成绩应在 0-100 之间")
    sp.academic_score = req.academic_score
    sync_score_and_ranks(db, sp, calculate_student_accounting(db, sp, use_final_snapshot=False))
    db.commit()
    return ApiResponse.success(message="学业成绩已更新")


# ========== 管理员端：教师管理 ==========
@router.get("/api/admin/teacher/list", tags=["🛡️ 3-管理端"], summary="管理员：教师列表（支持搜索）")
def admin_teacher_list(
    keyword: str = "", current_user: User = Depends(require_role(ROLE_ADMIN)), db: Session = Depends(get_db)
):
    query = db.query(User).filter(User.role == ROLE_TEACHER)
    if keyword:
        kw = f"%{keyword}%"
        query = query.filter((User.username.like(kw)) | (User.real_name.like(kw)) | (User.managed_class.like(kw)))
    rows = []
    for u in query.order_by(User.id).all():
        rows.append({
            "id": u.id, "role": u.role, "username": u.username, "realName": u.real_name,
            "email": u.email, "phone": u.phone, "age": u.age,
            "managedClass": u.managed_class,
            "isActive": bool(u.is_active),
            "isLocked": bool(u.locked_until and u.locked_until > datetime.now()),
        })
    return ApiResponse.success({"list": rows})


class TeacherCreateReq(BaseModel):
    username: str
    real_name: str
    managed_class: Optional[str] = ""
    email: Optional[str] = ""
    phone: Optional[str] = ""
    age: Optional[int] = None


@router.post("/api/admin/teacher/create", tags=["🛡️ 3-管理端"], summary="管理员：新增教师（密码默认123456）")
def admin_teacher_create(
    req: TeacherCreateReq, current_user: User = Depends(require_role(ROLE_ADMIN)), db: Session = Depends(get_db)
):
    if not req.username or not req.real_name:
        return ApiResponse.error(400, "账号和姓名必填")
    if db.query(User).filter(User.username == req.username).first():
        return ApiResponse.error(400, "账号已存在")
    managed_class = ""
    if req.managed_class:
        managed_class = normalize_class_name(req.managed_class)
        if not managed_class:
            return ApiResponse.error(400, "负责班级名称不合法")
    u = User(
        username=req.username, password=get_password_hash("123456"),
        role=ROLE_TEACHER, real_name=req.real_name,
        email=req.email or "", phone=req.phone or "",
        age=req.age, managed_class=managed_class
    )
    db.add(u); db.commit()
    return ApiResponse.success({"id": u.id}, message="教师创建成功，密码 123456")


@router.delete("/api/admin/teacher/delete/{user_id}", tags=["🛡️ 3-管理端"], summary="管理员：删除教师")
def admin_teacher_delete(
    user_id: int, current_user: User = Depends(require_role(ROLE_ADMIN)), db: Session = Depends(get_db)
):
    u = db.query(User).filter(User.id == user_id).first()
    if not u or u.role != ROLE_TEACHER:
        return ApiResponse.error(404, "教师不存在")
    if db.query(AuditRecord).filter(AuditRecord.auditor_id == u.id).first():
        u.is_active = False
        u.managed_class = ""
        db.commit()
        return ApiResponse.success(message="教师存在历史审核记录，已停用账号并撤销班级分配")
    db.delete(u); db.commit()
    return ApiResponse.success(message="删除成功")


# ========== 管理员端：班级管理 ==========
@router.get("/api/admin/class/list", tags=["🛡️ 3-管理端"], summary="管理员：班级聚合列表（含老师/学生，支持班级搜索，含空班级）")
def admin_class_list(
    keyword: str = "", current_user: User = Depends(require_role(ROLE_ADMIN)), db: Session = Depends(get_db)
):
    class_names_from_students = set([sp.class_name for sp in db.query(StudentProfile).all() if sp.class_name])
    class_names_from_meta = set([cm.class_name for cm in db.query(ClassMeta).all()])
    class_names_from_teachers = set([u.managed_class for u in db.query(User).filter(User.role == ROLE_TEACHER).all() if u.managed_class])
    classes = sorted(class_names_from_students | class_names_from_meta | class_names_from_teachers)
    if keyword:
        classes = [c for c in classes if keyword in c]
    t_by_cls: Dict[str, list] = {}
    for u in db.query(User).filter(User.role == ROLE_TEACHER).all():
        if u.managed_class:
            t_by_cls.setdefault(u.managed_class, []).append({
                "id": u.id, "username": u.username, "realName": u.real_name,
                "email": u.email, "phone": u.phone, "age": u.age
            })
    result = []
    for cn in classes:
        students = db.query(StudentProfile).filter(StudentProfile.class_name == cn).order_by(StudentProfile.student_id).all()
        stu_rows = []
        for sp in students:
            u = sp.user
            stu_rows.append({
                "id": sp.id, "userId": u.id, "studentId": sp.student_id, "realName": u.real_name,
                "academicScore": sp.academic_score, "moralScore": sp.moral_score,
                "email": u.email, "phone": u.phone, "age": u.age,
            })
        result.append({
            "className": cn,
            "teachers": t_by_cls.get(cn, []),
            "studentCount": len(stu_rows),
            "students": stu_rows,
        })
    return ApiResponse.success({"list": result})


class ClassCreateReq(BaseModel):
    class_name: str


@router.post("/api/admin/class/create", tags=["🛡️ 3-管理端"], summary="管理员：新增班级（空班级立即出现在列表最末）")
def admin_class_create(
    req: ClassCreateReq, current_user: User = Depends(require_role(ROLE_ADMIN)), db: Session = Depends(get_db)
):
    cn = normalize_class_name(req.class_name)
    if not cn:
        return ApiResponse.error(400, "班级名称不合法，应为1-50个常用文字、字母或数字")
    existing = (
        db.query(ClassMeta).filter(ClassMeta.class_name == cn).first()
        or db.query(StudentProfile).filter(StudentProfile.class_name == cn).first()
        or db.query(User).filter(User.role == ROLE_TEACHER, User.managed_class == cn).first()
    )
    if existing:
        return ApiResponse.error(400, "该班级名称已存在")
    db.add(ClassMeta(class_name=cn))
    db.commit()
    return ApiResponse.success({"className": cn}, message="班级已创建，可立即分配老师或移入学生")


class ClassRenameReq(BaseModel):
    old_name: str
    new_name: str


@router.post("/api/admin/class/rename", tags=["🛡️ 3-管理端"], summary="管理员：修改班级名称（同步学生/负责老师/ClassMeta）")
def admin_class_rename(
    req: ClassRenameReq, current_user: User = Depends(require_role(ROLE_ADMIN)), db: Session = Depends(get_db)
):
    old_name = normalize_class_name(req.old_name)
    new_name = normalize_class_name(req.new_name)
    if not old_name or not new_name or old_name == new_name:
        return ApiResponse.error(400, "班级名称无效")
    conflict = (
        db.query(ClassMeta).filter(ClassMeta.class_name == new_name).first()
        or db.query(StudentProfile).filter(StudentProfile.class_name == new_name).first()
        or db.query(User).filter(User.role == ROLE_TEACHER, User.managed_class == new_name).first()
    )
    if conflict:
        return ApiResponse.error(400, "目标班级名称已存在")
    for sp in db.query(StudentProfile).filter(StudentProfile.class_name == old_name).all():
        sp.class_name = new_name
    for u in db.query(User).filter(User.role == ROLE_TEACHER, User.managed_class == old_name).all():
        u.managed_class = new_name
    for cm in db.query(ClassMeta).filter(ClassMeta.class_name == old_name).all():
        cm.class_name = new_name
    db.commit()
    return ApiResponse.success(message="班级名称已同步更新")


@router.delete("/api/admin/class/delete/{class_name:path}", tags=["🛡️ 3-管理端"], summary="管理员：删除空班级（无学生无负责老师）")
def admin_class_delete(
    class_name: str, current_user: User = Depends(require_role(ROLE_ADMIN)), db: Session = Depends(get_db)
):
    cnt_s = db.query(StudentProfile).filter(StudentProfile.class_name == class_name).count()
    cnt_t = db.query(User).filter(User.role == ROLE_TEACHER, User.managed_class == class_name).count()
    if cnt_s or cnt_t:
        return ApiResponse.error(400, f"班级内还有 {cnt_s} 名学生 {cnt_t} 名老师，请先移走后删除")
    for cm in db.query(ClassMeta).filter(ClassMeta.class_name == class_name).all():
        db.delete(cm)
    db.commit()
    return ApiResponse.success(message="空班级已删除")


class ClassMoveStudentReq(BaseModel):
    student_id: str
    target_class: str


@router.post("/api/admin/class/move_student", tags=["🛡️ 3-管理端"], summary="管理员：在班级间增/移学生（或移出留空）")
def admin_class_move_student(
    req: ClassMoveStudentReq, current_user: User = Depends(require_role(ROLE_ADMIN)), db: Session = Depends(get_db)
):
    sp = db.query(StudentProfile).filter(StudentProfile.student_id == req.student_id).first()
    if not sp:
        return ApiResponse.error(404, "学生不存在")
    sp.class_name = req.target_class
    db.commit()
    return ApiResponse.success(message=f"已更新到班级 {req.target_class}")


class ClassAssignTeacherReq(BaseModel):
    user_id: int
    target_class: str


@router.post("/api/admin/class/assign_teacher", tags=["🛡️ 3-管理端"], summary="管理员：给班级分配/撤销负责老师（target_class 为空即撤销）")
def admin_class_assign_teacher(
    req: ClassAssignTeacherReq, current_user: User = Depends(require_role(ROLE_ADMIN)), db: Session = Depends(get_db)
):
    u = db.query(User).filter(User.id == req.user_id).first()
    if not u or u.role != ROLE_TEACHER:
        return ApiResponse.error(404, "教师不存在")
    u.managed_class = req.target_class or ""
    db.commit()
    return ApiResponse.success(message="已更新负责班级")


# ========== 管理员端：任意用户信息编辑 ==========
class AdminEditUserReq(BaseModel):
    user_id: int
    username: Optional[str] = None
    real_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    age: Optional[int] = None
    managed_class: Optional[str] = None
    student_id: Optional[str] = None
    class_name: Optional[str] = None
    major: Optional[str] = None
    grade: Optional[str] = None
    moral_score: Optional[float] = None
    academic_score: Optional[float] = None
    new_password: Optional[str] = None
    reset_password: Optional[bool] = False
    is_active: Optional[bool] = None
    unlock_account: Optional[bool] = False


@router.post("/api/admin/user/edit", tags=["🛡️ 3-管理端"], summary="管理员：任意修改用户/学生/教师字段，可设置新密码或重置为123456")
def admin_edit_user(
    req: AdminEditUserReq, current_user: User = Depends(require_role(ROLE_ADMIN)), db: Session = Depends(get_db)
):
    u = db.query(User).filter(User.id == req.user_id).first()
    if not u:
        return ApiResponse.error(404, "用户不存在")
    if req.username:
        other = db.query(User).filter(User.username == req.username, User.id != u.id).first()
        if other:
            return ApiResponse.error(400, "账号已存在")
        u.username = req.username
    if req.real_name is not None:
        u.real_name = req.real_name
    if req.email is not None:
        u.email = req.email
    if req.phone is not None:
        u.phone = req.phone
    if req.age is not None:
        if req.age < 15 or req.age > 100:
            return ApiResponse.error(400, "年龄应在15-100之间")
        u.age = req.age
    if req.is_active is False and (u.id == current_user.id or u.username == "admin"):
        return ApiResponse.error(400, "不能停用当前登录账号或主管理员账号")
    if req.is_active is not None:
        u.is_active = req.is_active
    if req.unlock_account:
        u.failed_login_count = 0
        u.locked_until = None
    if req.managed_class is not None and u.role == ROLE_TEACHER:
        u.managed_class = req.managed_class
    if req.new_password and len(req.new_password) < 6:
        return ApiResponse.error(400, "密码长度至少 6 位")
    if req.new_password:
        u.password = get_password_hash(req.new_password)
        u.failed_login_count = 0
        u.locked_until = None
    elif req.reset_password:
        u.password = get_password_hash("123456")
        u.failed_login_count = 0
        u.locked_until = None
    if u.role == ROLE_STUDENT:
        sp = db.query(StudentProfile).filter(StudentProfile.user_id == u.id).first()
        if sp:
            if (req.moral_score is not None or req.academic_score is not None) and is_student_finalized(db, sp.id):
                return ApiResponse.error(409, "该生综合测评已经终审，不能修改基础分")
            if req.student_id:
                if not re.fullmatch(r"\d{6,20}", req.student_id.strip()):
                    return ApiResponse.error(400, "学号应为6-20位数字")
                other_sp = db.query(StudentProfile).filter(StudentProfile.student_id == req.student_id, StudentProfile.id != sp.id).first()
                if other_sp:
                    return ApiResponse.error(400, "学号已存在")
                sp.student_id = req.student_id
            if req.class_name is not None:
                sp.class_name = req.class_name
            if req.major is not None:
                sp.major = req.major
            if req.grade is not None:
                sp.grade = req.grade
            if req.moral_score is not None:
                if req.moral_score < 0 or req.moral_score > 100:
                    return ApiResponse.error(400, "思品分应在0-100之间")
                sp.moral_score = req.moral_score
            if req.academic_score is not None:
                if req.academic_score < 0 or req.academic_score > 100:
                    return ApiResponse.error(400, "学业成绩应在0-100之间")
                sp.academic_score = req.academic_score
            if req.moral_score is not None or req.academic_score is not None:
                sync_score_and_ranks(db, sp, calculate_student_accounting(db, sp, use_final_snapshot=False))
    db.commit()
    return ApiResponse.success(message="用户信息已更新")

# ========== 管理员端：管理员账号管理 ==========
@router.get("/api/admin/admin/list", tags=["🛡️ 3-管理端"], summary="管理员：管理员账号列表")
def admin_admin_list(
    current_user: User = Depends(require_role(ROLE_ADMIN)), db: Session = Depends(get_db)
):
    rows = []
    for u in db.query(User).filter(User.role == ROLE_ADMIN).order_by(User.id).all():
        rows.append({
            "id": u.id, "role": u.role, "username": u.username, "realName": u.real_name,
            "email": u.email, "phone": u.phone, "age": u.age,
            "canDelete": u.username != "admin",
            "isActive": bool(u.is_active),
            "isLocked": bool(u.locked_until and u.locked_until > datetime.now()),
        })
    return ApiResponse.success({"list": rows})


class AdminCreateReq(BaseModel):
    username: str
    password: str
    real_name: Optional[str] = None
    email: Optional[str] = ""
    phone: Optional[str] = ""
    age: Optional[int] = None


@router.post("/api/admin/admin/create", tags=["🛡️ 3-管理端"], summary="管理员：新创管理员账号")
def admin_admin_create(
    req: AdminCreateReq, current_user: User = Depends(require_role(ROLE_ADMIN)), db: Session = Depends(get_db)
):
    if not req.username or not req.password:
        return ApiResponse.error(400, "账号密码必填")
    if len(req.password) < 6:
        return ApiResponse.error(400, "密码至少6位")
    if db.query(User).filter(User.username == req.username).first():
        return ApiResponse.error(400, "账号已存在")
    u = User(
        username=req.username, password=get_password_hash(req.password),
        role=ROLE_ADMIN, real_name=req.real_name or req.username,
        email=req.email or "", phone=req.phone or "", age=req.age
    )
    db.add(u); db.commit()
    return ApiResponse.success({"id": u.id}, message="管理员创建成功")


@router.delete("/api/admin/admin/delete/{user_id}", tags=["🛡️ 3-管理端"], summary="管理员：删除管理员（admin 不可删）")
def admin_admin_delete(
    user_id: int, current_user: User = Depends(require_role(ROLE_ADMIN)), db: Session = Depends(get_db)
):
    u = db.query(User).filter(User.id == user_id).first()
    if not u or u.role != ROLE_ADMIN:
        return ApiResponse.error(404, "管理员不存在")
    if u.username == "admin":
        return ApiResponse.error(400, "admin 账号不可删除")
    if u.id == current_user.id:
        return ApiResponse.error(400, "不能删除当前登录账号")
    if db.query(AuditRecord).filter(AuditRecord.auditor_id == u.id).first():
        u.is_active = False
        db.commit()
        return ApiResponse.success(message="管理员存在历史审核记录，已改为停用账号")
    db.delete(u); db.commit()
    return ApiResponse.success(message="管理员账号已删除")
