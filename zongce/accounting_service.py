from zongce.core import *


ASSESSMENT_YEAR = os.environ.get("ZONGCE_ASSESSMENT_YEAR", str(datetime.now().year))
INNOVATION_MARKERS = ("学术", "创新", "学科", "科研", "技能", "资格", "竞赛")
WORK_MARKERS = ("学生工作", "干部", "岗位", "任职", "文体", "志愿", "实践", "党团", "班级活动")


def _round(value: float) -> float:
    return round(float(value or 0.0), 4)


def classify_bonus(category: str, sub_category: str = "") -> Optional[str]:
    text_value = f"{category or ''} {sub_category or ''}"
    if "思想" in text_value or "学业成绩" in text_value:
        return None
    if category in {"学术创新成果", "创新创业", "学科竞赛", "学术科研成果", "职业技能与资格证书"}:
        return "innovation"
    if category in {"学生工作", "学生工作与干部经历", "文体竞赛", "志愿服务与社会实践"}:
        return "work"
    if any(marker in text_value for marker in WORK_MARKERS):
        return "work"
    if any(marker in text_value for marker in INNOVATION_MARKERS):
        return "innovation"
    return None


def is_position_item(category: str, sub_category: str) -> bool:
    text_value = f"{category or ''} {sub_category or ''}"
    return any(marker in text_value for marker in ("岗位", "任职", "干部"))


def active_finalization(db: Session, student_profile_id: int, year: str = ASSESSMENT_YEAR):
    return db.query(ScoreFinalization).filter(
        ScoreFinalization.student_id == student_profile_id,
        ScoreFinalization.assessment_year == year,
        ScoreFinalization.is_finalized == True,
    ).first()


def is_student_finalized(db: Session, student_profile_id: int, year: str = ASSESSMENT_YEAR) -> bool:
    return active_finalization(db, student_profile_id, year) is not None


def log_operation(
    db: Session,
    actor_id: int,
    action: str,
    student_id: Optional[int] = None,
    entity_type: str = "accounting",
    entity_id: Optional[int] = None,
    detail: str = "",
):
    db.add(OperationLog(
        actor_id=actor_id,
        student_id=student_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        detail=detail[:2000],
    ))


def _aggregate_rule_scores(applications: List[ScoreApplication]) -> Dict[str, Any]:
    grouped: Dict[int, Dict[str, Any]] = {}
    ignored = []
    for application in applications:
        rule = application.rule
        if not rule:
            continue
        bucket = classify_bonus(rule.category, rule.sub_category)
        if not bucket:
            ignored.append({"applicationId": application.id, "category": rule.category})
            continue
        item = grouped.setdefault(rule.id, {
            "ruleId": rule.id,
            "category": rule.category,
            "subCategory": rule.sub_category,
            "policy": rule.policy,
            "maxScore": rule.max_score,
            "bucket": bucket,
            "scores": [],
            "applications": [],
        })
        score = _round(application.final_score if application.final_score is not None else application.system_calculated_score)
        item["scores"].append(score)
        item["applications"].append({
            "id": application.id,
            "projectName": application.project_name,
            "score": score,
        })

    details = []
    innovation_parts = []
    position_parts = []
    activity_parts = []
    for item in grouped.values():
        scores = item.pop("scores")
        raw = max(scores, default=0.0) if item["policy"] == POLICY_MAX else sum(scores)
        if item["maxScore"] is not None:
            raw = min(raw, float(item["maxScore"]))
        item["countedScore"] = _round(raw)
        details.append(item)
        if item["bucket"] == "innovation":
            innovation_parts.append(raw)
        elif is_position_item(item["category"], item["subCategory"]):
            position_parts.append(raw)
        else:
            activity_parts.append(raw)

    innovation = min(sum(innovation_parts), 7.0)
    position = min(sum(position_parts), 3.0)
    activities = min(sum(activity_parts), 4.0)
    work = min(position + activities, 7.0)
    return {
        "innovation": _round(innovation),
        "work": _round(work),
        "position": _round(position),
        "activities": _round(activities),
        "details": sorted(details, key=lambda value: (value["bucket"], value["category"], value["subCategory"])),
        "ignored": ignored,
    }


def _active_deductions(db: Session, student_profile_id: int, year: str) -> List[ScoreDeduction]:
    return db.query(ScoreDeduction).filter(
        ScoreDeduction.student_id == student_profile_id,
        ScoreDeduction.assessment_year == year,
        ScoreDeduction.is_active == True,
    ).order_by(ScoreDeduction.id).all()


