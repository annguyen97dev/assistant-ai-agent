"""Run one scrape-and-sync job; schedule this container externally once per day."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

from scrape import scrape
from upload import ARTICLES_DIR, ROOT, load_corpus, resolve_store_name, upload


def main() -> int:
    store_name = resolve_store_name()
    if not store_name and os.environ.get("REQUIRE_EXISTING_STORE") == "1":
        raise RuntimeError(
            "Set FILE_SEARCH_STORE_NAME to the existing store before scheduling the job"
        )

    started_at = datetime.now(timezone.utc).isoformat()
    manifest = scrape(ARTICLES_DIR)
    summary = upload(load_corpus(), store_name)
    result = {
        "started_at_utc": started_at,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_public_articles_seen": manifest["total_public_articles_seen"],
        **summary,
    }
    logs_dir = ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)
    (logs_dir / "last-run.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print("JOB_RESULT " + json.dumps(result), flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print("JOB_ERROR " + json.dumps({"error": str(error)}), file=sys.stderr)
        sys.exit(1)
