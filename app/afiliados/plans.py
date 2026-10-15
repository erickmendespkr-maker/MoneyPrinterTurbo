"""Affiliate plan entitlements. Storage, authentication and billing are separate concerns."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PlanPolicy:
    name: str
    daily_video_limit: int | None
    platform_watermark_required: bool
    custom_watermark_allowed: bool
    videos_per_ad: int
    thumbnails_per_ad: int
    project_saving_allowed: bool


PLANS = {
    "gratis": PlanPolicy("gratis", 1, True, False, 1, 0, False),
    "pro": PlanPolicy("pro", 5, True, False, 1, 0, True),
    "creator": PlanPolicy("creator", None, False, True, 3, 9, True),
}


def get_plan_policy(plan: str) -> PlanPolicy:
    if not isinstance(plan, str) or plan not in PLANS:
        raise ValueError("Plano inválido")
    return PLANS[plan]


def can_generate(plan: str, videos_completed_today: int) -> bool:
    """Pure policy check; caller must count usage atomically in persistent storage."""
    policy = get_plan_policy(plan)
    if type(videos_completed_today) is not int or videos_completed_today < 0:
        raise ValueError("Contagem diária inválida")
    return policy.daily_video_limit is None or videos_completed_today < policy.daily_video_limit


def watermark_required(plan: str) -> bool:
    return get_plan_policy(plan).platform_watermark_required


def require_feature(plan: str, feature: str) -> None:
    """Fail closed before premium thumbnail or campaign generation."""
    policy = get_plan_policy(plan)
    if feature == "projects":
        allowed = policy.project_saving_allowed
    elif feature == "thumbnails":
        allowed = policy.thumbnails_per_ad > 0
    elif feature == "campaign":
        allowed = policy.videos_per_ad == 3
    else:
        raise ValueError("Recurso inválido")
    if not allowed:
        raise PermissionError("Recurso não disponível no plano atual")
