import importlib.util
import os
import socket
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    path = ROOT / ".env"
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> int:
    failures: list[str] = []
    warnings: list[str] = []
    print(f"[环境检查] 项目目录：{ROOT}")
    print(f"[通过] Python {sys.version.split()[0]}")
    if sys.version_info < (3, 10):
        failures.append("需要 Python 3.10 或更高版本")

    required = ("fastapi", "uvicorn", "sqlalchemy", "jose", "passlib", "multipart", "openpyxl", "pypdf", "reportlab")
    missing = [name for name in required if importlib.util.find_spec(name) is None]
    if missing:
        failures.append("缺少依赖：" + ", ".join(missing))
    else:
        print("[通过] 运行依赖完整")

    env = load_env()
    secret = os.environ.get("ZONGCE_SECRET_KEY") or env.get("ZONGCE_SECRET_KEY", "")
    local_secret = ROOT / ".zongce_secret"
    if (len(secret) < 32 or secret == "replace-with-a-long-random-secret") and not local_secret.is_file():
        warnings.append("首次启动时将自动生成本机应用签名密钥")
    elif local_secret.is_file() and not secret:
        print("[通过] 本机应用签名密钥已自动生成")
    else:
        print("[通过] 应用签名密钥已配置")
    ai_key = os.environ.get("DEEPSEEK_API_KEY") or env.get("DEEPSEEK_API_KEY", "")
    print(f"[信息] DeepSeek：{'已配置' if ai_key else '未配置（AI入口不可用，其他功能不受影响）'}")

    upload_dir = Path(os.environ.get("ZONGCE_UPLOAD_DIR") or env.get("ZONGCE_UPLOAD_DIR") or ROOT / "uploads")
    try:
        upload_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=upload_dir, prefix=".write-check-", delete=True):
            pass
        print(f"[通过] 上传目录可写：{upload_dir}")
    except OSError as exc:
        failures.append(f"上传目录不可写：{exc}")

    database_url = os.environ.get("ZONGCE_DATABASE_URL") or env.get("ZONGCE_DATABASE_URL", "")
    db_path = ROOT / "zongce.db"
    if database_url.startswith("sqlite:///"):
        db_path = Path(database_url.removeprefix("sqlite:///"))
    if db_path.is_file():
        try:
            with sqlite3.connect(db_path) as connection:
                result = connection.execute("PRAGMA quick_check").fetchone()[0]
            if result != "ok":
                failures.append(f"数据库完整性检查失败：{result}")
            else:
                print(f"[通过] SQLite数据库完整：{db_path}")
        except sqlite3.Error as exc:
            failures.append(f"数据库无法读取：{exc}")
    else:
        print("[信息] 数据库尚未生成，首次启动时会自动创建")

    try:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 8000))
        print("[通过] 端口8000可用")
    except OSError:
        failures.append("端口8000已被占用，请先关闭旧服务")

    for warning in warnings:
        print(f"[警告] {warning}")
    for failure in failures:
        print(f"[失败] {failure}")
    if failures:
        print(f"[结果] 环境检查未通过，共{len(failures)}项问题")
        return 1
    print("[结果] 环境检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
