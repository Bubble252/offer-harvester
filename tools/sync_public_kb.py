#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "app" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from public_kb import PublicKBStore, seed_target_universities  # noqa: E402
from storage import Workspace  # noqa: E402
from supabase_sync import SupabasePublicKBSync  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed and optionally sync the public admissions KB."
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=ROOT / "workspace",
        help="Workspace that contains public_kb/.",
    )
    parser.add_argument(
        "--seed-target-universities",
        action="store_true",
        help="Seed all 985 plus confirmed strong 211/specialized universities.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace local public_kb seed files instead of appending missing records.",
    )
    parser.add_argument(
        "--schema-sql-out",
        type=Path,
        default=None,
        help="Write Supabase/Postgres schema SQL to this file.",
    )
    parser.add_argument(
        "--data-sql-out",
        type=Path,
        default=None,
        help="Write schema plus public KB upsert SQL to this file.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform live Postgres sync. Default is dry-run.",
    )
    args = parser.parse_args()

    workspace = Workspace(str(args.workspace))
    store = PublicKBStore(workspace)
    seed_result = None
    if args.seed_target_universities:
        seed_result = seed_target_universities(store, replace=args.replace)

    syncer = SupabasePublicKBSync(
        database_url=os.environ.get("PUBLIC_KB_DATABASE_URL", ""),
        dry_run=not args.apply,
    )
    if args.schema_sql_out:
        args.schema_sql_out.parent.mkdir(parents=True, exist_ok=True)
        args.schema_sql_out.write_text(syncer.schema_sql(), encoding="utf-8")
    if args.data_sql_out:
        syncer.write_data_sql(store, args.data_sql_out)

    result = syncer.sync(store)
    payload = {
        "workspace": str(workspace.root),
        "seed": seed_result.model_dump() if seed_result else None,
        "validation": store.validate().model_dump(),
        "sync": result.__dict__,
        "schema_sql_out": str(args.schema_sql_out) if args.schema_sql_out else "",
        "data_sql_out": str(args.data_sql_out) if args.data_sql_out else "",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not result.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
