"""Smoke-test OptiBot with Gemini File Search and print its citations."""

from __future__ import annotations

import argparse
import os
import sys

from google import genai
from google.genai import types

from upload import ROOT, resolve_store_name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", nargs="?", default="How do I add a YouTube video?")
    parser.add_argument("--store-name")
    args = parser.parse_args()
    store_name = resolve_store_name(args.store_name)
    if not store_name:
        raise RuntimeError("Run upload.py first or set FILE_SEARCH_STORE_NAME")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "replace_me":
        raise RuntimeError("Add GEMINI_API_KEY to .env")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash"),
        contents=args.question,
        config=types.GenerateContentConfig(
            system_instruction=(ROOT / "system_prompt.txt").read_text(encoding="utf-8"),
            tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[store_name]))],
        ),
    )
    answer = response.text or "(No text returned)"
    print(answer)
    citations: list[str] = []
    for candidate in response.candidates or []:
        grounding = candidate.grounding_metadata
        if not grounding:
            continue
        for chunk in grounding.grounding_chunks or []:
            context = chunk.retrieved_context
            if not context:
                continue
            source_url = next(
                (item.string_value for item in context.custom_metadata or [] if item.key == "source_url"),
                None,
            )
            if source_url and source_url not in citations:
                citations.append(source_url)
    uncited = [url for url in citations if url not in answer]
    if uncited:
        print("\nSources:")
        for url in uncited[: max(0, 3 - answer.count("Article URL:"))]:
            print(f"Article URL: {url}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"Question failed: {error}", file=sys.stderr)
        sys.exit(1)
