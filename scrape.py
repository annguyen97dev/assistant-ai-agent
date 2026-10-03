"""Download a focused set of public OptiSigns Help Center articles as Markdown."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


API_URL = "https://support.optisigns.com/api/v2/help_center/en-us/articles.json"
SOURCE_HOST = "support.optisigns.com"

# A focused support corpus: getting started, screens, assets, playlists,
# schedules, and video integrations. Listing the full Help Center on each run
# also lets this selection pick up future articles in these sections.
SECTIONS = {
    26398357451923: "Getting started",
    26318906819091: "Screens",
    26318828341267: "Assets and content",
    26324652803475: "Playlists",
    26319329063571: "Playlist controls",
    26324698105235: "Schedules",
    26324076807315: "YouTube and video",
}


def session_with_retries() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=4,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(
        {"Accept": "application/json", "User-Agent": "OptiBotTakeHomeScraper/1.0"}
    )
    return session


def fetch_articles(session: requests.Session) -> list[dict]:
    articles: list[dict] = []
    next_url: str | None = API_URL
    params = {"per_page": 100}

    while next_url:
        parsed = urlparse(next_url)
        if parsed.scheme != "https" or parsed.hostname != SOURCE_HOST:
            raise ValueError(f"Unexpected pagination URL: {next_url}")
        response = session.get(next_url, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        articles.extend(payload["articles"])
        next_url = payload.get("next_page")
        params = None  # next_page already includes its query parameters.
        if next_url:
            time.sleep(0.25)

    return articles


def slugify(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title)
    ascii_title = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title).strip("-")
    return slug[:80] or "article"


def html_to_markdown(body: str) -> str:
    soup = BeautifulSoup(body, "html.parser")

    for tag in soup.select(
        "script, style, nav, aside, footer, form, button, "
        "[aria-hidden='true'], .advertisement, .related-articles"
    ):
        tag.decompose()

    # Zendesk articles sometimes put an in-article table of contents before
    # the actual instructions. Its anchor list is navigation, not answer text.
    for intro in soup.find_all(re.compile(r"^(h[1-6]|p)$")):
        if not intro.get_text(" ", strip=True).lower().startswith("in this article"):
            continue
        following = intro.find_next_sibling()
        if following and following.name in ("ul", "ol"):
            links = following.find_all("a", href=True)
            if links and all(link["href"].startswith("#") for link in links):
                following.decompose()
                intro.decompose()

    for paragraph in soup.find_all("p"):
        content = paragraph.get_text(" ", strip=True).lower()
        if "if you have any additional questions" in content and "support@optisigns.com" in content:
            paragraph.decompose()

    for iframe in soup.find_all("iframe"):
        src = iframe.get("src")
        if src and urlparse(src).scheme in ("http", "https"):
            link = soup.new_tag("a", href=src)
            link.string = "Embedded video"
            iframe.replace_with(link)
        else:
            iframe.decompose()

    for image in soup.find_all("img"):
        if not image.get("alt", "").strip():
            image["alt"] = "Article screenshot"

    # Inline presentation spans add no meaning to Markdown.
    for span in soup.find_all("span"):
        span.unwrap()

    for link in soup.find_all("a", href=True):
        if link["href"].strip().lower().startswith(("javascript:", "data:")):
            link.unwrap()

    text = markdownify(str(soup), heading_style="ATX", bullets="-")
    text = text.replace("\u00a0", " ").replace("\u200b", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def article_markdown(article: dict) -> str:
    title = article["title"].strip()
    url = article["html_url"]
    body = html_to_markdown(article["body"] or "")
    if not body:
        raise ValueError(f"Article {article['id']} has no usable body")
    return f"# {title}\n\nArticle URL: {url}\n\n{body}\n"


def scrape(output_dir: Path, minimum: int = 30) -> dict:
    with session_with_retries() as session:
        all_articles = fetch_articles(session)
    selected = sorted(
        (
            article
            for article in all_articles
            if article.get("section_id") in SECTIONS
            and not article.get("draft")
            and article.get("body")
        ),
        key=lambda article: int(article["id"]),
    )
    if len(selected) < minimum:
        raise RuntimeError(f"Only {len(selected)} usable articles; need {minimum}")

    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    changed = 0
    for article in selected:
        filename = f"{article['id']}-{slugify(article['title'])}.md"
        path = output_dir / filename
        content = article_markdown(article)
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            path.write_text(content, encoding="utf-8")
            changed += 1
        records.append(
            {
                "id": article["id"],
                "title": article["title"].strip(),
                "section": SECTIONS[article["section_id"]],
                "url": article["html_url"],
                "updated_at": article["updated_at"],
                "file": filename,
                "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            }
        )

    manifest = {
        "source": API_URL,
        "total_public_articles_seen": len(all_articles),
        "article_count": len(records),
        "articles": records,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Fetched {len(all_articles)} public articles; selected {len(records)}; "
        f"Markdown files changed: {changed}; unchanged: {len(records) - changed}"
    )
    print(f"Output: {output_dir.resolve()}")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("articles"))
    args = parser.parse_args()
    scrape(args.output_dir)
