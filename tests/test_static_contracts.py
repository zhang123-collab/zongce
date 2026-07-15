import ast
import re
import unittest
from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
ROOT = APP_PATH.parent
PYTHON_FILES = [APP_PATH, *sorted((ROOT / "zongce").rglob("*.py"))]
SOURCES = {path: path.read_text(encoding="utf-8") for path in PYTHON_FILES}
SOURCE = "\n".join(SOURCES.values())
INDEX_HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
FRONTEND = INDEX_HTML + "\n" + "\n".join(
    path.read_text(encoding="utf-8") for path in sorted((ROOT / "static").glob("*.js"))
)


def function_source(name: str) -> str:
    for source in SOURCES.values():
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                return ast.get_source_segment(source, node) or ""
    raise AssertionError(f"function not found: {name}")


class StaticContractTests(unittest.TestCase):
    def test_delivery_scripts_and_local_secret_are_present(self):
        for name in ("安装依赖.bat", "启动系统.bat", "备份数据.bat"):
            self.assertTrue((ROOT / name).is_file())
        self.assertTrue((ROOT / "scripts" / "check_environment.py").is_file())
        self.assertTrue((ROOT / "scripts" / "backup_data.py").is_file())
        self.assertIn(".zongce_secret", (ROOT / ".gitignore").read_text(encoding="utf-8"))
        self.assertIn("application_secret", SOURCE)

    def test_docker_delivery_files_are_safe_and_documented(self):
        for name in ("Dockerfile", "docker-compose.yml", ".dockerignore", "项目说明.md", "Docker启动.bat", "Docker停止.bat"):
            self.assertTrue((ROOT / name).is_file())
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
        guide = (ROOT / "项目说明.md").read_text(encoding="utf-8")
        self.assertIn("sqlite:////app/data/zongce.db", compose)
        self.assertIn("zongce_data:/app/data", compose)
        self.assertIn("${DEEPSEEK_API_KEY:-}", compose)
        self.assertNotRegex(compose, r"sk-[A-Za-z0-9]{16,}")
        for sensitive in (".env", ".zongce_secret", "*.db", "uploads", "学生证明材料"):
            self.assertIn(sensitive, dockerignore)
        self.assertIn("docker compose up --build -d", guide)
        self.assertIn("/api/login", guide)

    def test_publication_ranking_report_and_single_ai_are_integrated(self):
        for marker in (
            "/api/announcement/list",
            "/api/objection",
            "/api/report/student/",
            "/api/ai/application/",
            "classRank",
            "gradeRank",
        ):
            self.assertIn(marker, FRONTEND)
        self.assertIn("content_hash", SOURCE)
        self.assertIn("calculate_ranked_accounting", SOURCE)
        self.assertIn("ApplicationAiAnalysis", SOURCE)

    def test_python_syntax(self):
        for path, source in SOURCES.items():
            compile(source, str(path), "exec")

    def test_import_does_not_install_packages(self):
        self.assertNotIn("subprocess.check_call", SOURCE)
        self.assertNotRegex(SOURCE, r"pip[\"']?\s*,\s*[\"']install")

    def test_upload_requires_student_and_application_access(self):
        body = function_source("upload_file")
        self.assertIn("require_role(ROLE_STUDENT)", SOURCE)
        self.assertIn("can_access_application", body)
        self.assertIn("len(app_rec.evidence_files) >= 5", body)
        self.assertIn("content.startswith(signature)", body)
        self.assertIn("uuid4().hex", body)

    def test_teacher_audits_are_class_scoped(self):
        for name in ("audit_pass", "audit_reject", "audit_modify"):
            self.assertIn("can_access_application", function_source(name))
        self.assertIn("current_user.managed_class", function_source("audit_pending_list"))

    def test_rejected_and_withdrawn_applications_can_be_reworked(self):
        update = function_source("update_application")
        submit = function_source("submit_application")
        service_source = (ROOT / "zongce" / "application_service.py").read_text(encoding="utf-8")
        self.assertIn("EDITABLE_STATUSES", update)
        self.assertIn("EDITABLE_STATUSES", submit)
        for status_name in ("STATUS_REJECTED", "STATUS_WITHDRAWN"):
            self.assertIn(status_name, service_source)

    def test_frontend_uploads_before_submit(self):
        match = re.search(
            r"async function saveCreateApp\(submit_now, editing_id\)\{(.*?)\n\}",
            FRONTEND,
            re.S,
        )
        self.assertIsNotNone(match)
        body = match.group(1)
        self.assertLess(body.index("uploadFile('/api/file/upload'"), body.index("/api/application/submit/"))

    def test_fresh_start_has_material_based_fallback(self):
        init = function_source("init_test_data")
        self.assertIn("if not profiles_raw", init)
        self.assertIn("for sid in sorted(sid2name)", init)

    def test_frontend_is_external_resource(self):
        self.assertNotIn("INDEX_HTML =", APP_PATH.read_text(encoding="utf-8"))
        self.assertIn("<html", INDEX_HTML)
        self.assertIn('/static/app.css', INDEX_HTML)
        self.assertIn('/static/app.js', INDEX_HTML)
        for script in ("common.js", "student.js", "teacher.js", "admin.js"):
            self.assertIn(f'/static/{script}', INDEX_HTML)

    def test_main_application_is_only_composition_and_startup(self):
        self.assertLess(len(APP_PATH.read_text(encoding="utf-8").splitlines()), 180)
        for module in ("audits.py", "rules.py", "admin.py"):
            self.assertTrue((ROOT / "zongce" / "routers" / module).is_file())
        self.assertTrue((ROOT / "zongce" / "seed.py").is_file())
        self.assertTrue((ROOT / "zongce" / "accounting_service.py").is_file())
        self.assertTrue((ROOT / "zongce" / "routers" / "accounting.py").is_file())
        self.assertTrue((ROOT / "zongce" / "batch_service.py").is_file())
        self.assertTrue((ROOT / "zongce" / "routers" / "batches.py").is_file())
        self.assertTrue((ROOT / "zongce" / "routers" / "ai.py").is_file())
        self.assertTrue((ROOT / "zongce" / "ai" / "redaction.py").is_file())
        self.assertTrue((ROOT / "zongce" / "ai" / "extraction.py").is_file())

    def test_role_frontend_is_split_and_uses_safe_evidence_access(self):
        common = (ROOT / "static" / "common.js").read_text(encoding="utf-8")
        teacher = (ROOT / "static" / "teacher.js").read_text(encoding="utf-8")
        self.assertIn("function escapeHtml", common)
        self.assertIn("openEvidence(${f.id})", teacher)
        self.assertNotIn("window.open('${p}')", teacher)
        self.assertIn("button.disabled=true", common)

    def test_login_has_lockout(self):
        auth = function_source("_authenticate_user")
        self.assertIn("MAX_LOGIN_ATTEMPTS", auth)
        self.assertIn("locked_until", auth)

    def test_database_dependency_rolls_back_failed_requests(self):
        dependency = function_source("get_db")
        self.assertIn("except Exception", dependency)
        self.assertIn("db.rollback()", dependency)

    def test_frontend_locks_critical_duplicate_actions(self):
        common = (ROOT / "static" / "common.js").read_text(encoding="utf-8")
        teacher = (ROOT / "static" / "teacher.js").read_text(encoding="utf-8")
        student = (ROOT / "static" / "student.js").read_text(encoding="utf-8")
        self.assertIn("beginAction('login')", common)
        self.assertIn("'academic:'+sid", teacher)
        self.assertIn("'withdraw:'+id", student)
        self.assertIn("'delete:'+id", student)

    def test_accounting_is_integrated_into_split_role_frontends(self):
        student = (ROOT / "static" / "student.js").read_text(encoding="utf-8")
        teacher = (ROOT / "static" / "teacher.js").read_text(encoding="utf-8")
        admin = (ROOT / "static" / "admin.js").read_text(encoding="utf-8")
        self.assertIn("/api/accounting/me", student)
        self.assertIn("/api/accounting/list", teacher)
        self.assertIn("/api/admin/accounting/finalize/", admin)
        self.assertIn("/api/admin/accounting/deduction", admin)
        self.assertIn("/api/admin/accounting/export", admin)

    def test_batch_import_is_integrated_into_student_frontend(self):
        student = (ROOT / "static" / "student.js").read_text(encoding="utf-8")
        batch_service = (ROOT / "zongce" / "batch_service.py").read_text(encoding="utf-8")
        self.assertIn("/api/batch/upload", student)
        self.assertIn("/api/batch/template", student)
        self.assertIn("beginAction('batch-upload')", student)
        self.assertIn("zipfile.ZipFile", batch_service)
        self.assertIn("content.startswith(signature)", batch_service)

    def test_ai_is_advisory_and_redacts_before_external_call(self):
        student = (ROOT / "static" / "student.js").read_text(encoding="utf-8")
        task_service = (ROOT / "zongce" / "ai" / "task_service.py").read_text(encoding="utf-8")
        deepseek = (ROOT / "zongce" / "ai" / "deepseek.py").read_text(encoding="utf-8")
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("/api/ai/batch/", student)
        self.assertIn("AI结果仅供人工审核参考", student)
        self.assertLess(task_service.index("redacted_material = redact_text"), task_service.index("call_deepseek_batch(payloads"))
        self.assertNotIn("system_calculated_score", task_service)
        self.assertNotIn("final_score", task_service)
        self.assertIn('os.environ.get("DEEPSEEK_API_KEY"', deepseek)
        self.assertIn(".env", gitignore)

    def test_role_workspaces_use_real_data_and_unified_navigation(self):
        common = (ROOT / "static" / "common.js").read_text(encoding="utf-8")
        student = (ROOT / "static" / "student.js").read_text(encoding="utf-8")
        teacher = (ROOT / "static" / "teacher.js").read_text(encoding="utf-8")
        admin = (ROOT / "static" / "admin.js").read_text(encoding="utf-8")
        css = (ROOT / "static" / "app.css").read_text(encoding="utf-8")
        self.assertIn('id="sidebar"', INDEX_HTML)
        self.assertIn("function workspaceWrap", common)
        self.assertIn("function renderRoleNav", common)
        self.assertIn("function focusModule", common)
        self.assertIn("loadStudentOverview", student)
        self.assertIn("/api/accounting/me", student)
        self.assertIn("updateRuleEstimate", student)
        self.assertIn("loadTeacherOverview", teacher)
        self.assertIn("/api/application/list?page_size=999", teacher)
        self.assertIn("loadAdminOverview", admin)
        self.assertIn("/api/admin/accounting/overview", admin)
        self.assertIn(".side-nav-item", css)
        self.assertIn(".overview-grid", css)
        self.assertNotIn("DEMO_USERS", FRONTEND)

    def test_admin_can_create_one_student_without_excel(self):
        admin = (ROOT / "static" / "admin.js").read_text(encoding="utf-8")
        self.assertIn("function newStudentDlg", admin)
        self.assertIn("/api/admin/student/create", admin)
        self.assertIn("＋ 新增学生", admin)
        self.assertIn("/api/admin/student/import", admin)


if __name__ == "__main__":
    unittest.main()
