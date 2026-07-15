from fastapi import APIRouter

from zongce.core import *


router = APIRouter()


@router.get("/api/rule/list", tags=["🔓 0-登录与公共"], summary="加分规则列表（可按大类筛选）")
def rule_list(category: str = "", current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(ScoreRule).filter(ScoreRule.is_active == True)
    if category:
        query = query.filter(ScoreRule.category == category)
    items = query.order_by(ScoreRule.id.asc()).all()
    rows = []
    for it in items:
        coef = None
        if it.rank_coefficient:
            try:
                coef = json_lib.loads(it.rank_coefficient)
            except Exception:
                coef = {}
        rows.append({
            "id": it.id,
            "category": it.category,
            "subCategory": it.sub_category,
            "itemName": it.item_name,
            "baseScore": it.base_score,
            "maxScore": it.max_score,
            "policy": it.policy,
            "policyName": ["", "取最高", "累加", "封顶"][it.policy],
            "rankCoefficient": coef or {},
            "isActive": it.is_active
        })
    return ApiResponse.success(rows)


@router.get("/api/rule/grouped", tags=["🔓 0-登录与公共"], summary="加分规则按「大类→子类」分组（前端下拉联动用）")
def rule_grouped(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.query(ScoreRule).filter(ScoreRule.is_active == True).order_by(ScoreRule.id.asc()).all()
    result = {}
    for it in items:
        coef = None
        if it.rank_coefficient:
            try:
                coef = json_lib.loads(it.rank_coefficient)
            except Exception:
                coef = {}
        rule_data = {
            "id": it.id,
            "category": it.category,
            "subCategory": it.sub_category,
            "itemName": it.item_name,
            "baseScore": it.base_score,
            "maxScore": it.max_score,
            "policy": it.policy,
            "rankCoefficient": coef or {}
        }
        if it.category not in result:
            result[it.category] = {}
        if it.sub_category not in result[it.category]:
            result[it.category][it.sub_category] = []
        result[it.category][it.sub_category].append(rule_data)
    return ApiResponse.success(result)


class RuleCreate(BaseModel):
    category: str
    sub_category: str
    item_name: str
    base_score: float
    max_score: Optional[float] = None
    policy: int = POLICY_SUM
    rank_coefficient: Optional[Dict[str, Any]] = None


@router.post("/api/admin/rule/create", tags=["🛡️ 3-管理端"], summary="管理员：新增综测规则")
def admin_rule_create(req: RuleCreate, current_user: User = Depends(require_role(ROLE_ADMIN)), db: Session = Depends(get_db)):
    coef_str = None
    if req.rank_coefficient is not None:
        coef_str = json_lib.dumps(req.rank_coefficient, ensure_ascii=False)
    rule = ScoreRule(
        category=req.category,
        sub_category=req.sub_category,
        item_name=req.item_name,
        base_score=req.base_score,
        max_score=req.max_score,
        policy=req.policy,
        rank_coefficient=coef_str
    )
    db.add(rule)
    db.commit()
    return ApiResponse.success(message="规则创建成功")


@router.delete("/api/admin/rule/delete/{rule_id}", tags=["🛡️ 3-管理端"], summary="管理员：停用某条加分规则（软删除）")
def admin_rule_delete(rule_id: int, current_user: User = Depends(require_role(ROLE_ADMIN)), db: Session = Depends(get_db)):
    rule = db.query(ScoreRule).filter(ScoreRule.id == rule_id).first()
    if not rule:
        return ApiResponse.error(404, "规则不存在")
    rule.is_active = False
    db.commit()
    return ApiResponse.success(message="规则已停用")

# ========== 管理员端：规则编辑 ==========
class RuleEditReq(BaseModel):
    rule_id: int
    category: Optional[str] = None
    sub_category: Optional[str] = None
    item_name: Optional[str] = None
    base_score: Optional[float] = None
    max_score: Optional[float] = None
    policy: Optional[int] = None
    is_active: Optional[bool] = None


@router.post("/api/admin/rule/edit", tags=["🛡️ 3-管理端"], summary="管理员：编辑加分规则字段")
def admin_rule_edit(
    req: RuleEditReq, current_user: User = Depends(require_role(ROLE_ADMIN)), db: Session = Depends(get_db)
):
    r = db.query(ScoreRule).filter(ScoreRule.id == req.rule_id).first()
    if not r:
        return ApiResponse.error(404, "规则不存在")
    if req.category is not None:
        r.category = req.category
    if req.sub_category is not None:
        r.sub_category = req.sub_category
    if req.item_name is not None:
        r.item_name = req.item_name
    if req.base_score is not None:
        r.base_score = req.base_score
    if req.max_score is not None:
        r.max_score = req.max_score
    if req.policy is not None:
        r.policy = req.policy
    if req.is_active is not None:
        r.is_active = req.is_active
    db.commit()
    return ApiResponse.success(message="规则已更新")


@router.get("/api/admin/rule/list", tags=["🛡️ 3-管理端"], summary="管理员：规则列表（含已停用的，供增删改/启用停用切换使用）")
def admin_rule_list(category: str = "", current_user: User = Depends(require_role(ROLE_ADMIN)), db: Session = Depends(get_db)):
    query = db.query(ScoreRule)
    if category:
        query = query.filter(ScoreRule.category == category)
    items = query.order_by(ScoreRule.id.asc()).all()
    rows = []
    for it in items:
        coef = None
        if it.rank_coefficient:
            try:
                coef = json_lib.loads(it.rank_coefficient)
            except Exception:
                coef = {}
        rows.append({
            "id": it.id,
            "category": it.category,
            "subCategory": it.sub_category,
            "itemName": it.item_name,
            "baseScore": it.base_score,
            "maxScore": it.max_score,
            "policy": it.policy,
            "policyName": ["", "取最高", "累加", "封顶"][it.policy],
            "rankCoefficient": coef or {},
            "isActive": bool(it.is_active)
        })
    return ApiResponse.success(rows)
