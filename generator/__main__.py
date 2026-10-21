"""CLI: python -m generator --seed 42 --out data/ [--matches 3]"""
import argparse
import json
from pathlib import Path

from .core import generate_match, FIXTURES

# Hand-picked seeds giving typical-looking demo matches (balanced shots, 2-4 goals).
DEMO_SEEDS = [53, 58, 63]


def main() -> None:
    p = argparse.ArgumentParser(description="Generate synthetic football matches.")
    p.add_argument("--seed", type=int, default=42, help="base random seed")
    p.add_argument("--out", type=Path, default=Path("data"), help="output directory")
    p.add_argument("--matches", type=int, default=3, help="number of matches")
    p.add_argument("--demo", action="store_true", help="use curated DEMO_SEEDS for the 3 fixtures")
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    for i in range(a.matches):
        home, away = FIXTURES[i % len(FIXTURES)]
        meta, events = generate_match(seed=DEMO_SEEDS[i % 3] if a.demo else a.seed + i, home=home, away=away, match_no=i + 1)
        mid = meta["match_id"]
        (a.out / f"{mid}_meta.json").write_text(json.dumps(meta, indent=2))
        with open(a.out / f"{mid}_events.jsonl", "w") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")
        s = meta["final_score"]
        print(f"{mid}: {meta['home']['name']} {s['home']}-{s['away']} {meta['away']['name']} ({len(events)} events)")


if __name__ == "__main__":
    main()
