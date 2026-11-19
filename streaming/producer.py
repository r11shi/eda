"""Kafka producer: REPLAYS historical completed inspections in chronological order as simulated live events.

IMPORTANT: the official dataset is a historical file, not a live feed. Every event carries
source_mode = "REPLAY_SIMULATION" and the dashboard is labelled as a replay simulation.

  python streaming/producer.py --from 2025-10-01 --to 2025-12-31 --rate 60 [--bad-every 100]
"""
import argparse, json, time, uuid
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from kafka import KafkaProducer

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--bootstrap", default="localhost:9092"); ap.add_argument("--topic", default="food_inspections")
ap.add_argument("--from", dest="d_from", default="2025-10-01"); ap.add_argument("--to", dest="d_to", default="2025-12-31")
ap.add_argument("--rate", type=float, default=60.0, help="replay speed in events per second")
ap.add_argument("--bad-every", type=int, default=0, help="inject one malformed test event after every N events (0 = none)")
args = ap.parse_args()

df = pd.read_csv(ROOT / "data" / "curated" / "inspections_curated.csv", parse_dates=["inspection_date"], dtype={"zip": str, "license_number": str})
df = df[df["is_completed"] & df["inspection_date"].between(args.d_from, args.d_to)].sort_values(["inspection_date", "inspection_id"])
run_id = uuid.uuid4().hex[:8]
producer = KafkaProducer(bootstrap_servers=args.bootstrap, key_serializer=lambda k: str(k).encode(), value_serializer=lambda v: v if isinstance(v, bytes) else json.dumps(v).encode(),
                         linger_ms=5, acks=1)
now_iso = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
nn = lambda v: None if pd.isna(v) else v

print(f"REPLAY SIMULATION run {run_id}: {len(df):,} completed inspections {args.d_from}..{args.d_to} at {args.rate}/s -> topic '{args.topic}'")
t0, sent, bad = time.time(), 0, 0
for i, r in enumerate(df.itertuples(index=False)):
    event = {"event_id": f"e-{r.inspection_id}", "source_mode": "REPLAY_SIMULATION", "replay_run_id": run_id, "emitted_at": now_iso(),
             "event_time": r.inspection_date.strftime("%Y-%m-%d"), "inspection_id": int(r.inspection_id), "license_number": nn(r.license_number),
             "dba_name": r.dba_name, "facility_type": r.facility_type_clean, "facility_group": r.facility_group, "risk_group": r.risk_group,
             "inspection_type_group": r.inspection_type_group, "result": r.results, "result_group": r.result_group,
             "violation_count": None if pd.isna(r.violation_count) else int(r.violation_count), "zip": r.zip, "area_group": r.geographic_area_group}
    producer.send(args.topic, key=r.inspection_id, value=event); sent += 1
    if args.bad_every and (i + 1) % args.bad_every == 0:               # labelled test injection to exercise the validation rules
        kind = (i // args.bad_every) % 3
        if kind == 0:   producer.send(args.topic, key="bad", value=b"{this is not json")
        elif kind == 1: producer.send(args.topic, key="bad", value={**event, "result_group": "Banana", "inspection_id": int(r.inspection_id) + 10**9})
        else:           producer.send(args.topic, key="bad", value={**event, "violation_count": -5, "inspection_id": int(r.inspection_id) + 2 * 10**9})
        bad += 1
    delay = t0 + (i + 1) / args.rate - time.time()
    if delay > 0:
        time.sleep(delay)
producer.flush()
print(f"done: {sent:,} events + {bad} injected malformed test events in {time.time() - t0:.1f} s ({sent / (time.time() - t0):.1f} events/s)")
