from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.openapi.docs import get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html
from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime, ForeignKey, Boolean, UniqueConstraint, inspect, text, func
from sqlalchemy.orm import sessionmaker, Session, relationship, declarative_base
import os
import re
import hashlib
import secrets
import json as json_lib
import uvicorn
from jose import JWTError, jwt
from passlib.context import CryptContext

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_project_env():
    """Load local configuration before database/auth settings are evaluated."""
    env_path = os.path.join(PROJECT_DIR, ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path, "r", encoding="utf-8-sig") as stream:
        for raw_line in stream:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key.replace("_", "").isalnum():
                os.environ.setdefault(key, value)


def application_secret() -> str:
    configured = os.environ.get("ZONGCE_SECRET_KEY", "").strip()
    if configured and configured != "replace-with-a-long-random-secret":
        return configured
    secret_path = os.path.join(PROJECT_DIR, ".zongce_secret")
    if os.path.isfile(secret_path):
        with open(secret_path, "r", encoding="ascii") as stream:
            saved = stream.read().strip()
        if len(saved) >= 32:
            return saved
    generated = secrets.token_urlsafe(48)
    temporary = secret_path + ".tmp"
    with open(temporary, "w", encoding="ascii") as stream:
        stream.write(generated)
    os.replace(temporary, secret_path)
    return generated


load_project_env()
UPLOAD_DIR = os.environ.get("ZONGCE_UPLOAD_DIR", os.path.join(PROJECT_DIR, "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)

SECRET_KEY = application_secret()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCK_MINUTES = 30

default_db_path = os.path.join(PROJECT_DIR, "zongce.db").replace("\\", "/")
SQLALCHEMY_DATABASE_URL = os.environ.get("ZONGCE_DATABASE_URL", f"sqlite:///{default_db_path}")
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ROLE_STUDENT = 0
ROLE_TEACHER = 1
ROLE_ADMIN = 2

STATUS_DRAFT = 0
STATUS_PENDING = 1
STATUS_PASSED = 2
STATUS_REJECTED = 3
STATUS_WITHDRAWN = 4

STATUS_TEXT = {
    STATUS_DRAFT: "草稿",
    STATUS_PENDING: "审核中",
    STATUS_PASSED: "已通过",
    STATUS_REJECTED: "未通过",
    STATUS_WITHDRAWN: "已撤回",
}

AUDIT_PASS = 1
AUDIT_REJECT = 2
AUDIT_MODIFY = 3

POLICY_MAX = 1
POLICY_SUM = 2
POLICY_LIMIT = 3


class User(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(Integer, default=ROLE_STUDENT, nullable=False)
    real_name = Column(String(50), nullable=False)
    email = Column(String(100), default="")
    phone = Column(String(20), default="")
    age = Column(Integer, default=None)
    managed_class = Column(String(50), default="")
    is_active = Column(Boolean, default=True, nullable=False)
    failed_login_count = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, default=None)
    last_login_at = Column(DateTime, default=None)
    created_at = Column(DateTime, default=datetime.now)


class StudentProfile(Base):
    __tablename__ = "student_profile"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id"), unique=True)
    student_id = Column(String(20), unique=True, nullable=False)
    class_name = Column(String(50), nullable=False)
    major = Column(String(100), nullable=False)
    grade = Column(String(10), default="2023")
    moral_score = Column(Float, default=0.0)
    academic_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.now)
    user = relationship("User")


class ScoreRule(Base):
    __tablename__ = "score_rule"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    category = Column(String(50), nullable=False)
    sub_category = Column(String(50), nullable=False)
    item_name = Column(String(100), nullable=False)
    base_score = Column(Float, nullable=False)
    max_score = Column(Float, default=None)
    policy = Column(Integer, default=POLICY_SUM)
    rank_coefficient = Column(String(1000), default=None)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


class ScoreApplication(Base):
    __tablename__ = "score_application"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("student_profile.id"))
    rule_id = Column(Integer, ForeignKey("score_rule.id"))
    project_name = Column(String(200), nullable=False)
    project_level = Column(String(50), default="")
    team_rank = Column(Integer, default=1)
    team_total = Column(Integer, default=1)
    project_date = Column(String(30), default="")
    description = Column(Text, default="")
    status = Column(Integer, default=STATUS_DRAFT)
    system_calculated_score = Column(Float, default=0.0)
    final_score = Column(Float, default=0.0)
    remark = Column(Text, default="")
    reject_reason = Column(Text, default="")
    submitted_at = Column(DateTime, default=None)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    student = relationship("StudentProfile")
    rule = relationship("ScoreRule")
    evidence_files = relationship("EvidenceFile", back_populates="application", cascade="all, delete-orphan")
    audit_records = relationship("AuditRecord", back_populates="application", cascade="all, delete-orphan")


class EvidenceFile(Base):
    __tablename__ = "evidence_file"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("score_application.id"))
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, default=0)
    file_type = Column(String(50), default="")
    content_hash = Column(String(64), default="", index=True)
    uploaded_at = Column(DateTime, default=datetime.now)
    application = relationship("ScoreApplication", back_populates="evidence_files")


