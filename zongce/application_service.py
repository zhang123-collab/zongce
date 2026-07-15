from datetime import datetime

from sqlalchemy.orm import Session

from zongce.core import (
    STATUS_DRAFT,
    STATUS_PASSED,
    STATUS_PENDING,
    STATUS_REJECTED,
    STATUS_WITHDRAWN,
    ScoreApplication,
)


EDITABLE_STATUSES = {STATUS_DRAFT, STATUS_REJECTED, STATUS_WITHDRAWN}
ALLOWED_TRANSITIONS = {
    STATUS_DRAFT: {STATUS_PENDING},
    STATUS_PENDING: {STATUS_PASSED, STATUS_REJECTED, STATUS_WITHDRAWN},
    STATUS_REJECTED: {STATUS_DRAFT, STATUS_PENDING},
    STATUS_WITHDRAWN: {STATUS_DRAFT, STATUS_PENDING},
    STATUS_PASSED: set(),
}


def validate_application_fields(
    project_name: str,
    team_rank: int,
    team_total: int,
    project_date: str = "",
    description: str = "",
    remark: str = "",
):
    name = (project_name or "").strip()
    if not name:
        return "项目名称为必填项"
    if len(name) > 200:
        return "项目名称不能超过200个字符"
    if team_rank < 1 or team_total < 1:
        return "团队排名和团队总人数必须为正整数"
    if team_rank > team_total:
        return "个人排名不能超过团队总人数"
    if len(description or "") > 500:
        return "项目描述不能超过500个字符"
    if len(remark or "") > 200:
        return "备注不能超过200个字符"
    if project_date:
        try:
            datetime.strptime(project_date, "%Y-%m-%d")
        except ValueError:
            return "项目日期格式应为 YYYY-MM-DD"
    return None


def normalize_pagination(page: int, page_size: int, maximum: int = 200):
    return max(1, page), min(max(1, page_size), maximum)


def transition_application(
    db: Session,
    application_id: int,
    student_id: int,
    allowed_from: set[int],
    target_status: int,
    extra_values=None,
):
    """带原状态条件更新，防止重复提交/撤回覆盖其他请求。"""
    if not all(target_status in ALLOWED_TRANSITIONS.get(status, set()) for status in allowed_from):
        raise ValueError("非法申请状态转换")
    values = {ScoreApplication.status: target_status}
    values.update(extra_values or {})
    updated = (
        db.query(ScoreApplication)
        .filter(
            ScoreApplication.id == application_id,
            ScoreApplication.student_id == student_id,
            ScoreApplication.status.in_(allowed_from),
        )
        .update(values, synchronize_session=False)
    )
    return updated == 1
