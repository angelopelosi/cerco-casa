from dataclasses import dataclass
from typing import Optional
import hashlib

TIPI_VALIDI = ("affitto", "vendita", "asta")

@dataclass
class Listing:
    fonte: str
    external_id: str
    tipo: str
    titolo: str
    prezzo: int
    url: str
    categoria: str = "residenziale"
    superficie_mq: Optional[int] = None
    locali: Optional[int] = None
    comune: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    stato_disponibilita: Optional[str] = None
    data_disponibilita: Optional[str] = None
    arredato: str = "non_specificato"
    data_pubblicazione: Optional[str] = None
    tribunale: Optional[str] = None
    data_asta: Optional[str] = None
    offerta_minima: Optional[int] = None
    chi_vende: Optional[str] = None

    @property
    def id(self) -> str:
        raw = f"{self.fonte}:{self.external_id}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def validate(self) -> None:
        if self.tipo not in TIPI_VALIDI:
            raise ValueError(f"tipo non valido: {self.tipo}")
        if not self.fonte or not self.external_id:
            raise ValueError("fonte e external_id sono obbligatori")
        if not self.url:
            raise ValueError("url obbligatorio")
        if self.prezzo is not None and self.prezzo < 0:
            raise ValueError("prezzo non puo essere negativo")
        if self.chi_vende is not None and self.chi_vende not in ("privato", "agenzia"):
            raise ValueError(f"chi_vende non valido: {self.chi_vende}")
