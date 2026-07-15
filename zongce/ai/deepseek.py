import json
import os
from pathlib import Path
import urllib.error
import urllib.request

from zongce.core import PROJECT_DIR


DEFAULT_API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-chat"


def load_local_env() -> None:
    """读取项目本机 .env；不覆盖启动进程显式传入的环境变量。"""
    env_path = Path(PROJECT_DIR) / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key.replace("_", "").isalnum():
            os.environ.setdefault(key, value)


def ai_config() -> dict:
    load_local_env()
    return {
        "enabled": os.environ.get("ZONGCE_AI_ENABLED", "1").strip().lower() not in {"0", "false", "off", "no"},
        "configured": bool(os.environ.get("DEEPSEEK_API_KEY", "").strip()),
        "api_url": os.environ.get("DEEPSEEK_API_URL", DEFAULT_API_URL).strip() or DEFAULT_API_URL,
        "model": os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
    }


def call_deepseek_batch(items: list[dict]) -> list[dict]:
    config = ai_config()
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not config["enabled"]:
        raise RuntimeError("AI辅助核验已关闭")
    if not api_key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY")
    system_prompt = (
        "你是本科生综合测评材料核验助手。输入内容已经脱敏。"
        "你只能根据候选规则和证据片段提出建议，不得推断真实身份，不得把建议描述为最终审核结论。"
        "对每个item_id输出verification_status（仅匹配、不匹配、模糊）、suggested_score（0到100或null）、"
        "selected_rule_id（只能使用该项candidate_rule.id或null）和简短reason。证据不足必须标记为模糊。"
        "只输出JSON对象，格式为{\"items\":[...]}。"
    )
    body = {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps({"items": items}, ensure_ascii=False)},
        ],
        "temperature": 0.0,
        "max_tokens": 3500,
        "stream": False,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        config["api_url"],
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            outer = json.loads(response.read().decode("utf-8"))
        content = outer["choices"][0]["message"]["content"]
        payload = json.loads(content)
        if not isinstance(payload.get("items"), list):
            raise ValueError("响应缺少items数组")
        return payload["items"]
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"DeepSeek服务返回HTTP {exc.code}") from None
    except urllib.error.URLError:
        raise RuntimeError("无法连接DeepSeek服务") from None
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise RuntimeError("DeepSeek返回内容格式不正确") from None

