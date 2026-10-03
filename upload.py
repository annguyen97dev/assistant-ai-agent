"""Validate and sync the scraped Markdown corpus to Gemini File Search."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types


ROOT = Path(__file__).resolve().parent
ARTICLES_DIR = ROOT / "articles"
STORE_NAME_FILE = ROOT / ".file_search_store_name"
CHUNKING_CONFIG = {"white_space_config": {"max_tokens_per_chunk": 512, "max_overlap_tokens": 50}}
load_dotenv(ROOT / ".env")


def load_corpus() -> list[dict]:
    manifest = json.loads((ARTICLES_DIR / "manifest.json").read_text(encoding="utf-8"))
    articles = manifest["articles"]
    if len(articles) < 30 or manifest["article_count"] != len(articles):
        raise ValueError("Manifest must contain at least 30 articles and a matching count")

    ids: set[str] = set()
    for article in articles:
        article_id = str(article["id"])
        if article_id in ids:
            raise ValueError(f"Duplicate article ID: {article_id}")
        ids.add(article_id)
        path = ARTICLES_DIR / article["file"]
        if not path.is_file() or path.parent != ARTICLES_DIR:
            raise FileNotFoundError(path)
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != article["sha256"]:
            raise ValueError(f"SHA-256 mismatch: {path.name}; rerun scrape.py")
        if f"Article URL: {article['url']}" not in content.decode("utf-8"):
            raise ValueError(f"Missing source URL: {path.name}")
    return articles


def resolve_store_name(argument: str | None = None) -> str | None:
    if argument:
        return argument
    if os.environ.get("FILE_SEARCH_STORE_NAME"):
        return os.environ["FILE_SEARCH_STORE_NAME"]
    if STORE_NAME_FILE.exists():
        return STORE_NAME_FILE.read_text(encoding="utf-8").strip() or None
    return None


def metadata(document: types.Document) -> dict[str, str]:
    return {item.key: item.string_value for item in document.custom_metadata or [] if item.key and item.string_value}


def wait_for_upload(client: genai.Client, operation: types.UploadToFileSearchStoreOperation) -> str:
    deadline = time.monotonic() + 600
    while not operation.done:
        if time.monotonic() >= deadline:
            raise TimeoutError("Gemini indexing did not finish within 10 minutes")
        time.sleep(5)
        operation = client.operations.get(operation)
    if operation.error:
        raise RuntimeError(f"Gemini indexing failed: {operation.error}")
    name = operation.response.document_name if operation.response else None
    if not name:
        raise RuntimeError("Gemini finished indexing without a document name")
    return name


def wait_for_active_document(client: genai.Client, name: str) -> None:
    for _ in range(24):
        document = client.file_search_stores.documents.get(name=name)
        if document.state == types.DocumentState.STATE_ACTIVE:
            return
        if document.state == types.DocumentState.STATE_FAILED:
            raise RuntimeError(f"Gemini failed to index document: {name}")
        time.sleep(5)
    raise TimeoutError(f"Gemini document did not become active: {name}")


def upload(corpus: list[dict], store_name: str | None) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("API_KEY")
    if not api_key or api_key == "replace_me":
        raise RuntimeError("Add GEMINI_API_KEY to .env (do not paste the key into chat)")
    client = genai.Client(api_key=api_key)

    if store_name is None:
        store = client.file_search_stores.create(
            config={"display_name": "OptiBot Help Center", "embedding_model": "models/gemini-embedding-2"}
        )
        store_name = store.name
        if not store_name:
            raise RuntimeError("Gemini created a store without a name")
        STORE_NAME_FILE.write_text(store_name + "\n", encoding="utf-8")
        print(f"Created File Search store: {store_name}", flush=True)
    else:
        client.file_search_stores.get(name=store_name)
        print(f"Using File Search store: {store_name}", flush=True)

    existing: dict[str, list[types.Document]] = {}
    for document in client.file_search_stores.documents.list(parent=store_name):
        article_id = metadata(document).get("article_id")
        if article_id:
            existing.setdefault(article_id, []).append(document)

    added = updated = skipped = 0
    for article in corpus:
        article_id = str(article["id"])
        previous = existing.get(article_id, [])
        if any(
            item.state == types.DocumentState.STATE_ACTIVE
            and metadata(item).get("sha256") == article["sha256"]
            for item in previous
        ):
            skipped += 1
            print(f"skipped {article['file']}", flush=True)
            continue

        path = ARTICLES_DIR / article["file"]
        operation = client.file_search_stores.upload_to_file_search_store(
            file=path,
            file_search_store_name=store_name,
            config={
                "display_name": path.name,
                "mime_type": "text/markdown",
                "chunking_config": CHUNKING_CONFIG,
                "custom_metadata": [
                    {"key": "article_id", "string_value": article_id},
                    {"key": "sha256", "string_value": article["sha256"]},
                    {"key": "source_url", "string_value": article["url"]},
                ],
            },
        )
        new_name = wait_for_upload(client, operation)
        wait_for_active_document(client, new_name)
        for old in previous:
            client.file_search_stores.documents.delete(name=old.name, config={"force": True})
        action = "updated" if previous else "added"
        if previous:
            updated += 1
        else:
            added += 1
        print(f"{action} {path.name} -> {new_name}", flush=True)

    summary = {"file_search_store_name": store_name, "source_articles": len(corpus),
               "added": added, "updated": updated, "skipped": skipped,
               "chunk_count_note": "Gemini does not return the actual number of internal chunks",
               "chunking_config": CHUNKING_CONFIG}
    print(json.dumps(summary, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store-name", help="Use an existing File Search store")
    parser.add_argument("--dry-run", action="store_true", help="Validate local files without API access")
    args = parser.parse_args()
    corpus = load_corpus()
    print(f"Validated {len(corpus)} Markdown files and SHA-256 hashes")
    if args.dry_run:
        print("Dry run only: no store created and no files uploaded")
        return 0
    upload(corpus, resolve_store_name(args.store_name))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"Upload failed: {error}", file=sys.stderr)
        sys.exit(1)
