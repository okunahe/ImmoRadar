import re
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.kleinanzeigen.de"


@dataclass
class Listing:
    title: str
    price: float | None
    area: float | None
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

    response = requests.get(
        url,
        headers=headers,
        timeout=15,
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    print("Status:", response.status_code)
    print("URL:", response.url)
    print("HTML-Länge:", len(response.text))
    print("article:", len(soup.select("article")))
    print("aditem:", len(soup.select(".aditem")))
    print("Links:", len(soup.select("a[href]")))

    anzeige_links = set()

    for link in soup.select("a[href]"):
        href = link.get("href")

        if isinstance(href, str) and "/s-anzeige/" in href:
            anzeige_links.add(href)

    print("Einzigartige Anzeigen:", len(anzeige_links))

    for href in anzeige_links:
        print("ANZEIGE:", href)

    # TEST: Erste Anzeige öffnen
    if anzeige_links:
        test_href = sorted(anzeige_links)[0]
        test_url = urljoin(BASE_URL, test_href)

        print("\n--- TEST EINZELANZEIGE ---")
        print("URL:", test_url)

        detail_response = requests.get(
            test_url,
            headers=headers,
            timeout=15,
        )

        print("Status:", detail_response.status_code)

        detail_response.raise_for_status()

        detail_soup = BeautifulSoup(
            detail_response.text,
            "html.parser",
        )

        print(
            "Titel:",
            detail_soup.title.get_text(" ", strip=True)
            if detail_soup.title
            else "Kein Titel",
        )

        print(
            "H1:",
            detail_soup.select_one("h1").get_text(" ", strip=True)
            if detail_soup.select_one("h1")
            else "Kein H1",
        )

        price_meta = detail_soup.select_one(
            'meta[itemprop="price"]'
        )

        if price_meta:
            price_content = price_meta.get("content")

            if isinstance(price_content, str):
                price = float(price_content)
                print("Kaufpreis:", price)
            else:
                print("Kaufpreis: nicht gefunden")
        else:
            print("Kaufpreis: nicht gefunden")

    area = None

    for detail in detail_soup.select("li.addetailslist--detail"):
        text = detail.get_text(" ", strip=True)

        if "Wohnfläche" in text:
            area_match = re.search(
                r"(\d+(?:[.,]\d+)?)\s*m²",
                text,
            )

            if area_match:
                area = float(
                    area_match.group(1).replace(",", ".")
                )
                break

    print("Wohnfläche:", area)

    if price is not None and area is not None:
        price_per_sqm = round(price / area, 2)
        print("Preis pro m²:", price_per_sqm)

    listings = []

    for href in sorted(anzeige_links)[:max_results]:
        listing_url = urljoin(BASE_URL, href)

        print("\n--------------------")
        print("Lade:", listing_url)

        detail_response = requests.get(
            listing_url,
            headers=headers,
            timeout=15,
        )

        if detail_response.status_code != 200:
            print("Übersprungen, Status:", detail_response.status_code)
            continue

        detail_soup = BeautifulSoup(
            detail_response.text,
            "html.parser",
        )

        # Titel
        h1 = detail_soup.select_one("h1")

        if h1 is None:
            print("Kein Titel gefunden")
            continue

        title = h1.get_text(" ", strip=True)

        # Kaufpreis
        price = None

        price_meta = detail_soup.select_one(
            'meta[itemprop="price"]'
        )

        if price_meta:
            price_content = price_meta.get("content")

            if isinstance(price_content, str):
                try:
                    price = float(price_content)
                except ValueError:
                    pass

        # Wohnfläche
        area = None

        for detail in detail_soup.select(
                "li.addetailslist--detail"
        ):
            text = detail.get_text(" ", strip=True)

            if "Wohnfläche" in text:
                area_match = re.search(
                    r"(\d+(?:[.,]\d+)?)\s*m²",
                    text,
                )

                if area_match:
                    area = float(
                        area_match.group(1).replace(",", ".")
                    )
                break

        # Ort
        location = ""

        location_element = detail_soup.select_one(
            '[itemprop="addressLocality"]'
        )

        if location_element:
            location = location_element.get_text(
                " ",
                strip=True,
            )

        print("Ort:", location)

        # €/m²
        price_per_sqm = calculate_price_per_sqm(
            price,
            area,
        )
#TODO: Zimmer and Hausgeld Info
#TODO: Telegram Eingabe einbinden
#TODO: Test mit andere Postleitzahl


        print("Titel:", title)
        print("Kaufpreis:", price)
        print("Wohnfläche:", area)
        print("Preis pro m²:", price_per_sqm)
        print("URL:", listing_url)

        listings.append(
            Listing(
                title=title,
                price=price,
                area=area,
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
    )

    print(f"\n{len(results)} Immobilien gefunden\n")

    for listing in results:
        print("--------------------")
        print("Titel:", listing.title)
        print("Preis:", listing.price)
        print("Fläche:", listing.area)
        print("€/m²:", listing.price_per_sqm)
        print("Ort:", listing.location)
        print("URL:", listing.url)