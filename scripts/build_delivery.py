from __future__ import annotations

import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT.parent / "交付包"
PACKAGE_NAME = "本科生综测计分系统"

FILES = (
    "app.py",
    "requirements.txt",
    "requirements-ai.txt",
    ".env.example",
    ".gitignore",
    ".dockerignore",
    "Dockerfile",
    "docker-compose.yml",
    "README.md",
    "项目说明.md",
    "安装依赖.bat",
    "启动系统.bat",
    "备份数据.bat",
    "Docker启动.bat",
    "Docker停止.bat",
)

DIRECTORIES = ("zongce", "static", "tests", "scripts", "deploy")
SKIP_PARTS = {"__pycache__", ".pytest_cache"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".zip", ".db"}


def should_include(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    return not any(part in SKIP_PARTS for part in relative.parts) and path.suffix.lower() not in SKIP_SUFFIXES


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def build_delivery() -> Path:
    missing = [name for name in FILES if not (ROOT / name).is_file()]
    missing += [name for name in DIRECTORIES if not (ROOT / name).is_dir()]
    if missing:
        raise FileNotFoundError("交付所需文件缺失：" + "、".join(missing))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    staging = OUTPUT_DIR / PACKAGE_NAME
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()

    for name in FILES:
        copy_file(ROOT / name, staging / name)

    for directory in DIRECTORIES:
        for source in (ROOT / directory).rglob("*"):
            if source.is_file() and should_include(source):
                copy_file(source, staging / source.relative_to(ROOT))

    for empty_dir in ("uploads", "backups"):
        target = staging / empty_dir
        target.mkdir()
        (target / ".gitkeep").write_text("", encoding="utf-8")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = OUTPUT_DIR / f"{PACKAGE_NAME}_{stamp}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in sorted(staging.rglob("*")):
            if source.is_file():
                archive.write(source, Path(PACKAGE_NAME) / source.relative_to(staging))

    with zipfile.ZipFile(zip_path) as archive:
        bad_file = archive.testzip()
        if bad_file:
            raise RuntimeError(f"压缩包校验失败：{bad_file}")
        names = set(archive.namelist())
        forbidden = ("/.env", "/.zongce_secret", "/zongce.db")
        if any(any(item.endswith(marker) for marker in forbidden) for item in names):
            raise RuntimeError("压缩包包含禁止交付的敏感文件")

    shutil.rmtree(staging)
    return zip_path


if __name__ == "__main__":
    try:
        result = build_delivery()
    except Exception as exc:
        print(f"交付包生成失败：{exc}", file=sys.stderr)
        raise SystemExit(1)
    print(result)
