"""namemask: 完全ローカルの機密テキスト・マスキング/復元ツール。"""

__version__ = "0.1.0"

from namemask.types import (
    ALL_TYPES,
    Entity,
    EntityType,
    MaskResult,
    ReportItem,
    RestoreResult,
    Span,
)

__all__ = [
    "ALL_TYPES",
    "Entity",
    "EntityType",
    "MaskResult",
    "ReportItem",
    "RestoreResult",
    "Span",
]
