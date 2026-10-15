"""Public showcase content is intentionally read-only and never user-owned media."""
from __future__ import annotations

from pathlib import Path

from app.afiliados.plans import PLANS


def public_demo_videos(root: Path, limit: int = 6) -> list[Path]:
    """Only explicitly deployed demo MP4 files, never private media libraries."""
    root = Path(root)
    if not 1 <= limit <= 12:
        raise ValueError("Limite de demonstrações inválido")
    demo_dir = root / "assets" / "afiliados" / "demos"
    if not demo_dir.is_dir() or demo_dir.is_symlink():
        return []
    return [p for p in sorted(demo_dir.iterdir())
            if p.is_file() and not p.is_symlink() and p.suffix.lower() == ".mp4"
            and 0 < p.stat().st_size <= 100 * 1024 * 1024][:limit]


def public_plan_comparison() -> dict[str, list]:
    plans = [PLANS[name] for name in ("gratis", "pro", "creator")]
    return {
        "Plano": ["Grátis", "Pro", "Creator"],
        "Vídeos por dia": [str(p.daily_video_limit) if p.daily_video_limit is not None else "Ilimitados (uso justo)" for p in plans],
        "Vídeos por anúncio": [p.videos_per_ad for p in plans],
        "Capas por anúncio": [p.thumbnails_per_ad for p in plans],
        "Salvar projetos": ["Sim" if p.project_saving_allowed else "Não" for p in plans],
        "Publicidade": ["Sim", "Não", "Não"],
    }