class AuditRecord(Base):
    __tablename__ = "audit_record"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("score_application.id"))
    auditor_id = Column(Integer, ForeignKey("user.id"))
    result = Column(Integer, nullable=False)
    modified_score = Column(Float, default=None)
    opinion = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now)
    application = relationship("ScoreApplication", back_populates="audit_records")
    auditor = relationship("User")


class ScoreResult(Base):
    __tablename__ = "score_result"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("student_profile.id"), unique=True)
    moral_score = Column(Float, default=0.0)
    academic_score = Column(Float, default=0.0)
    innovation_score = Column(Float, default=0.0)
    work_score = Column(Float, default=0.0)
    total_score = Column(Float, default=0.0)
    class_rank = Column(Integer, default=None)
    grade_rank = Column(Integer, default=None)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class ScoreDeduction(Base):
    __tablename__ = "score_deduction"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("student_profile.id"), nullable=False, index=True)
    assessment_year = Column(String(10), nullable=False, index=True)
    rule_id = Column(Integer, ForeignKey("score_rule.id"), default=None)
    rule_snapshot = Column(Text, default="")
    scope = Column(String(30), default="综合测评总分")
    deduction_score = Column(Float, nullable=False)
    reason = Column(Text, nullable=False)
    evidence_ref = Column(String(500), default="")
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(Integer, ForeignKey("user.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    deleted_by = Column(Integer, ForeignKey("user.id"), default=None)
    deleted_at = Column(DateTime, default=None)


class ScoreFinalization(Base):
    __tablename__ = "score_finalization"
    __table_args__ = (UniqueConstraint("student_id", "assessment_year", name="uq_score_finalization_student_year"),)
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("student_profile.id"), nullable=False, index=True)
    assessment_year = Column(String(10), nullable=False, index=True)
    is_finalized = Column(Boolean, default=True, nullable=False)
    snapshot_json = Column(Text, nullable=False, default="{}")
    finalized_by = Column(Integer, ForeignKey("user.id"), nullable=False)
    finalized_at = Column(DateTime, default=datetime.now)
    reopened_by = Column(Integer, ForeignKey("user.id"), default=None)
    reopened_at = Column(DateTime, default=None)
    reopen_reason = Column(Text, default="")


class OperationLog(Base):
    __tablename__ = "operation_log"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    actor_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("student_profile.id"), default=None, index=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, default=None)
    action = Column(String(100), nullable=False)
    detail = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now, index=True)


class SubmissionBatch(Base):
    __tablename__ = "submission_batch"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("student_profile.id"), nullable=False, index=True)
    assessment_year = Column(String(10), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="parsed")
    version = Column(Integer, nullable=False, default=1)
    excel_name = Column(String(255), nullable=False)
    excel_path = Column(String(500), nullable=False)
    item_count = Column(Integer, nullable=False, default=0)
    valid_count = Column(Integer, nullable=False, default=0)
    error_count = Column(Integer, nullable=False, default=0)
    confirmed_at = Column(DateTime, default=None)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class SubmissionBatchItem(Base):
    __tablename__ = "submission_batch_item"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("submission_batch.id"), nullable=False, index=True)
    row_number = Column(Integer, nullable=False)
    rule_id = Column(Integer, ForeignKey("score_rule.id"), default=None)
    project_name = Column(String(200), nullable=False, default="")
    project_level = Column(String(50), default="")
    role_rank = Column(String(100), default="")
    declared_score = Column(Float, default=0.0)
    project_date = Column(String(30), default="")
    description = Column(Text, default="")
    evidence_ref = Column(String(500), default="")
    status = Column(String(20), nullable=False, default="valid")
    error_message = Column(Text, default="")
    application_id = Column(Integer, ForeignKey("score_application.id"), default=None)
    created_at = Column(DateTime, default=datetime.now)


class SubmissionBatchMaterial(Base):
    __tablename__ = "submission_batch_material"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("submission_batch.id"), nullable=False, index=True)
    original_name = Column(String(255), nullable=False)
    stored_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False, default=0)
    file_type = Column(String(50), nullable=False, default="application/octet-stream")
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.now)


class AiAnalysisJob(Base):
    __tablename__ = "ai_analysis_job"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("submission_batch.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("student_profile.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    provider = Column(String(30), nullable=False, default="deepseek")
    model = Column(String(100), nullable=False, default="deepseek-chat")
    item_count = Column(Integer, nullable=False, default=0)
    completed_count = Column(Integer, nullable=False, default=0)
    error_message = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.now)
    started_at = Column(DateTime, default=None)
    completed_at = Column(DateTime, default=None)


class AiItemSuggestion(Base):
    __tablename__ = "ai_item_suggestion"
    __table_args__ = (
        UniqueConstraint("job_id", "batch_item_id", name="uq_ai_suggestion_job_item"),
    )
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("ai_analysis_job.id"), nullable=False, index=True)
    batch_item_id = Column(Integer, ForeignKey("submission_batch_item.id"), nullable=False, index=True)
    verification_status = Column(String(20), nullable=False, default="模糊")
    suggested_score = Column(Float, default=None)
    selected_rule_id = Column(Integer, ForeignKey("score_rule.id"), default=None)
    reason = Column(String(500), default="")
    evidence_summary = Column(Text, default="")
    response_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.now)


