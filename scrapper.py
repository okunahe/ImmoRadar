import re
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.kleinanzeigen.de"


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


def parse_number(text: str) -> float | None:
    if not text:
        return None

    match = re.search(r"[\d.,]+", text)

    if not match:
        return None

    value = match.group()
    value = value.replace(".", "").replace(",", ".")

    try:
        return float(value)
    except ValueError:
        return None


def calculate_price_per_sqm(
    price: float | None,
    area: float | None,
) -> float | None:
    if price is None or area is None or area <= 0:
        return None

    return round(price / area, 2)


def search_listings(
    postcode: str,
    radius: int,
    max_results: int = 10,
) -> list[Listing]:

    # Eigentumswohnungen
    # l349 ist momentan die getestete Kleinanzeigen-Location-ID
    # für unsere Suche rund um 66346.
    url = (
        f"{BASE_URL}/s-wohnung-kaufen/{postcode}/"
        f"c196l349r{radius}"
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/140.0 Safari/537.36"
        )
    }

    print("Suche:", url)

    response = requests.get(
        url,
        headers=headers,
        timeout=15,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    # Alle eindeutigen Anzeigen-Links sammeln
    anzeige_links = set()

    for link in soup.select("a[href]"):
        href = link.get("href")

        if (
            isinstance(href, str)
            and "/s-anzeige/" in href
        ):
            anzeige_links.add(href)

    print(
        "Einzigartige Anzeigen:",
        len(anzeige_links),
    )

    listings = []

    # Maximal max_results Anzeigen laden
    for href in sorted(anzeige_links)[:max_results]:
        listing_url = urljoin(
            BASE_URL,
            href,
        )

        print("\n--------------------")
        print("Lade:", listing_url)

        try:
            detail_response = requests.get(
                listing_url,
                headers=headers,
                timeout=15,
            )

            detail_response.raise_for_status()

        except requests.RequestException as error:
            print(
                "Anzeige konnte nicht geladen werden:",
                error,
            )
            continue

        detail_soup = BeautifulSoup(
            detail_response.text,
            "html.parser",
        )

        # --------------------
        # Titel
        # --------------------

        h1 = detail_soup.select_one("h1")

        if h1 is None:
            print("Kein Titel gefunden.")
            continue

        title = h1.get_text(
            " ",
            strip=True,
        )

        # --------------------
        # Kaufpreis
        # --------------------

        price = None

        price_meta = detail_soup.select_one(
            'meta[itemprop="price"]'
        )

        if price_meta:
            price_content = price_meta.get(
                "content"
            )

            if isinstance(price_content, str):
                try:
                    price = int(float(price_content))
                except ValueError:
                    price = None

        # --------------------
        # Wohnfläche
        # Zimmer
        # Hausgeld
        # --------------------

        area = None
        rooms = None
        house_fee = None

        details = detail_soup.select(
            "li.addetailslist--detail"
        )

        for detail in details:
            text = detail.get_text(
                " ",
                strip=True,
            )

            # Wohnfläche
            if "Wohnfläche" in text:
                area_match = re.search(
                    r"(\d+(?:[.,]\d+)?)\s*m²",
                    text,
                )

                if area_match:
                    area = float(
                        area_match
                        .group(1)
                        .replace(",", ".")
                    )

            # Zimmer
            if text.startswith("Zimmer"):
                rooms_match = re.search(
                    r"Zimmer\s+(\d+(?:[.,]\d+)?)",
                    text,
                )

                if rooms_match:
                    rooms = int(float(
                        rooms_match
                        .group(1)
                        .replace(",", ".")
                    ))

            # Hausgeld
            if text.startswith("Hausgeld"):
                house_fee_match = re.search(
                    r"Hausgeld\s+([\d.,]+)",
                    text,
                )

                if house_fee_match:
                    house_fee = parse_number(
                        house_fee_match.group(1)
                    )

        # --------------------
        # Ort
        # --------------------

        location = ""

        location_element = detail_soup.select_one(
            '[itemprop="addressLocality"]'
        )

        if location_element:
            location = location_element.get_text(
                " ",
                strip=True,
            )

        # --------------------
        # Preis pro m²
        # --------------------

        price_per_sqm = calculate_price_per_sqm(
            price,
            area,
        )

        # --------------------
        # Ergebnis anzeigen
        # --------------------

        print("Titel:", title)
        print("Kaufpreis:", price)
        print("Wohnfläche:", area)
        print("Zimmer:", rooms)
        print("Hausgeld:", house_fee)
        print("Preis pro m²:", price_per_sqm)
        print("Ort:", location)
        print("URL:", listing_url)

        # --------------------
        # Listing speichern
        # --------------------

        listings.append(
            Listing(
                title=title,
                price=price,
                area=area,
                rooms=rooms,
                house_fee=house_fee,
                price_per_sqm=price_per_sqm,
                location=location,
                url=listing_url,
            )
        )

    return listings


if __name__ == "__main__":

    results = search_listings(
        postcode="66346",
        radius=50,
        max_results=10,
    )

    print(
        f"\n{len(results)} Immobilien gefunden\n"
    )

    for listing in results:
        print("--------------------")
        print("Titel:", listing.title)
        print("Preis:", listing.price)
        print("Fläche:", listing.area)
        print("Zimmer:", listing.rooms)
        print("Hausgeld:", listing.house_fee)
        print("€/m²:", listing.price_per_sqm)
        print("Ort:", listing.location)
        print("URL:", listing.url)