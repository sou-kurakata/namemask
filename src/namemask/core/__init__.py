"""可逆性: 置換・復元・mapping。"""

from namemask.core.mapping import MappingStore
from namemask.core.replacer import mask
from namemask.core.restorer import unmask

__all__ = ["MappingStore", "mask", "unmask"]
