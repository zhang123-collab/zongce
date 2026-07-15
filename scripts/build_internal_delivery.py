from __future__ import annotations

import shutil
import sqlite3
import sys
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from build_delivery import DIRECTORIES, FILES, OUTPUT_DIR, ROOT, copy_file, should_include


PACKAGE_NAME = "本科生综测计分系统_组内完整部署"
INTERNAL_FILES = (
    "docker-compose.internal.yml",
    "Docker组内启动.bat",
    "Docker组内停止.bat",
    "组内部署说明.md",
    ".env",
    ".zongce_secret",
)


def resolve_stored_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def relative_to(path: Path, base: Path) -> Path | None:
    try:
        return path.resolve().relative_to(base.resolve())
    except (OSError, ValueError):
        return None


def copy_sensitive_data(staging: Path) -> tuple[int, int]:
    data_dir = staging / "internal-data"
    data_dir.mkdir(parents=True)
    db_target = data_dir / "zongce.db"

    source_db = sqlite3.connect(ROOT / "zongce.db")
    target_db = sqlite3.connect(db_target)
    try:
        source_db.backup(target_db)
    finally:
        source_db.close()
        target_db.close()

    upload_root = ROOT / "uploads"
    material_root = ROOT / "学生证明材料"
    if upload_root.is_dir():
        shutil.copytree(upload_root, data_dir / "uploads", dirs_exist_ok=True)
    else:
        (data_dir / "uploads").mkdir()
    if material_root.is_dir():
        shutil.copytree(material_root, data_dir / "student-materials", dirs_exist_ok=True)

    connection = sqlite3.connect(db_target)
    mapped = 0
    missing = 0

    def map_file(raw_path: str, category: str, record_id: int, display_name: str) -> str | None:
        nonlocal mapped, missing
        source = resolve_stored_path(raw_path)
        if not source.is_file():
            missing += 1
            return None
        upload_relative = relative_to(source, upload_root)
        material_relative = relative_to(source, material_root)
        if upload_relative is not None:
            target_relative = Path("uploads") / upload_relative
        elif material_relative is not None:
            target_relative = Path("student-materials") / material_relative
        else:
            safe_name = Path(display_name or source.name).name
            target_relative = Path(category) / f"{record_id}_{safe_name}"
            copy_file(source, data_dir / target_relative)
        mapped += 1
        return "/app/internal-data/" + PurePosixPath(target_relative).as_posix()

    try:
        evidence_rows = connection.execute(
            "SELECT id, file_path, file_name FROM evidence_file"
        ).fetchall()
        for record_id, raw_path, display_name in evidence_rows:
            mapped_path = map_file(raw_path, "evidence", record_id, display_name)
            if mapped_path:
                connection.execute(
                    "UPDATE evidence_file SET file_path = ? WHERE id = ?",
                    (mapped_path, record_id),
                )

        batch_rows = connection.execute(
            "SELECT id, stored_path, original_name FROM submission_batch_material"
        ).fetchall()
        for record_id, raw_path, display_name in batch_rows:
            mapped_path = map_file(raw_path, "batch-materials", record_id, display_name)
            if mapped_path:
                connection.execute(
                    "UPDATE submission_batch_material SET stored_path = ? WHERE id = ?",
                    (mapped_path, record_id),
                )
        connection.commit()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"数据库副本完整性检查失败：{integrity}")
    finally:
        connection.close()
    return mapped, missing


def build_internal_delivery() -> tuple[Path, int, int]:
    required = [*FILES, *INTERNAL_FILES, "zongce.db"]
    missing_required = [name for name in required if not (ROOT / name).is_file()]
    if missing_required:
        raise FileNotFoundError("组内部署所需文件缺失：" + "、".join(missing_required))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    staging = OUTPUT_DIR / PACKAGE_NAME
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()

    for name in (*FILES, *INTERNAL_FILES):
        copy_file(ROOT / name, staging / name)
    for directory in DIRECTORIES:
        for source in (ROOT / directory).rglob("*"):
            if source.is_file() and should_include(source):
                copy_file(source, staging / source.relative_to(ROOT))

    mapped, missing = copy_sensitive_data(staging)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = OUTPUT_DIR / f"{PACKAGE_NAME}_{stamp}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for source in sorted(staging.rglob("*")):
            if source.is_file():
                archive.write(source, Path(PACKAGE_NAME) / source.relative_to(staging))

    with zipfile.ZipFile(zip_path) as archive:
        bad_file = archive.testzip()
        if bad_file:
            raise RuntimeError(f"压缩包校验失败：{bad_file}")
        names = set(archive.namelist())
        required_suffixes = (
            "/.env",
            "/.zongce_secret",
            "/internal-data/zongce.db",
            "/组内部署说明.md",
        )
        absent = [suffix for suffix in required_suffixes if not any(name.endswith(suffix) for name in names)]
        if absent:
            raise RuntimeError("组内敏感文件未完整打包：" + "、".join(absent))

    shutil.rmtree(staging)
    return zip_path, mapped, missing


if __name__ == "__main__":
    try:
        result, mapped_count, missing_count = build_internal_delivery()
    except Exception as exc:
        print(f"组内完整部署包生成失败：{exc}", file=sys.stderr)
        raise SystemExit(1)
    print(result)
    print(f"材料路径已转换：{mapped_count}，缺失引用：{missing_count}")
