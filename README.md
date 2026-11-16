# Meeting Minutes Studio — Project 03

An AI-assisted portfolio implementation for Pranil Deshmukh: turn meeting transcripts into source-linked discussion excerpts, explicit decisions and action items, review them, then export a saved version. Includes a fictional demo with **no API key required**.

Inspired by Ed Donner's meeting-minutes exercise in [LLM Engineering](https://github.com/ed-donner/llm_engineering/tree/main/week3). This repository adds its own FastAPI interface, conservative source selection, review workflow, SQLite revision history, exports and automated tests. It is a course-inspired, AI-assisted implementation, not a claim of independent course authorship.

## Run on your computer

Install Python 3.11 or newer. Run these commands in a terminal:

```bash
git clone --branch project-03-meeting-minutes --single-branch https://github.com/pra986/source-backed-brochures.git meeting-minutes-assistant
cd meeting-minutes-assistant
python -m venv .venv
```

Activate the environment on Windows:

```powershell
.venv\Scripts\Activate.ps1
```

Or on macOS/Linux:

```bash
source .venv/bin/activate
```

Then:

```bash
python -m pip install -e .
python -m uvicorn minutes.app:app --host 127.0.0.1 --port 8000
```

Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)**. This link works after the server starts on your computer. If another project uses port 8000, choose `--port 8003` and open `http://127.0.0.1:8003`. Stop with Ctrl+C.

1. Click **Load fictional demo**, keep Offline mode, then **Create draft minutes**.
2. Inspect source links; edit, exclude or add items. Blank owner/due fields mean unknown.
3. Check the review box and click **Save review**.
4. Download Markdown minutes, action CSV or the full JSON snapshot. Print/save PDF uses the browser print dialog.
5. Reopen a saved meeting, inspect revisions or delete its local data.

## What it does

- Parses up to 300 transcript segments, with optional speakers and `[MM:SS]` / `[HH:MM:SS]` timestamps.
- Offline selection uses the first four segments as discussion excerpts, explicit decision phrases and explicit commitments. It does not produce an abstractive summary.
- Optional AI selects existing source IDs; the server rejects unknown IDs, duplicate IDs, unsupported decisions and actions. Extracted text remains verbatim.
- Every item retains its original source quote. User edits and manual additions are labeled separately.
- Saves immutable source data, a source hash and revision snapshots in SQLite; stale writes receive HTTP 409.
- Requires a saved reviewed version for exports. Markdown/CSV include only selected items; JSON includes the complete record, including excluded items and the original transcript.
- Optional audio forwards one file, up to 20 MiB, to a configured transcription provider; returned text requires review. Audio is not saved by this application.

## Optional hosted AI/audio

Offline mode needs no configuration. For optional provider modes set environment variables **before** starting the server:

```bash
export OPENAI_API_KEY='your-key'
export OPENAI_MODEL='your-compatible-chat-model'
export OPENAI_TRANSCRIBE_MODEL='your-compatible-transcription-model'
```

PowerShell uses `$env:OPENAI_API_KEY='your-key'` and the same pattern for model variables. Choose models available to your provider account. `.env.example` documents settings; the app does **not** automatically load `.env` files. `OPENAI_BASE_URL` defaults to `https://api.openai.com/v1`. The server uses OpenAI-compatible chat-completions JSON output and audio-transcription endpoints. Provider compatibility and current model availability must be checked for your account.

Transcript content is sent externally only in AI mode; audio only when you explicitly transcribe. Provider usage may incur charges. No live paid provider calls were made for verification; provider contracts are mocked in tests. There is no local speech model, diarization, audio chunking or fabricated speaker/timestamp metadata.

## Data and limits

This is a local, single-user portfolio demo with no authentication or account isolation. Bind to loopback. Do not deploy it publicly as a multi-user service or upload confidential recordings. All users of the same server can access its saved meetings. Transcripts and complete revision snapshots are stored unencrypted in `.data/minutes.sqlite3` (override `MINUTES_DATA_DIR`). Deleting a meeting removes its active record and history; previously downloaded exports and backups remain outside the app.

Source hashes detect a changed string; they do not establish authenticity. Approval records user review, not independent factual verification. Rule-based extraction can miss paraphrases, misread negation or interpret names incorrectly. AI selection can omit important items. Relative due text such as “Friday” is never resolved to a calendar date. Human edits can introduce unsupported claims, so original quotes remain visible. Print layout is browser-controlled; downloadable Markdown/CSV/JSON are the defined export formats.

## Verify

```bash
python -m unittest discover -s tests -v
python -m pip install 'playwright>=1.50,<2'
python -m playwright install chromium
python tests/browser_smoke.py
```

CI runs unit/API tests on Python 3.11, 3.12 and 3.13 plus a Chromium workflow against a real local server. Browser screenshots and downloads are CI artifacts, not committed meeting data. See [evaluation/results.md](evaluation/results.md).

## Understand and present it

- [Architecture, data model and flow](docs/architecture.md)
- [Interview walkthrough and contribution notes](docs/interview.md)

This branch is a standalone project within the existing repository. Project 01 and Project 02 remain on their own branches. Do not merge this branch's root replacement over another application by accident.
