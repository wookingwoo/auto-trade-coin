from __future__ import annotations

from datetime import UTC, datetime

import feedparser
import httpx

from app.config import Settings
from app.models.market import NewsSignal


class NewsSignalService:
    """Collect external news and sentiment signals."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = httpx.Client(timeout=10.0)

    def collect(self, run_id: str, symbol: str) -> list[NewsSignal]:
        signals: list[NewsSignal] = []
        now = datetime.now(tz=UTC)

        for url in self.settings.news_rss_urls:
            feed = feedparser.parse(url)
            for entry in feed.entries[: self.settings.news_headline_limit]:
                published = self._parse_feed_time(entry)
                signals.append(
                    NewsSignal(
                        run_id=run_id,
                        symbol=symbol,
                        collected_at=now,
                        signal_type="headline",
                        source=feed.feed.get("title", url),
                        title=entry.get("title", "Untitled headline"),
                        summary=entry.get("summary"),
                        url=entry.get("link"),
                        published_at=published,
                    )
                )

        try:
            response = self._client.get(self.settings.fear_greed_api_url)
            response.raise_for_status()
            payload = response.json()
            current = payload["data"][0]
            signals.append(
                NewsSignal(
                    run_id=run_id,
                    symbol=symbol,
                    collected_at=now,
                    signal_type="sentiment",
                    source="alternative.me",
                    title="Crypto Fear & Greed Index",
                    summary=f"Current value is {current['value']} ({current['value_classification']}).",
                    sentiment_label=current["value_classification"],
                    sentiment_score=float(current["value"]),
                    metadata={"time_until_update": current.get("time_until_update")},
                )
            )
        except Exception:
            pass

        return signals

    @staticmethod
    def _parse_feed_time(entry: dict) -> datetime | None:
        value = entry.get("published_parsed") or entry.get("updated_parsed")
        if not value:
            return None
        return datetime(*value[:6], tzinfo=UTC)

