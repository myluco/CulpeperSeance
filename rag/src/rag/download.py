"""Fetch the Gutenberg plain-text edition of Culpeper's Complete Herbal."""
from __future__ import annotations

from pathlib import Path

import httpx

from .config import GUTENBERG_URLS, Settings, get_settings

MIN_EXPECTED_BYTES = 500_000  # the real file is ~1.5 MB; anything tiny is an error page


class DownloadError(RuntimeError):
    pass


def download(settings: Settings | None = None, force: bool = False) -> Path:
    """Download the book to data/raw/ unless it is already there. Returns the path."""
    settings = settings or get_settings()
    target = settings.raw_text
    if target.exists() and target.stat().st_size >= MIN_EXPECTED_BYTES and not force:
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    for url in GUTENBERG_URLS:
        try:
            response = httpx.get(url, follow_redirects=True, timeout=60.0)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            errors.append(f"{url}: {exc}")
            continue
        data = response.content
        if len(data) < MIN_EXPECTED_BYTES or b"Culpeper" not in data[:200_000]:
            errors.append(f"{url}: response does not look like the herbal ({len(data)} bytes)")
            continue
        tmp = target.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.replace(target)
        return target

    raise DownloadError(
        "Could not download the herbal.\n  "
        + "\n  ".join(errors)
        + f"\nYou can fetch it manually and save it as {target}"
    )
