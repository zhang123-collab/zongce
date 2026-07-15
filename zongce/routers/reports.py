from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from zongce.accounting_service import calculate_ranked_accounting
from zongce.core import *
from zongce.report_service import build_student_report


router = APIRouter()


def _can_view(user: User, student: StudentProfile) -> bool:
    if user.role == ROLE_ADMIN:
        return True
    if user.role == ROLE_TEACHER:
        return bool(user.managed_class and user.managed_class == student.class_name)
    return user.id == student.user_id


@router.get("/api/report/student/{student_id}.pdf", tags=["👤 4-通用"], summary="按权限导出个人综合测评PDF报告")
def student_pdf_report(
    student_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    student = db.query(StudentProfile).filter(StudentProfile.student_id == student_id).first()
    if not student or not _can_view(current_user, student):
        return ApiResponse.error(404, "学生不存在")
    ranked = calculate_ranked_accounting(db, [student])
    if not ranked:
        return ApiResponse.error(404, "核算结果不存在")
    output = build_student_report(ranked[0])
    filename = f"zongce_{student.student_id}.pdf"
    return StreamingResponse(
        output,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