class ClassMeta(Base):
    __tablename__ = "class_meta"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    class_name = Column(String(50), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


class Announcement(Base):
    __tablename__ = "announcement"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    scope_type = Column(String(20), nullable=False, default="all")
    scope_value = Column(String(100), default="")
    description = Column(Text, default="")
    starts_at = Column(DateTime, nullable=False)
    ends_at = Column(DateTime, nullable=False)
    created_by = Column(Integer, ForeignKey("user.id"), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.now)


class ScoreObjection(Base):
    __tablename__ = "score_objection"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    announcement_id = Column(Integer, ForeignKey("announcement.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("student_profile.id"), nullable=False, index=True)
    score_item = Column(String(100), nullable=False, default="综合测评总分")
    objection_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    resolution = Column(Text, default="")
    handled_by = Column(Integer, ForeignKey("user.id"), default=None)
    handled_at = Column(DateTime, default=None)
    created_at = Column(DateTime, default=datetime.now)


class ApplicationAiAnalysis(Base):
    __tablename__ = "application_ai_analysis"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("score_application.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("student_profile.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    provider = Column(String(30), nullable=False, default="deepseek")
    model = Column(String(100), nullable=False, default="deepseek-chat")
    verification_status = Column(String(20), default="模糊")
    suggested_score = Column(Float, default=None)
    selected_rule_id = Column(Integer, ForeignKey("score_rule.id"), default=None)
    reason = Column(String(500), default="")
    evidence_summary = Column(Text, default="")
    error_message = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.now)
    started_at = Column(DateTime, default=None)
    completed_at = Column(DateTime, default=None)


Base.metadata.create_all(bind=engine)


def migrate_user_security_columns():
    """为已有 SQLite 演示库补充登录安全字段，避免要求用户删库。"""
    if not SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
        return
    existing = {column["name"] for column in inspect(engine).get_columns("user")}
    additions = {
        "is_active": "BOOLEAN NOT NULL DEFAULT 1",
        "failed_login_count": "INTEGER NOT NULL DEFAULT 0",
        "locked_until": "DATETIME",
        "last_login_at": "DATETIME",
    }
    with engine.begin() as connection:
        for name, ddl in additions.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE user ADD COLUMN {name} {ddl}"))


migrate_user_security_columns()


def migrate_extended_columns():
    """Keep existing SQLite demo databases compatible with newly added optional fields."""
    if not SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
        return
    additions = {
        "evidence_file": {"content_hash": "VARCHAR(64) DEFAULT ''"},
        "score_result": {"grade_rank": "INTEGER"},
    }
    with engine.begin() as connection:
        for table_name, columns in additions.items():
            existing = {column["name"] for column in inspect(engine).get_columns(table_name)}
            for name, ddl in columns.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {name} {ddl}"))


migrate_extended_columns()


def backfill_evidence_hashes():
    """Populate fingerprints for legacy files so duplicate detection also covers existing data."""
    db = SessionLocal()
    try:
        changed = False
        for evidence in db.query(EvidenceFile).filter(
            (EvidenceFile.content_hash == "") | (EvidenceFile.content_hash.is_(None))
        ).all():
            if not evidence.file_path or not os.path.isfile(evidence.file_path):
                continue
            digest = hashlib.sha256()
            with open(evidence.file_path, "rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            evidence.content_hash = digest.hexdigest()
            changed = True
        if changed:
            db.commit()
    finally:
        db.close()


backfill_evidence_hashes()


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class ApiResponse:
    @staticmethod
    def success(data=None, message="操作成功"):
        return {"code": 200, "message": message, "data": data}

    @staticmethod
    def error(code=400, message="操作失败", data=None):
        return {"code": code, "message": message, "data": data}


def verify_password(plain_password, hashed_password):
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password


def get_password_hash(password):
    try:
        return pwd_context.hash(password)
    except Exception:
        return hashlib.sha256(password.encode()).hexdigest()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


from fastapi.security import OAuth2PasswordBearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/oauth/token", auto_error=False)


async def get_current_user(token: Optional[str] = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或登录已过期")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    except JWTError:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已停用，请联系管理员")
    return user


def require_role(*roles):
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="无操作权限")
        return current_user
    return role_checker


def get_student_for_user(db: Session, user: User) -> Optional[StudentProfile]:
    return db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()


def can_access_application(user: User, application: ScoreApplication, db: Session) -> bool:
    """统一判断申请详情、材料和审核记录的访问范围。"""
    if user.role == ROLE_ADMIN:
        return True
    if user.role == ROLE_STUDENT:
        student = get_student_for_user(db, user)
        return bool(student and application.student_id == student.id)
    if user.role == ROLE_TEACHER:
        return bool(
            user.managed_class
            and application.student
            and application.student.class_name == user.managed_class
        )
    return False


