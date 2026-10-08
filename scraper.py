
import re
import time
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


BASE_URL = "https://www.kleinanzeigen.de"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    )
}


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


def find_location_id(
    postcode: str,
    headers: dict,
) -> str:
    url = f"{BASE_URL}/s-ort-empfehlungen.json"

    response = requests.get(
        url,
        params={"query": postcode},
        headers=headers,
        timeout=15,
    )

    response.raise_for_status()
    locations = response.json()

    for location_id, location_name in locations.items():
        if location_id == "0":
            continue

        if (
            isinstance(location_name, str)
            and location_name.startswith(postcode)
        ):
            print(
                f"PLZ {postcode} → "
                f"{location_name} → l{location_id}"
            )
            return location_id.lstrip("_")

    raise ValueError(
        f"Keine passende Location-ID "
        f"für PLZ {postcode} gefunden."
    )


def search_listings(
    postcode: str,
    radius: int,
    max_results: int = 10,
) -> list[Listing]:

    if not re.fullmatch(r"\d{5}", postcode):
        raise ValueError("Die PLZ muss genau 5 Ziffern haben.")

    if radius <= 0:
        raise ValueError("Der Radius muss größer als 0 sein.")

    if max_results <= 0:
        return []

    location_id = find_location_id(
        postcode,
        HEADERS,
    )

    # Kategorie c196 = Eigentumswohnungen kaufen

    url = (
        f"{BASE_URL}/s-wohnung-kaufen/{postcode}/"
        f"c196l{location_id}r{radius}"
    )

    print("\nSuche:", url)
    print("URL exakt:", repr(url))
    # -----------------------------------
    # 1. Suchergebnisse mit Playwright
    # -----------------------------------

    anzeige_links = []
    bekannte_links = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=False,
        )

        try:
            page = browser.new_page(
                viewport={
                    "width": 1440,
                    "height": 900,
                }
            )

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000,
            )
            print("Seitentitel:", page.title())
            print(
                "Suchergebnisse-Überschrift:",
                page.locator("h1").first.inner_text()
            )
            print(
                "Erster Artikel:",
                page.locator(
                    "#srchrslt-results article[data-href]"
                ).first.inner_text()[:350]
            )

            print("Browser-URL:", page.url)

            try:
                page.wait_for_selector(
                    "#srchrslt-results article[data-href]",
                    timeout=15000,
                )
            except PlaywrightTimeoutError:
                print(
                    "Keine Anzeigen im Ergebnisbereich gefunden."
                )
                return []

            # Nur Artikel aus der eigentlichen Ergebnisliste
            cards = page.locator(
                "#srchrslt-results article[data-href]"
            )

            print(
                "Artikel im Ergebnisbereich:",
                cards.count(),
            )

            # Links in der Reihenfolge der Suchseite sammeln
            for i in range(cards.count()):
                article = cards.nth(i)

                href = article.get_attribute(
                    "data-href"
                )

                if not href:
                    continue

                if "/s-anzeige/" not in href:
                    continue

                listing_url = urljoin(
                    BASE_URL,
                    href,
                )

                if listing_url in bekannte_links:
                    continue

                bekannte_links.add(listing_url)
                anzeige_links.append(listing_url)

                print(
                    "Gefundener Link:",
                    listing_url,
                )

                if len(anzeige_links) >= max_results:
                    break

        finally:
            browser.close()

    print(
        "\nAnzeigen auf Suchseite:",
        len(anzeige_links),
    )

    print(
        "Davon werden verarbeitet:",
        min(len(anzeige_links), max_results),
    )

    # -----------------------------------
    # 2. Einzelne Anzeigen auslesen
    # -----------------------------------

    listings = []

    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        for listing_url in anzeige_links[:max_results]:

            print("\n--------------------")
            print("Lade:", listing_url)

            try:
                response = session.get(
                    listing_url,
                    timeout=15,
                )

                response.raise_for_status()

            except requests.RequestException as error:
                print(
                    "Anzeige konnte nicht geladen werden:",
                    error,
                )
                continue

            detail_soup = BeautifulSoup(
                response.text,
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
                        price = int(
                            float(price_content)
                        )
                    except ValueError:
                        price = None

            # --------------------
            # Wohnfläche, Zimmer, Hausgeld
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
                            area_match.group(1).replace(
                                ",", "."
                            )
                        )

                # Zimmer
                if text.startswith("Zimmer"):
                    rooms_match = re.search(
                        r"Zimmer\s+(\d+(?:[.,]\d+)?)",
                        text,
                    )

                    if rooms_match:
                        rooms = int(
                            float(
                                rooms_match.group(1).replace(
                                    ",", "."
                                )
                            )
                        )

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
            # Ausgabe
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

            # Kleine Pause zwischen Detailseiten
            time.sleep(1)

    finally:
        session.close()

    return listings


# -----------------------------------
# Test ohne Telegram
# -----------------------------------

if __name__ == "__main__":

    results = search_listings(
        postcode="80805",
        radius=5,
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
