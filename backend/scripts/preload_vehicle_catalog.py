"""Preload the internal vehicle reference catalog from NHTSA vPIC.

This is an explicit operator command, not a Check-in request and not a daemon.
It stores year/make/model identifiers plus provenance only. It does not decode
VINs, create shop vehicles, create customer links, or generate service advice.

Example:
  DATABASE_URL=... python scripts/preload_vehicle_catalog.py --year 2017 --make Toyota
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from urllib.parse import quote

import httpx

from app.db.models import VehicleCatalogEntry
from app.db.session import SessionLocal
from app.customer_data_security import normalize_search_text

BASE = "https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMakeYear"


def fetch_models(client: httpx.Client, year: int, make: str) -> tuple[str, list[dict]]:
    endpoint = f"{BASE}/make/{quote(make, safe='')}/modelyear/{year}?format=json"
    response = client.get(endpoint)
    response.raise_for_status()
    payload = response.json()
    return endpoint, payload.get("Results", [])


def upsert_year_make(year: int, make: str) -> int:
    now = datetime.utcnow()
    with httpx.Client(timeout=20.0, headers={"Accept": "application/json"}) as client:
        endpoint, rows = fetch_models(client, year, make)
    count = 0
    with SessionLocal() as db:
        for row in rows:
            source_make_id = str(row.get("Make_ID") or "")
            source_model_id = str(row.get("Model_ID") or "")
            source_make = str(row.get("Make_Name") or "").strip()
            source_model = str(row.get("Model_Name") or "").strip()
            if not (source_make_id and source_model_id and source_make and source_model):
                continue
            entry = db.query(VehicleCatalogEntry).filter(
                VehicleCatalogEntry.source_name == "nhtsa_vpic",
                VehicleCatalogEntry.model_year == year,
                VehicleCatalogEntry.source_make_id == source_make_id,
                VehicleCatalogEntry.source_model_id == source_model_id,
            ).one_or_none()
            if not entry:
                entry = VehicleCatalogEntry(
                    source_name="nhtsa_vpic",
                    source_make_id=source_make_id,
                    source_model_id=source_model_id,
                    model_year=year,
                    make=source_make,
                    model=source_model,
                    search_text=normalize_search_text(f"{year} {source_make} {source_model}"),
                    source_url=endpoint,
                    source_retrieved_at=now,
                    active=True,
                    created_at=now,
                )
                db.add(entry)
            else:
                entry.make = source_make
                entry.model = source_model
                entry.search_text = normalize_search_text(f"{year} {source_make} {source_model}")
                entry.source_url = endpoint
                entry.source_retrieved_at = now
                entry.active = True
            count += 1
        db.commit()
    return count


def main():
    parser = argparse.ArgumentParser(description="Cache NHTSA vPIC year/make/model reference records for staff Check-in.")
    parser.add_argument("--year", type=int, action="append", required=True, help="Model year; repeatable.")
    parser.add_argument("--make", action="append", required=True, help="Vehicle make; repeatable.")
    parser.add_argument("--sleep-seconds", type=float, default=1.0, help="Pause between source requests to respect NHTSA rate control.")
    args = parser.parse_args()
    if any(year < 1886 or year > 2100 for year in args.year):
        parser.error("--year must be between 1886 and 2100")
    if args.sleep_seconds < 0.25:
        parser.error("--sleep-seconds must be at least 0.25")

    total = 0
    jobs = [(year, make.strip()) for year in args.year for make in args.make if make.strip()]
    for index, (year, make) in enumerate(jobs, start=1):
        count = upsert_year_make(year, make)
        total += count
        print(f"cached {count} NHTSA catalog rows for {year} {make}")
        if index < len(jobs):
            time.sleep(args.sleep_seconds)
    print(f"complete: cached or refreshed {total} source rows")


if __name__ == "__main__":
    main()
