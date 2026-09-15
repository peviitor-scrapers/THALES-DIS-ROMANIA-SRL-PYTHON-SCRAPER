"""End-to-end test: scrape the real THALES DIS ROMANIA S.R.L. Phenom board.

Thales publishes Romania jobs on the Phenom-powered career site
(careers.thalesgroup.com). Skips (rather than fails) when the board is
unreachable, so that CI does not break on transient network issues.
"""

import socket

import pytest

from scraper import index

# Observed: 30 unique Romania jobs on the Phenom board (deduplicated by reqId).
# A sane lower bound protects against board restructures without being brittle.
EXPECTED_MIN_JOBS = 1


def _board_reachable():
    try:
        with socket.create_connection(("careers.thalesgroup.com", 443), timeout=5):
            return True
    except OSError:
        return False


def test_scrape_real_board():
    if not _board_reachable():
        pytest.skip("Thales Phenom board not reachable")
    jobs = index.scrape_all_listings()
    assert len(jobs) >= EXPECTED_MIN_JOBS, f"Expected >= {EXPECTED_MIN_JOBS} jobs, got {len(jobs)}"
    for job in jobs:
        assert job["url"].startswith("https://thales.wd3.myworkdayjobs.com/Careers/job/")
        assert job["title"]
    urls = {j["url"] for j in jobs}
    assert len(urls) == len(jobs), "duplicate job URLs found"