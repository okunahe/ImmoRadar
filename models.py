from dataclasses import dataclass


@dataclass
class Listing:
    title: str
    price: int | None
    area: float | None
    rooms: int | None
    house_fee: float | None
    price_per_sqm: float | None
    location: str
    url: str