def calculate_price_per_sqm(
    price: float | None,
    area: float | None,
) -> float | None:
    if price is None or area is None or area <= 0:
        return None

    return round(price / area, 2)