# OptiBot Mini-Clone

Scrapes public OptiSigns Help Center articles into Markdown, indexes them in Gemini File Search, and answers support questions with source URLs.

## Run locally

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.sample .env  # set GEMINI_API_KEY locally; never commit it
.venv/bin/python scrape.py
.venv/bin/python upload.py
.venv/bin/python ask.py
```

`scrape.py` paginates the public Zendesk Help Center API, selects 39 articles across seven relevant sections, and retains headings, links, tables, and code blocks. `articles/manifest.json` records source URLs and SHA-256 hashes. `upload.py` validates those files, creates or reuses a Gemini File Search store, waits for indexing, and skips unchanged documents by comparing remote `article_id` and `sha256` metadata. Changed articles are uploaded and activated before old versions are removed. Chunking is configured at 512 tokens maximum with 50-token overlap; Gemini does not expose its actual internal chunk count. `system_prompt.txt` is the exact assignment prompt.

## Daily Railway job

`main.py` runs one scrape-and-sync pass, prints `added`, `updated`, and `skipped` counts as `JOB_RESULT`, writes `logs/last-run.json`, then exits 0. The [Dockerfile](Dockerfile) runs this one-shot command. Locally: `docker build -t optibot-daily .` and `docker run --rm --env-file .env optibot-daily` (set `FILE_SEARCH_STORE_NAME` in `.env` to the existing store).

[Railway daily-sync service](https://railway.com/project/e647be60-33fe-4bd6-8da3-d133158c2ffa/service/530f0ffd-322e-45f7-b9cd-667638a1b6cc) is scheduled by `.railway/railway.ts` for `0 19 * * *` UTC (02:00 Vietnam time). The first [Railway run log](logs/railway-first-run.txt) recorded `added=0`, `updated=0`, `skipped=39` and a successful exit. Railway dashboard logs may require project access; the checked-in log is the reviewable artifact. The Gemini key is a Railway service variable and is excluded from the image and Git.

## Assistant evidence

[Google AI Studio Build screenshot](screenshots/optibot-aistudio-youtube.png) shows the requested YouTube question, answer, and cited URLs. `ask.py` independently checks File Search retrieval; [API answer log](logs/youtube-answer.txt) and [upload log](logs/upload-verification.txt) record the result.
