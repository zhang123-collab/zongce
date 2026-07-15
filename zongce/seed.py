from zongce.core import *


def _scan_student_materials(base_dir: str):
    name_map = {}          # sid -> 真实姓名
    files_meta = []        # [(sid, type_code, file_name, abs_path)]
    # type_code: 1=云支教证明  2=暑期社会实践  3=老证明材料(仅建档不建申请)
    if not os.path.isdir(base_dir):
        return name_map, files_meta

    cloud_dir = os.path.join(base_dir, "云支教证明材料")
    summer_dir = os.path.join(base_dir, "暑期实践证明材料")
    old_dir = os.path.join(base_dir, "老证明材料")

    if os.path.isdir(cloud_dir):
        for fn in os.listdir(cloud_dir):
            if not fn.lower().endswith(".pdf"):
                continue
            m = re.match(r"^(.+?)(\d{12})云支教证明\.pdf$", fn)
            if not m:
                continue
            name, sid = m.group(1).strip(), m.group(2)
            name_map[sid] = name
            files_meta.append((sid, 1, fn, os.path.join(cloud_dir, fn)))

    if os.path.isdir(summer_dir):
        for fn in os.listdir(summer_dir):
            if not fn.lower().endswith(".pdf"):
                continue
            m = re.match(r"^(\d{12})\s+(.+)\.pdf$", fn)
            if not m:
                continue
            sid, name = m.group(1), m.group(2).strip()
            name_map[sid] = name
            files_meta.append((sid, 2, fn, os.path.join(summer_dir, fn)))

    if os.path.isdir(old_dir):
        for fn in os.listdir(old_dir):
            if not fn.lower().endswith(".pdf"):
                continue
            m = re.match(r"^(\d{12})\s+(.+)\.pdf$", fn)
            if not m:
                continue
            sid, name = m.group(1), m.group(2).strip()
            name_map[sid] = name
            files_meta.append((sid, 3, fn, os.path.join(old_dir, fn)))

    return name_map, files_meta


