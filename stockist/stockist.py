from dataclasses import dataclass, field

from typing import Final
from io import StringIO

STOCK_UNLIMITED: Final[int] = -1

@dataclass
class Product:
    sku: dict[str, str] = field(default_factory=dict)
    enabled: dict[str, bool] = field(default_factory=dict)

    name: dict[str, str] = field(default_factory=dict)
    categories: dict[str, set[str]] = field(default_factory=dict)
    default_category: dict[str, str] = field(default_factory=dict)

    price: float = None
    msrp: float = None
    cost: float = None

    quantity: int = 0

    weight: float = None
    length: float = None
    width: float = None
    height: float = None

    # shipping methods

    def __str__(self):
        s = StringIO()
        sku = ', '.join([f"{k}:{v}" for k,v in self.sku.items()])
        s.write(f"[{sku}] ")
        s.write(f"{self.name} " if self.name else " ")
        s.write('(')
        s.write(f"${self.price if self.price else '--'} : ")
        s.write(f"${self.msrp if self.msrp else '--'} : ")
        s.write(f"${self.cost if self.cost else '--'}")
        s.write(')')
        return s.getvalue()
