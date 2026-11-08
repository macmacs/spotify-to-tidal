""" Paged fetch: get every item from a paginated endpoint, in parallel, with retry on transient errors """
import asyncio
from dataclasses import dataclass
from typing import Callable, Sequence, TypeVar

import requests
import spotipy
import tidalapi
from tqdm.asyncio import tqdm as atqdm

T = TypeVar('T')

RETRYABLE_ERRORS = (
    tidalapi.exceptions.TooManyRequests,
    requests.exceptions.RequestException,
    spotipy.exceptions.SpotifyException,
)

# seconds to wait before each retry; the number of entries is the number of retries
BACKOFF_SECONDS: Sequence[float] = (1, 10, 60, 5 * 60, 10 * 60)


@dataclass
class Page:
    items: list
    total: int
    limit: int


async def retry(fn: Callable[..., T], *args, backoff: Sequence[float] = BACKOFF_SECONDS, **kwargs) -> T:
    """
    Run the blocking function fn in a worker thread, retrying on transient network / rate limit errors.
    Re-raises the last error once all retries are used up.
    """
    for attempt, delay in enumerate((*backoff, None)):
        try:
            return await asyncio.to_thread(fn, *args, **kwargs)
        except RETRYABLE_ERRORS as e:
            if isinstance(e, requests.exceptions.RequestException) and e.response is not None:
                print(f"Response message: {e.response.text}")
                print(f"Response headers: {e.response.headers}")
            if delay is None:
                print(f"{e} could not be recovered")
                raise
            print(f"{e} occurred, retrying {len(backoff) - attempt} more times")
            await asyncio.sleep(delay)


async def fetch_all(fetch_page: Callable[[int], Page], *, backoff: Sequence[float] = BACKOFF_SECONDS,
                    desc: str = "Fetching additional data chunks") -> list:
    """
    Fetch every item from a paginated endpoint.
    fetch_page(offset) is a blocking call returning one Page; pages after the first are fetched in parallel.
    """
    first = await retry(fetch_page, 0, backoff=backoff)
    items = list(first.items)
    if first.limit <= 0:
        return items

    offsets = range(first.limit, first.total, first.limit)
    if offsets:
        pages = await atqdm.gather(*[retry(fetch_page, offset, backoff=backoff) for offset in offsets], desc=desc)
        for page in pages:
            items.extend(page.items)
    return items