def init_test_data(db: Session):
    if db.query(User).count() > 0:
        return

    # ===== 预先扫描证明材料文件夹（拿真实姓名 & 材料清单） =====
    project_dir = PROJECT_DIR
    material_dir = os.path.join(project_dir, "学生证明材料")
    sid2name, files_meta = _scan_student_materials(material_dir)

    sql_path = os.path.join(project_dir, "data.sql")
    text = ""
    if os.path.exists(sql_path):
        with open(sql_path, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        print("[初始化提示] 未找到 data.sql，将根据证明材料文件名创建可登录的演示学生。")

    # ===================== 1) 基础账号（忽略 data.sql 中伪造的 password hash，用真实算法重新生成） =====================
    admin = User(username="admin", password=get_password_hash("123456"),
                 role=ROLE_ADMIN, real_name="系统管理员", email="admin@example.com", age=38)
    teacher = User(username="teacher01", password=get_password_hash("123456"),
                   role=ROLE_TEACHER, real_name="张老师", email="teacher01@example.com",
                   age=32, managed_class="2023级1班")
    db.add_all([admin, teacher])
    db.flush()

    # ===================== 2) 34 条学生档案 + 34 个学生账号（用户名=学号，真实姓名来自证明材料文件名） =====================
    m = re.search(r"INSERT INTO `student_profile`\s*\([^)]+\)\s*VALUES\s*(.*?);", text, re.S | re.I)
    profiles_raw = []
    if m:
        values_str = m.group(1).strip()
        for tup_str in re.findall(r"\(([^)]+)\)", values_str):
            parts = [p.strip().strip("'\"") for p in tup_str.split(",")]
            if len(parts) < 7:
                continue
            try:
                profiles_raw.append((parts[1], parts[2], parts[3], parts[4],
                                     float(parts[5]), float(parts[6])))
            except (ValueError, IndexError):
                continue
    if not profiles_raw:
        for sid in sorted(sid2name):
            grade = sid[:4] if len(sid) >= 4 and sid[:4].isdigit() else "2023"
            profiles_raw.append((
                sid,
                f"{grade}级1班",
                "计算机类",
                grade,
                0.0,
                0.0,
            ))

    students_map = {}       # sid -> User
    extra_users = []
    used_usernames = {"admin", "teacher01"}
    for i, (sid, cn, mj, gd, ms, ac) in enumerate(profiles_raw):
        uname = sid                          # 直接用学号作登录名，不重复
        used_usernames.add(uname)
        real_name = sid2name.get(sid, f"学生{i+1:02d}")
        default_age = 18 + (i % 4)
        u = User(
            username=uname, password=get_password_hash("123456"),
            role=ROLE_STUDENT, real_name=real_name,
            email=f"s{sid}@example.com", age=default_age
        )
        extra_users.append(u)
        students_map[sid] = u
    db.add_all(extra_users)
    db.flush()

    sp_map = {}  # sid -> StudentProfile
    for i, (sid, cn, mj, gd, ms, ac) in enumerate(profiles_raw):
        u = students_map[sid]
        sp = StudentProfile(
            user_id=u.id, student_id=sid, class_name=cn, major=mj, grade=gd,
            moral_score=ms, academic_score=ac
        )
        db.add(sp)
        sp_map[sid] = sp
    db.flush()

    # ===================== 3) 31 条综测规则 + 2 条材料文件夹对应的社会实践规则（云支教/暑期实践，data.sql 原缺） =====================
    m2 = re.search(r"INSERT INTO `score_rule`\s*\([^)]+\)\s*VALUES\s*(.*?);", text, re.S | re.I)
    rules_raw = []
    if m2:
        for tup_str in re.findall(r"\(([^)]+)\)", m2.group(1).strip()):
            parts = [p.strip() for p in tup_str.split(",")]
            if len(parts) < 5:
                continue
            try:
                cat = parts[0].strip("'\"")
                sub = parts[1].strip("'\"")
                bs = float(parts[2])
                mx = float(parts[3])
                pol = int(parts[4])
                rules_raw.append((cat, sub, bs, mx, pol))
            except (ValueError, IndexError):
                continue
    # 补 2 条社会实践规则，正好匹配证明材料文件夹，再额外补 20+ 条常见规则范例（确保创建加分申请下拉框一定有内容）
    extra_rules = [
        # —— 材料文件夹对应的两条（保留）
        ("学术创新成果", "社会实践_云支教证明", 0.5, 7.0, POLICY_SUM),
        ("学术创新成果", "社会实践_暑期实践证明", 0.3, 7.0, POLICY_SUM),
        # —— 常见大类：思想道德 / 学业成绩 / 创新创业 / 学科竞赛 / 文体竞赛 / 志愿服务 / 技能证书 / 学术科研 / 学生工作 / 文艺体育 / 其他
        ("思想道德与公民素养", "见义勇为/好人好事", 0.5, 5.0, POLICY_SUM),
        ("思想道德与公民素养", "党课团课结业", 0.3, 3.0, POLICY_SUM),
        ("学业成绩", "专业成绩排名前5%", 2.0, 3.0, POLICY_MAX),
        ("学业成绩", "专业成绩排名前10%-20%", 1.0, 2.0, POLICY_MAX),
        ("创新创业", "大学生创新创业训练计划（大创）", 1.0, 8.0, POLICY_SUM),
        ("创新创业", "互联网+创新创业大赛", 1.0, 10.0, POLICY_MAX),
        ("创新创业", "挑战杯创业计划竞赛", 1.0, 10.0, POLICY_MAX),
        ("学科竞赛", "蓝桥杯程序设计大赛", 0.5, 5.0, POLICY_MAX),
        ("学科竞赛", "数学建模竞赛", 0.5, 6.0, POLICY_MAX),
        ("学科竞赛", "英语演讲/写作比赛", 0.3, 4.0, POLICY_MAX),
        ("文体竞赛", "运动会个人项目", 0.3, 4.0, POLICY_MAX),
        ("文体竞赛", "文艺晚会/歌唱比赛", 0.3, 4.0, POLICY_MAX),
        ("志愿服务与社会实践", "志愿服务时长≥20小时", 0.2, 3.0, POLICY_SUM),
        ("志愿服务与社会实践", "社区服务/乡村振兴实践", 0.5, 5.0, POLICY_SUM),
        ("学生工作与干部经历", "班长/团支书/学生会干部", 0.5, 3.0, POLICY_MAX),
        ("学生工作与干部经历", "社团负责人", 0.3, 2.0, POLICY_MAX),
        ("学术科研成果", "发表学术论文普刊", 2.0, 5.0, POLICY_SUM),
        ("学术科研成果", "发表SCI/EI/核心期刊", 5.0, 10.0, POLICY_SUM),
        ("职业技能与资格证书", "英语六级/CET-6", 0.5, 2.0, POLICY_MAX),
        ("职业技能与资格证书", "计算机二级/三级", 0.3, 2.0, POLICY_MAX),
        ("职业技能与资格证书", "教师资格证/法律职业资格", 1.0, 3.0, POLICY_SUM),
    ]
    rules_raw.extend(extra_rules)

    rule_map = {}    # (category, sub_category) -> ScoreRule
    for cat, sub, bs, mx, pol in rules_raw:
        if pol not in (POLICY_MAX, POLICY_SUM):
            pol = POLICY_SUM
        r = ScoreRule(
            category=cat, sub_category=sub, item_name=sub,
            base_score=bs, max_score=mx, policy=pol, rank_coefficient=None
        )
        db.add(r)
        rule_map[(cat, sub)] = r
    db.flush()

    # ===================== 4) 34 条分数结果（子查询找 student_profile.id） =====================
    m3 = re.search(r"INSERT INTO `score_result`\s*\([^)]+\)\s*VALUES\s*(.*?);", text, re.S | re.I)
    results_raw = []
    if m3:
        values_str = m3.group(1).strip()
        sub_pat = (r"\(\(\s*SELECT\s+id\s+FROM\s+`?student_profile`?\s+WHERE\s+"
                   r"`?student_id`?\s*=\s*'([^']+)'\s*\),\s*([\d.]+),\s*([\d.]+),"
                   r"\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)\)")
        for mm in re.finditer(sub_pat, values_str):
            try:
                sid = mm.group(1)
                ms = float(mm.group(2))
                ac = float(mm.group(3))
                ins = float(mm.group(4))
                ws = float(mm.group(5))
                ts = float(mm.group(6))
                results_raw.append((sid, ms, ac, ins, ws, ts))
            except (ValueError, IndexError):
                continue
    for sid, ms, ac, ins, ws, ts in results_raw:
        sp = sp_map.get(sid)
        if sp:
            sr = ScoreResult(
                student_id=sp.id, moral_score=ms, academic_score=ac,
                innovation_score=ins, work_score=ws, total_score=ts
            )
            db.add(sr)
    db.flush()

    # ===================== 5) 根据证明材料自动生成已通过的加分申请 + 证据文件 + 审核记录 =====================
    cloud_rule = rule_map.get(("学术创新成果", "社会实践_云支教证明"))
    summer_rule = rule_map.get(("学术创新成果", "社会实践_暑期实践证明"))
    app_count = 0
    file_count = 0
    for sid, type_code, fn, abs_path in files_meta:
        sp = sp_map.get(sid)
        if not sp:
            continue
        rule = None
        if type_code == 1:
            rule = cloud_rule
        elif type_code == 2:
            rule = summer_rule
        evidence = EvidenceFile(
            file_name=fn, file_path=abs_path,
            file_size=os.path.getsize(abs_path) if os.path.exists(abs_path) else 0,
            file_type="application/pdf"
        )
        db.add(evidence)
        file_count += 1

        if type_code == 3 or rule is None:   # 老证明材料：不推测类别，仅建档为材料记录，暂不绑申请
            continue

        sys_score = rule.base_score
        app = ScoreApplication(
            student_id=sp.id,
            rule_id=rule.id,
            project_name=f"{rule.item_name}-{sid2name.get(sid, fn)}",
            system_calculated_score=sys_score,
            final_score=sys_score,
            status=STATUS_PASSED,
            submitted_at=datetime.now()
        )
        db.add(app)
        db.flush()                    # flush 拿到 app.id 和 evidence.id
        app_count += 1
        evidence.application_id = app.id
        ar = AuditRecord(
            application_id=app.id, auditor_id=admin.id,
            result=AUDIT_PASS, modified_score=sys_score,
            opinion=f"材料 {fn} 已审核通过（初始化时根据证明材料自动入库）"
        )
        db.add(ar)

    db.commit()
    real_name_count = len(sid2name)
    print("===== 从 data.sql + 学生证明材料 加载真实数据完成 =====")
    print(f"- 账号总数：{db.query(User).count()}（管理员1 / 老师1 / 学生{db.query(User).filter(User.role==ROLE_STUDENT).count()}）")
    print(f"- 学生档案：{len(profiles_raw)} 条，已匹配真实姓名：{real_name_count}/{len(profiles_raw)}")
    print(f"- 加分规则：{len(rules_raw)} 条（含新增 云支教证明 0.5 分 / 暑期实践证明 0.3 分）")
    print(f"- 分数结果：{len(results_raw)} 条")
    print(f"- 证明材料：{file_count} 份 PDF 已建档，自动生成 STATUS_PASSED 已通过申请 {app_count} 条")
    print("演示账号（密码均为 123456）：")
    print(f"  管理员：admin          老师：teacher01")
    if profiles_raw:
        samples = [(sid, sid2name.get(sid, f"学生{i+1:02d}")) for i, sid in enumerate(
            [p[0] for p in profiles_raw[:4]])]
        for sid, rn in samples:
            print(f"  学生：{sid}   （姓名：{rn}）")
    print("其余学生登录账号=学号，可在 admin 登录后通过 GET /api/admin/student/list 查询")


def _warn_if_old_db(db: Session) -> bool:
    try:
        bad_user = db.query(User).filter(
            (User.username == "student01") | (User.username == "teacher02") | (User.username == "student03")
        ).first()
        bad_profile = db.query(StudentProfile).filter(
            (StudentProfile.class_name.like("计算机23%")) |
            (StudentProfile.moral_score > 10.0)
        ).first()
        return (bad_user is not None) or (bad_profile is not None)
    except Exception:
        return False


def initialize_demo_data():
    with SessionLocal() as db:
        if db.query(User).count() > 0 and _warn_if_old_db(db):
            print("[数据库提示] 检测到旧演示数据；如需重新加载当前材料，请备份后删除 zongce.db。")
        init_test_data(db)
