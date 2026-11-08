# tests/unit/test_track_resolution.py

import asyncio
from types import SimpleNamespace

import pytest
import requests

from spotify_to_tidal.cache import MatchFailureDatabase
from spotify_to_tidal.track_resolution import TrackResolver


def tidal_track(id, name, artists, duration=200, isrc=None, version=None, available=True):
    return SimpleNamespace(id=id, name=name, artists=[SimpleNamespace(name=a) for a in artists],
                           duration=duration, isrc=isrc, version=version, available=available)


def tidal_album(name, artists, tracks):
    return SimpleNamespace(name=name, artists=[SimpleNamespace(name=a) for a in artists],
                           num_tracks=len(tracks), tracks=lambda: list(tracks))


def spotify_track(id, name, artists, duration_ms=200_000, isrc=None, album="Album", track_number=1):
    return {
        'id': id, 'name': name, 'artists': [{'name': a} for a in artists],
        'duration_ms': duration_ms, 'track_number': track_number,
        'external_ids': {'isrc': isrc} if isrc else {},
        'album': {'name': album, 'artists': [{'name': artists[0]}]},
    }


class FakeCatalogue:
    """ In-memory TidalCatalogue """
    def __init__(self, albums=(), tracks=(), failures=0):
        self.albums, self.tracks, self.failures = list(albums), list(tracks), failures
        self.queries = []

    def _maybe_fail(self):
        if self.failures:
            self.failures -= 1
            raise requests.exceptions.ConnectionError("transient")

    def search_albums(self, query):
        self._maybe_fail()
        self.queries.append(('album', query))
        return self.albums

    def search_tracks(self, query):
        self._maybe_fail()
        self.queries.append(('track', query))
        return self.tracks


@pytest.fixture
def failure_db(tmp_path):
    return MatchFailureDatabase(str(tmp_path / "cache.db"))


def make_resolver(catalogue, failure_db):
    return TrackResolver(catalogue, failure_db, rate_limit=1000, max_concurrency=10, backoff=(0, 0))


def resolve(resolver, spotify_tracks, existing=()):
    return asyncio.run(resolver.resolve(spotify_tracks, existing, label="test"))


def test_existing_tidal_tracks_resolve_without_searching(failure_db):
    catalogue = FakeCatalogue()
    existing = [tidal_track(11, "Song A", ["Artist"]), tidal_track(12, "Other", ["X"], isrc="ISRC2")]
    tracks = [spotify_track("a", "Song A", ["Artist"]), spotify_track("b", "Renamed", ["Y"], isrc="ISRC2")]

    result = resolve(make_resolver(catalogue, failure_db), tracks, existing)

    assert result.tidal_ids == [11, 12]
    assert result.not_found == []
    assert catalogue.queries == []


def test_album_search_picks_track_by_track_number(failure_db):
    wanted = tidal_track(22, "Second", ["Artist"])
    album = tidal_album("Album", ["Artist"], [tidal_track(21, "First", ["Artist"]), wanted])
    catalogue = FakeCatalogue(albums=[album])

    result = resolve(make_resolver(catalogue, failure_db), [spotify_track("s", "Second", ["Artist"], track_number=2)])

    assert result.tidal_ids == [22]
    assert catalogue.queries == [('album', "Album Artist")]


def test_falls_back_to_track_search(failure_db):
    catalogue = FakeCatalogue(albums=[], tracks=[tidal_track(31, "Song (feat. Guest)", ["Artist", "Guest"])])

    result = resolve(make_resolver(catalogue, failure_db), [spotify_track("s", "Song - Radio Edit", ["Artist"])])

    assert result.tidal_ids == [31]
    assert [kind for kind, _ in catalogue.queries] == ['album', 'track']


def test_match_rules_reject_remix_and_wrong_duration(failure_db):
    catalogue = FakeCatalogue(tracks=[
        tidal_track(41, "Song", ["Artist"], version="Remix"),
        tidal_track(42, "Song", ["Artist"], duration=260),
    ])

    result = resolve(make_resolver(catalogue, failure_db), [spotify_track("s", "Song", ["Artist"])])

    assert result.tidal_ids == []
    assert [t['id'] for t in result.not_found] == ["s"]


def test_match_failure_is_remembered_across_runs(failure_db):
    tracks = [spotify_track("missing", "Nowhere", ["Nobody"])]
    first = resolve(make_resolver(FakeCatalogue(), failure_db), tracks)
    assert [t['id'] for t in first.not_found] == ["missing"]

    catalogue = FakeCatalogue()
    second = resolve(make_resolver(catalogue, failure_db), tracks)
    assert second.not_found == []  # only tracks searched in this run are reported
    assert catalogue.queries == []


def test_matches_are_shared_between_playlists(failure_db):
    catalogue = FakeCatalogue(tracks=[tidal_track(51, "Hit", ["Artist"])])
    resolver = make_resolver(catalogue, failure_db)
    track = spotify_track("s", "Hit", ["Artist"])

    assert resolve(resolver, [track]).tidal_ids == [51]
    searches = len(catalogue.queries)
    assert resolve(resolver, [track]).tidal_ids == [51]
    assert len(catalogue.queries) == searches


def test_duplicates_are_dropped_and_reported(failure_db):
    existing = [tidal_track(61, "Hit", ["Artist"])]
    tracks = [spotify_track("a", "Hit", ["Artist"]), spotify_track("b", "Hit", ["Artist"])]

    result = resolve(make_resolver(FakeCatalogue(), failure_db), tracks, existing)

    assert result.tidal_ids == [61]
    assert [t['id'] for t in result.duplicates] == ["b"]


def test_local_files_without_id_are_skipped(failure_db):
    catalogue = FakeCatalogue()
    result = resolve(make_resolver(catalogue, failure_db), [spotify_track(None, "Local", ["Me"])])
    assert result.tidal_ids == [] and result.not_found == []
    assert catalogue.queries == []


def test_transient_search_errors_are_retried(failure_db):
    catalogue = FakeCatalogue(tracks=[tidal_track(71, "Song", ["Artist"])], failures=1)
    result = resolve(make_resolver(catalogue, failure_db), [spotify_track("s", "Song", ["Artist"])])
    assert result.tidal_ids == [71]