def calculate_student_accounting(
    db: Session,
    student: StudentProfile,
    year: str = ASSESSMENT_YEAR,
    use_final_snapshot: bool = True,
) -> Dict[str, Any]:
    finalization = active_finalization(db, student.id, year)
    if finalization and use_final_snapshot:
        try:
            snapshot = json_lib.loads(finalization.snapshot_json)
            snapshot["isFinalized"] = True
            snapshot["finalizedAt"] = finalization.finalized_at.strftime("%Y-%m-%d %H:%M:%S") if finalization.finalized_at else ""
            return snapshot
        except (TypeError, ValueError):
            pass

    applications = db.query(ScoreApplication).filter(
        ScoreApplication.student_id == student.id,
        ScoreApplication.status == STATUS_PASSED,
    ).all()
    bonus = _aggregate_rule_scores(applications)
    deductions = _active_deductions(db, student.id, year)
    deduction_total = _round(sum(item.deduction_score for item in deductions))
    moral = _round(student.moral_score)
    academic = _round(student.academic_score)
    subtotal = _round(moral + academic + bonus["innovation"] + bonus["work"])
    total = _round(max(0.0, subtotal - deduction_total))
    return {
        "studentProfileId": student.id,
        "studentId": student.student_id,
        "studentName": student.user.real_name if student.user else "",
        "className": student.class_name,
        "assessmentYear": year,
        "moralScore": moral,
        "academicScore": academic,
        "innovationScore": bonus["innovation"],
        "workScore": bonus["work"],
        "positionScore": bonus["position"],
        "activityScore": bonus["activities"],
        "subtotal": subtotal,
        "deductionScore": deduction_total,
        "totalScore": total,
        "bonusDetails": bonus["details"],
        "ignoredApplications": bonus["ignored"],
        "deductions": [
            {
                "id": item.id,
                "ruleId": item.rule_id,
                "ruleSnapshot": item.rule_snapshot,
                "scope": item.scope,
                "score": _round(item.deduction_score),
                "reason": item.reason,
                "evidenceRef": item.evidence_ref,
                "createdAt": item.created_at.strftime("%Y-%m-%d %H:%M:%S") if item.created_at else "",
            }
            for item in deductions
        ],
        "isFinalized": bool(finalization),
        "finalizedAt": finalization.finalized_at.strftime("%Y-%m-%d %H:%M:%S") if finalization and finalization.finalized_at else "",
    }


def sync_score_result(db: Session, student: StudentProfile, accounting: Optional[Dict[str, Any]] = None) -> ScoreResult:
    accounting = accounting or calculate_student_accounting(db, student, use_final_snapshot=False)
    result = db.query(ScoreResult).filter(ScoreResult.student_id == student.id).first()
    if not result:
        result = ScoreResult(student_id=student.id)
        db.add(result)
    result.moral_score = accounting["moralScore"]
    result.academic_score = accounting["academicScore"]
    result.innovation_score = accounting["innovationScore"]
    result.work_score = accounting["workScore"]
    result.total_score = accounting["totalScore"]
    return result


def refresh_rank_cache(db: Session) -> None:
    """Refresh dense ranks from cached totals without recalculating every accounting detail."""
    students = db.query(StudentProfile).order_by(StudentProfile.id).all()
    cached: Dict[int, ScoreResult] = {
        item.student_id: item for item in db.query(ScoreResult).all()
    }
    for student in students:
        if student.id not in cached:
            cached[student.id] = sync_score_result(db, student)
    db.flush()

    def assign(group_attr: str, rank_attr: str) -> None:
        groups: Dict[str, List[StudentProfile]] = {}
        for student in students:
            groups.setdefault(str(getattr(student, group_attr) or ""), []).append(student)
        for members in groups.values():
            members.sort(key=lambda student: (-float(cached[student.id].total_score or 0), student.student_id))
            previous_score = None
            rank = 0
            for position, student in enumerate(members, 1):
                score = float(cached[student.id].total_score or 0)
                if previous_score is None or score != previous_score:
                    rank = position
                    previous_score = score
                setattr(cached[student.id], rank_attr, rank)

    assign("class_name", "class_rank")
    assign("grade", "grade_rank")
    db.flush()


def sync_score_and_ranks(
    db: Session,
    student: StudentProfile,
    accounting: Optional[Dict[str, Any]] = None,
) -> ScoreResult:
    result = sync_score_result(db, student, accounting)
    db.flush()
    refresh_rank_cache(db)
    return result


def calculate_accounting_with_ranks(db: Session, student: StudentProfile) -> Dict[str, Any]:
    accounting = calculate_student_accounting(db, student)
    cached = db.query(ScoreResult).filter(ScoreResult.student_id == student.id).first()
    if not cached or cached.class_rank is None or cached.grade_rank is None:
        refresh_rank_cache(db)
        cached = db.query(ScoreResult).filter(ScoreResult.student_id == student.id).first()
    accounting["classRank"] = cached.class_rank if cached else None
    accounting["gradeRank"] = cached.grade_rank if cached else None
    return accounting


def calculate_ranked_accounting(
    db: Session,
    students: Optional[List[StudentProfile]] = None,
    persist: bool = False,
) -> List[Dict[str, Any]]:
    """Calculate dense class/grade ranks from the same accounting snapshot used by the UI."""
    requested = students if students is not None else db.query(StudentProfile).order_by(StudentProfile.id).all()
    if persist:
        population = db.query(StudentProfile).order_by(StudentProfile.id).all()
        for student in population:
            sync_score_result(db, student, calculate_student_accounting(db, student, use_final_snapshot=False))
        db.flush()
        refresh_rank_cache(db)
    elif db.query(ScoreResult).filter(
        (ScoreResult.class_rank.is_(None)) | (ScoreResult.grade_rank.is_(None))
    ).first() is not None:
        refresh_rank_cache(db)
    return [calculate_accounting_with_ranks(db, student) for student in requested]
