"""Page rendering with a content-addressed image cache (shared by VLM, OCR and review)."""
from __future__ import annotations

from pathlib import Path

from .config import Config


def page_image_path(cfg: Config, sha256: str, page: int, dpi: int) -> Path:
    return cfg.work / "cache" / "pages" / sha256[:16] / f"p{page:04d}_{dpi}.png"


def render_pages(cfg: Config, pdf_path: str, sha256: str, pages: list[int], dpi: int) -> dict[int, Path]:
    """Render 1-based ``pages`` once; later calls are cache hits."""
    out: dict[int, Path] = {}
    todo = []
    for p in pages:
        path = page_image_path(cfg, sha256, p, dpi)
        out[p] = path
        if not path.exists():
            todo.append(p)
    if todo:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(pdf_path)
        try:
            for p in todo:
                page = pdf[p - 1]
                image = page.render(scale=dpi / 72.0, may_draw_forms=True).to_pil().convert("RGB")
                out[p].parent.mkdir(parents=True, exist_ok=True)
                tmp = out[p].with_suffix(".tmp.png")
                image.save(tmp, optimize=False, compress_level=1)
                tmp.replace(out[p])
                page.close()
        finally:
            pdf.close()
    return out


def image_source_path(cfg: Config, src: str, sha256: str) -> Path:
    """Normalise an image document (any format, EXIF rotation, CMYK) to RGB PNG once."""
    path = cfg.work / "cache" / "pages" / sha256[:16] / "p0001_src.png"
    if not path.exists():
        from PIL import Image, ImageOps
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            path.parent.mkdir(parents=True, exist_ok=True)
            im.save(path, compress_level=1)
    return path
