# Love Island USA Sentiment Tracker

A personal, non-commercial project that performs read-only sentiment analysis
of public discussion about the TV show *Love Island USA*. It collects public
commentary from **sanctioned, API-first sources**, scores sentiment with an LLM,
stores the results, and surfaces them in a simple dashboard.

## What it does
- **Collects** public commentary from sanctioned sources:
  - **YouTube** (Data API) — comments on recap / reaction videos *(v1)*
  - **News** (GDELT, free, no key) — news coverage *(v1)*
  - **Reddit** (official Data API via PRAW, read-only) — *stubbed, enabled once access is approved*
  - **X / Twitter** (official paid API) — *stubbed, for a later version*
- **Scores** sentiment with an LLM — overall, and by contestant/couple and topic
  (coupling / drama / game). The rubric is built to handle sarcasm, nicknames,
  and spoilers.
- **Stores** results in a local SQLite database (schema written to migrate to
  Postgres later).
- **Surfaces** results in a light Streamlit dashboard: top-line sentiment and
  biggest movers first, then trends over time, by contestant/couple, by source,
  and volume.

> **Source policy:** API-first, sanctioned sources only. This project never
> scrapes X/Twitter, Instagram, Facebook, or Reddit web pages.

## How it's organized
```
loveisland/
  collectors/   one module per source (youtube, news, reddit*, x_api*)
  sentiment/    LLM scoring + the scoring rubric
  store/        SQLite database + schema
  dashboard/    Streamlit app
  config.py     loads config.yaml + .env
  cli.py        the command menu (collect / score / run / serve)
config.yaml     YOUR settings: cast roster, keywords, channels, episodes
.env            YOUR secret keys (never committed; see .env.example)
```
`*` = stubbed, ready to switch on later.

## Setup (one time)

**1. Create the project's private toolbox and install its packages**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**2. Add your keys**
```bash
cp .env.example .env
```
Then open `.env` in any text editor and paste in your keys:
- `YOUTUBE_API_KEY` — from the Google Cloud Console
- `ANTHROPIC_API_KEY` — from https://console.anthropic.com/settings/keys

(GDELT needs no key. Reddit/X keys stay blank until those sources are enabled.)

**3. Fill in the cast**
Open `config.yaml` and set the `season` number and the `entities` roster
(contestants and couples, with nicknames). Examples are included in the file.

## Usage
```bash
python -m loveisland init-db                 # create the database
python -m loveisland run                      # collect + score (the usual command)
python -m loveisland serve                    # open the dashboard

# finer control:
python -m loveisland collect --since 2026-06-08 --source youtube,news
python -m loveisland score --limit 200
```

## Scheduling
Runs automatically **every 3 hours** via a macOS LaunchAgent (the built-in
scheduler), which calls `scripts/run_pipeline.py` (collect + score). A template
plist lives at `scripts/com.loveisland.sentiment.plist`.

```bash
# Install (one time) — copy the template, edit the paths inside, then load:
cp scripts/com.loveisland.sentiment.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.loveisland.sentiment.plist

# Useful commands:
launchctl print gui/$(id -u)/com.loveisland.sentiment   # status
launchctl kickstart gui/$(id -u)/com.loveisland.sentiment  # run now
launchctl bootout gui/$(id -u)/com.loveisland.sentiment    # stop/disable
tail -f outputs/cron.log                                  # watch the log
```

The plist uses `StartCalendarInterval` to run at fixed clock times every 3 hours
(00,03,06,09,12,15,18,21). Change those entries and re-load to adjust cadence.
It runs while the Mac is awake/logged in; launchd also runs one catch-up when
the Mac wakes from sleep.

**Hands-off wake (optional):** schedule the Mac to wake itself so runs fire even
when it's asleep (Apple Silicon wakes from sleep, not full shutdown; keep it
plugged in):
```bash
sudo pmset repeat wakeorpoweron MTWRFSU 23:55:00   # wake nightly for the midnight run
pmset -g sched                                     # verify
sudo pmset repeat cancel                           # remove
```

A cron line is an equivalent alternative to the LaunchAgent:
```cron
0 */3 * * *  cd /path/to/loveisland-sentiment && .venv/bin/python scripts/run_pipeline.py
```

## Reddit usage (when enabled)
- **Read-only.** Does not post, comment, vote, message, or take any user or
  moderator action.
- Targets public subreddit content (r/LoveIslandUSA).
- Low volume, within free-tier rate limits.
- App-only ("script") credentials — no username/password. Stored in the
  gitignored `.env` and never committed.

## Privacy
Author IDs are hashed before storage (`author_hash`); raw usernames are never
saved. The local database (`data/`) and any `outputs/` are gitignored.

## Status
Early development, built step by step. Each data source is a swappable module
behind a common `Collector` interface.

## Stack
Python · YouTube Data API · GDELT · PRAW · Anthropic API · SQLite · Streamlit
