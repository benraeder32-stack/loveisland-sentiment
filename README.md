# Love Island USA Sentiment Tracker

A personal, non-commercial project that performs read-only sentiment analysis
of public discussion about the TV show *Love Island USA*.

## What it does
- Collects public posts and comments from sanctioned sources: Reddit (official
  Data API via PRAW), YouTube (Data API), and news (GDELT).
- Scores sentiment with an LLM — overall, and by contestant/couple and topic.
- Stores results in a local database and surfaces them in a personal dashboard.

## Reddit usage
- **Read-only.** Does not post, comment, vote, message, or take any user or
  moderator action.
- Targets public subreddit content (r/LoveIslandUSA).
- Low volume, within free-tier rate limits (100 QPM).
- API credentials live in a gitignored `.env` and are never committed.

## Status
Early development. Collectors are modular — each data source is a swappable
module behind a common interface.

## Stack
Python · PRAW · SQLite · LLM-based sentiment scoring.# loveisland-sentiment
