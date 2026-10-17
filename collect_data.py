"""
Сбор POI города Астана из OpenStreetMap (Overpass API).
Запуск: python collect_data.py
Результат: data/raw_poi.json + статистика по категориями в консоли.
"""
import json
import os
import time
from collections import Counter
from datetime import date

import requests

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# Прямоугольник вокруг Астаны: юг, запад, север, восток
BBOX = "50.98,71.25,51.28,71.70"

QUERY = f"""
[out:json][timeout:90];
(
  nwr["amenity"="cafe"]({BBOX});
  nwr["amenity"="restaurant"]({BBOX});
  nwr["amenity"="cinema"]({BBOX});
  nwr["tourism"~"museum|viewpoint|attraction|gallery|zoo|theme_park"]({BBOX});
  nwr["leisure"~"park|playground|garden"]({BBOX});
  nwr["historic"]({BBOX});
);
out center tags;
"""

def classify(tags: dict) -> str:
    if tags.get("amenity") == "cafe":
        return "cafe"
    if tags.get("amenity") == "restaurant":
        return "restaurant"
    if tags.get("amenity") == "cinema":
        return "cinema"
    t = tags.get("tourism")
    if t == "museum":
        return "museum"
    if t == "gallery":
        return "gallery"
    if t == "viewpoint":
        return "viewpoint"
    if t in ("attraction", "zoo", "theme_park"):
        return "attraction"
    l = tags.get("leisure")
    if l == "playground":
        return "playground"
    if l in ("park", "garden"):
        return "park"
    if "historic" in tags:
        return "historic"
    return "other"

def fetch() -> dict:
    last_err = None
    headers = {
        'User-Agent': 'AstanaWalkAssistant/1.0 (Student Hackathon Project)'
    }
    
    for url in OVERPASS_URLS:
        try:
            print(f"Запрос к {url} ...")
            r = requests.post(url, data={"data": QUERY}, headers=headers, timeout=120)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            print("Ошибка:", e, "- пробую следующий сервер")
            time.sleep(3)
    raise RuntimeError(f"Не удалось получить данные: {last_err}")

def to_record(el: dict):
    tags = el.get("tags", {})
    lat = el.get("lat") or (el.get("center") or {}).get("lat")
    lon = el.get("lon") or (el.get("center") or {}).get("lon")
    name = tags.get("name:ru") or tags.get("name") or tags.get("name:en")
    if not (name and lat and lon):
        return None
    hours = tags.get("opening_hours")
    return {
        "id": f"osm_{el['type']}_{el['id']}",
        "name": name,
        "lat": lat,
        "lon": lon,
        "category": classify(tags),
        "description": tags.get("description:ru") or tags.get("description"),
        "description_source": "osm" if (tags.get("description:ru") or tags.get("description")) else None,
        "opening_hours": hours,
        "hours_confidence": "from_osm" if hours else "unknown",
        "website": tags.get("website") or tags.get("contact:website"),
        "phone": tags.get("phone") or tags.get("contact:phone"),
        "wheelchair": tags.get("wheelchair"),
        "outdoor_seating": tags.get("outdoor_seating"),
        "internet_access": tags.get("internet_access"),
        "source": "OpenStreetMap",
        "last_updated": date.today().isoformat(),
    }

def main():
    data = fetch()
    records, seen = [], set()
    for el in data.get("elements", []):
        rec = to_record(el)
        if not rec:
            continue
        key = (rec["name"].lower(), round(rec["lat"], 4), round(rec["lon"], 4))
        if key in seen:
            continue
        seen.add(key)
        records.append(rec)

    os.makedirs("data", exist_ok=True)
    with open("data/raw_poi.json", "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"\nВсего точек: {len(records)}")
    for cat, n in Counter(r["category"] for r in records).most_common():
        print(f"  {cat:12s} {n}")
    with_hours = sum(1 for r in records if r["opening_hours"])
    with_desc = sum(1 for r in records if r["description"])
    print(f"\nС часами работы: {with_hours}")
    print(f"С описанием:     {with_desc}")
    print("Сохранено в data/raw_poi.json")

if __name__ == "__main__":
    main()