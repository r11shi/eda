"""Downloads the official Chicago Food Inspections records for 1 Jan 2022 - 31 Dec 2025 from the City of Chicago Data Portal (Socrata API)."""
import hashlib, urllib.parse, urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "data" / "raw"; root.mkdir(parents=True, exist_ok=True)
base = "https://data.cityofchicago.org/resource/4ijn-s7e5.csv"
query = urllib.parse.urlencode({"$where": "inspection_date between '2022-01-01T00:00:00' and '2025-12-31T23:59:59'", "$order": "inspection_date,inspection_id", "$limit": "500000"})
target = root / "food_inspections_2022_2025.csv"
with urllib.request.urlopen(f"{base}?{query}", timeout=600) as r, open(target, "wb") as f:
    f.write(r.read())
meta = root / "socrata_metadata.json"
with urllib.request.urlopen("https://data.cityofchicago.org/api/views/4ijn-s7e5.json", timeout=60) as r, open(meta, "wb") as f:
    f.write(r.read())
print("saved", target, "sha256", hashlib.sha256(target.read_bytes()).hexdigest())
print("The portal is updated over time: a later download can differ slightly from the file documented in docs/dataset_source.md.")
