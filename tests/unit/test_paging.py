# tests/unit/test_paging.py

import asyncio
import threading

import pytest
import requests

from spotify_to_tidal.paging import Page, fetch_all, retry
from spotify_to_tidal.tidalapi_patch import _tidal_page_fetcher

NO_WAIT = (0, 0)


def make_endpoint(total, limit):
    """ Blocking page function over items 0..total-1, recording the offsets it was asked for """
    calls = []
    lock = threading.Lock()

    def fetch_page(offset):
        with lock:
            calls.append(offset)
        return Page(items=list(range(offset, min(offset + limit, total))), total=total, limit=limit)

    return fetch_page, calls


def test_fetch_all_returns_every_item_in_order():
    fetch_page, calls = make_endpoint(total=23, limit=5)
    assert asyncio.run(fetch_all(fetch_page, backoff=NO_WAIT)) == list(range(23))
    assert sorted(calls) == [0, 5, 10, 15, 20]


def test_fetch_all_single_page_makes_one_call():
    fetch_page, calls = make_endpoint(total=3, limit=5)
    assert asyncio.run(fetch_all(fetch_page, backoff=NO_WAIT)) == [0, 1, 2]
    assert calls == [0]


def test_fetch_all_empty_endpoint():
    fetch_page, calls = make_endpoint(total=0, limit=5)
    assert asyncio.run(fetch_all(fetch_page, backoff=NO_WAIT)) == []
    assert calls == [0]


def test_fetch_all_retries_a_failing_page():
    fetch_page, _ = make_endpoint(total=10, limit=5)
    failures = {5: 1}

    def flaky(offset):
        if failures.get(offset):
            failures[offset] -= 1
            raise requests.exceptions.ConnectionError("boom")
        return fetch_page(offset)

    assert asyncio.run(fetch_all(flaky, backoff=NO_WAIT)) == list(range(10))


def test_retry_reraises_after_last_attempt():
    attempts = []

    def always_fails():
        attempts.append(1)
        raise requests.exceptions.ConnectionError("boom")

    with pytest.raises(requests.exceptions.ConnectionError):
        asyncio.run(retry(always_fails, backoff=NO_WAIT))
    assert len(attempts) == len(NO_WAIT) + 1


def test_retry_does_not_retry_other_errors():
    attempts = []

    def bug():
        attempts.append(1)
        raise KeyError("not transient")

    with pytest.raises(KeyError):
        asyncio.run(retry(bug, backoff=NO_WAIT))
    assert len(attempts) == 1


class FakeTidalRequest:
    """ Mimics tidalapi's session.request for a paginated endpoint """
    def __init__(self, total, limit):
        self.total, self.limit = total, limit
        self.seen_params = []
        self.lock = threading.Lock()

    def map_request(self, url, params):
        with self.lock:
            self.seen_params.append(params)
        offset = params['offset']
        return {'limit': self.limit, 'totalNumberOfItems': self.total,
                'items': list(range(offset, min(offset + self.limit, self.total)))}

    def map_json(self, raw, parse):
        return [parse(i) for i in raw['items']]


def test_tidal_pages_get_their_own_offset():
    request = FakeTidalRequest(total=50, limit=10)
    session = type("Session", (), {"request": request})()
    params = {"limit": 10}

    items = asyncio.run(fetch_all(_tidal_page_fetcher("url", session, parser=lambda x: x, params=params), backoff=NO_WAIT))

    assert items == list(range(50))
    assert sorted(p['offset'] for p in request.seen_params) == [0, 10, 20, 30, 40]
    assert params == {"limit": 10}  # caller's params are never mutated
