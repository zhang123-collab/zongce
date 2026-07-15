import re
from typing import Iterable


MAX_REDACTED_CHARS = 50_000
MAX_EVIDENCE_CHARS = 1_600


SENSITIVE_PATTERNS = {
    "邮箱": re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),
    "手机号": re.compile(r"(?<!\d)(?:\+?86[-\s.]*)?1[3-9](?:[-\s.]*\d){9}(?!\d)"),
    "Windows路径": re.compile(r"(?i)(?<![A-Z0-9])[A-Z]:\\[^\r\n<>|\"，,；;。]+"),
    "Unix路径": re.compile(r"(?<!\w)/(?:home|users?|tmp|var|opt)/[^\s<>\"]+"),
}
LONG_DIGIT_PATTERN = re.compile(r"(?<!\d)(?:\d[\s_.-]*){8,}(?!\d)")
DATE_PATTERN = re.compile(r"\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}(?:日)?")


def redact_text(
    text: str,
    student_name: str = "",
    student_id: str = "",
    filenames: Iterable[str] = (),
    max_chars: int = MAX_REDACTED_CHARS,
) -> str:
    """删除送入外部模型前可识别个人身份的信息。"""
    value = str(text or "")
    for filename in sorted({str(name) for name in filenames if name}, key=len, reverse=True):
        value = value.replace(filename, "[材料文件]")
    if student_name:
        value = value.replace(student_name, "[姓名]")
        if len(student_name) in (3, 4) and re.fullmatch(r"[\u4e00-\u9fff]+", student_name):
            value = re.sub(r"[\u4e00-\u9fff]" + re.escape(student_name[1:]), "[姓名]", value)
    if student_id:
        value = value.replace(student_id, "[学号]")

    # 联系方式必须先替换，避免其中的长数字和后续中文字段标签被误识别为名单项。
    value = SENSITIVE_PATTERNS["邮箱"].sub("[邮箱]", value)
    value = SENSITIVE_PATTERNS["手机号"].sub("[手机号]", value)

    # 名单常见格式为“姓名 + 学号/证件号”。必须同时保护材料中的其他学生，
    # 不能只删除当前登录人的姓名。
    value = re.sub(
        r"([\u4e00-\u9fff·]{2,6})\s*[,，:：]?\s*(?=(?:\d[\s_.-]*){8,})",
        "[姓名] ",
        value,
    )
    value = re.sub(
        r"((?:\d[\s_.-]*){8,})\s*[,，:：]?\s*([\u4e00-\u9fff·]{2,4})(?=\s*[,，;；\n]|$)",
        r"\1 [姓名]",
        value,
    )
    value = re.sub(
        r"((?:学生)?姓名|负责人|联系人|获奖人|成员)\s*[:：]\s*[\u4e00-\u9fff·]{2,8}",
        r"\1：[姓名]",
        value,
    )
    value = SENSITIVE_PATTERNS["Windows路径"].sub("[本地路径]", value)
    value = SENSITIVE_PATTERNS["Unix路径"].sub("[本地路径]", value)

    def mask_long_digits(match: re.Match) -> str:
        raw = match.group(0)
        if DATE_PATTERN.fullmatch(raw.strip()):
            return raw
        return "[长数字]" if len(re.sub(r"\D", "", raw)) >= 8 else raw

    value = LONG_DIGIT_PATTERN.sub(mask_long_digits, value)
    return value[:max(0, max_chars)]


def privacy_issues(text: str, forbidden_values: Iterable[str] = ()) -> list[str]:
    """发送外部模型前的最后一道阻断检查；只返回问题类别，不返回敏感原文。"""
    value = str(text or "")
    issues = [name for name, pattern in SENSITIVE_PATTERNS.items() if pattern.search(value)]
    if any(not DATE_PATTERN.fullmatch(match.group(0).strip()) for match in LONG_DIGIT_PATTERN.finditer(value)):
        issues.append("长数字")
    if any(secret and str(secret) in value for secret in forbidden_values):
        issues.append("已知身份字段")
    return list(dict.fromkeys(issues))


def ensure_private(text: str, forbidden_values: Iterable[str] = ()) -> None:
    issues = privacy_issues(text, forbidden_values)
    if issues:
        raise ValueError("脱敏安全检查未通过：" + "、".join(issues))


def evidence_snippet(text: str, terms: Iterable[str], max_chars: int = MAX_EVIDENCE_CHARS) -> str:
    """从已脱敏文本中截取与申报项目最相关的少量上下文。"""
    text = (text or "").strip()
    if not text:
        return ""
    snippets = []
    lowered = text.lower()
    seen = set()
    for raw_term in terms:
        term = str(raw_term or "").strip().lower()
        if len(term) < 2:
            continue
        start = 0
        while len("\n…\n".join(snippets)) < max_chars:
            index = lowered.find(term, start)
            if index < 0:
                break
            piece = text[max(0, index - 100):min(len(text), index + len(term) + 300)].strip()
            key = re.sub(r"\s+", "", piece[:100]).lower()
            if piece and key not in seen:
                snippets.append(piece)
                seen.add(key)
            start = index + len(term)
    result = "\n…\n".join(snippets) if snippets else text[:max_chars]
    return result[:max_chars]
