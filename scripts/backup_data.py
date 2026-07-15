import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    path = ROOT / ".env"
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> int:
    env = load_env()
    database_url = os.environ.get("ZONGCE_DATABASE_URL") or env.get("ZONGCE_DATABASE_URL", "")
    db_path = ROOT / "zongce.db"
    if database_url.startswith("sqlite:///"):
        db_path = Path(database_url.removeprefix("sqlite:///"))
    if not db_path.is_file():
        print(f"[失败] 找不到SQLite数据库：{db_path}")
        return 1
    upload_dir = Path(os.environ.get("ZONGCE_UPLOAD_DIR") or env.get("ZONGCE_UPLOAD_DIR") or ROOT / "uploads")
    backup_dir = ROOT / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot = backup_dir / f".zongce_{timestamp}.db"
    archive = backup_dir / f"zongce_backup_{timestamp}.zip"
    referenced_files: list[tuple[Path, Path]] = []
    try:
        with closing(sqlite3.connect(db_path)) as source, closing(sqlite3.connect(snapshot)) as target:
            source.backup(target)
            target.commit()
            tables = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "evidence_file" in tables:
                for file_id, file_path, file_name in source.execute("SELECT id, file_path, file_name FROM evidence_file"):
                    if file_path:
                        referenced_files.append((Path(file_path), Path("evidence") / f"application_file_{file_id}_{Path(file_name or file_path).name}"))
            if "submission_batch_material" in tables:
                for file_id, file_path, file_name in source.execute("SELECT id, stored_path, original_name FROM submission_batch_material WHERE is_active = 1"):
                    if file_path:
                        referenced_files.append((Path(file_path), Path("batch_materials") / f"batch_file_{file_id}_{Path(file_name or file_path).name}"))
        with ZipFile(archive, "w", compression=ZIP_DEFLATED, compresslevel=6) as output:
            output.write(snapshot, "database/zongce.db")
            archived_paths: set[Path] = set()
            for path, archive_name in referenced_files:
                if path.is_file():
                    resolved = path.resolve()
                    if resolved not in archived_paths:
                        output.write(path, archive_name)
                        archived_paths.add(resolved)
            if upload_dir.is_dir():
                for path in upload_dir.rglob("*"):
                    if path.is_file() and path.resolve() not in archived_paths:
                        output.write(path, Path("uploads") / path.relative_to(upload_dir))
            if (ROOT / ".env.example").is_file():
                output.write(ROOT / ".env.example", "config/.env.example")
        print(f"[完成] 备份已生成：{archive}")
        print(f"[信息] 已纳入数据库及{len(referenced_files)}条材料引用（不存在的历史文件会跳过）")
        print("[提醒] 备份可能包含学生证明材料和个人信息，请勿上传到公开仓库或群聊")
        return 0
    finally:
        snapshot.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
