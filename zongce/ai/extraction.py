from dataclasses import dataclass
from pathlib import Path
from typing import Any


PDF_MAX_PAGES = 20
RAW_TEXT_MAX_CHARS = 50_000


@dataclass
class ExtractionResult:
    text: str
    method: str
    warning: str = ""


def ocr_available() -> bool:
    try:
        import rapidocr_onnxruntime  # noqa: F401
        from PIL import Image  # noqa: F401
        return True
    except ImportError:
        return False


def _ocr_image(image: Any) -> str:
    from rapidocr_onnxruntime import RapidOCR

    result, _ = RapidOCR()(image)
    if not result:
        return ""
    return "\n".join(str(line[1]) for line in result if len(line) > 1)[:RAW_TEXT_MAX_CHARS]


def _extract_image(path: Path) -> ExtractionResult:
    if not ocr_available():
        return ExtractionResult("", "unavailable", "图片OCR组件未安装，需人工核验图片材料")
    from PIL import Image

    with Image.open(path) as image:
        return ExtractionResult(_ocr_image(image.convert("RGB")), "ocr")


def _ocr_pdf(path: Path) -> ExtractionResult:
    if not ocr_available():
        return ExtractionResult("", "unavailable", "扫描版PDF的OCR组件未安装，需人工核验")
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return ExtractionResult("", "unavailable", "PDF渲染组件未安装，扫描版PDF需人工核验")
    document = pdfium.PdfDocument(str(path))
    pages = []
    try:
        for page_number in range(min(len(document), PDF_MAX_PAGES)):
            bitmap = document[page_number].render(scale=1.5)
            pages.append(_ocr_image(bitmap.to_pil()))
            if sum(map(len, pages)) >= RAW_TEXT_MAX_CHARS:
                break
    finally:
        document.close()
    return ExtractionResult("\n".join(pages)[:RAW_TEXT_MAX_CHARS], "ocr")


def _extract_pdf(path: Path) -> ExtractionResult:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ExtractionResult("", "unavailable", "PDF文本提取组件未安装，需人工核验")
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            try:
                if not reader.decrypt(""):
                    return ExtractionResult("", "encrypted", "PDF已加密，需人工核验")
            except Exception:
                return ExtractionResult("", "encrypted", "PDF已加密，需人工核验")
        pages = []
        for page in reader.pages[:PDF_MAX_PAGES]:
            pages.append(page.extract_text() or "")
            if sum(map(len, pages)) >= RAW_TEXT_MAX_CHARS:
                break
        text = "\n".join(pages)[:RAW_TEXT_MAX_CHARS].strip()
        if text:
            return ExtractionResult(text, "pdf-text")
        return _ocr_pdf(path)
    except Exception:
        return ExtractionResult("", "failed", "PDF无法解析，需人工核验原文件")


def extract_material_text(path_value: str, file_type: str) -> ExtractionResult:
    path = Path(path_value)
    if not path.is_file():
        return ExtractionResult("", "missing", "材料文件不存在")
    file_type = (file_type or "").lower()
    if file_type == "application/pdf" or path.suffix.lower() == ".pdf":
        return _extract_pdf(path)
    if file_type.startswith("image/") or path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
        try:
            return _extract_image(path)
        except Exception:
            return ExtractionResult("", "failed", "图片无法识别，需人工核验原文件")
    return ExtractionResult("", "unsupported", "材料类型不支持自动提取")

