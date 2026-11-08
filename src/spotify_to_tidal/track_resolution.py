""" Track resolution: find the Tidal track corresponding to each Spotify track """
import asyncio
import datetime
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import List, Protocol, Sequence, Set
import unicodedata

import tidalapi
from tqdm.asyncio import tqdm as atqdm

from .cache import MatchFailureDatabase, TrackMatchCache
from .paging import BACKOFF_SECONDS, retry
from .type import spotify as t_spotify


class TidalCatalogue(Protocol):
    """
    Tidal search, as seen by track resolution.
    Albums expose name, artists, num_tracks and tracks(); tracks expose id, name, version, isrc, duration, artists, available.
    Both methods are blocking and may raise the transient errors handled by paging.retry.
    """
    def search_albums(self, query: str) -> Sequence[tidalapi.Album]: ...
    def search_tracks(self, query: str) -> Sequence[tidalapi.Track]: ...


class TidalSessionCatalogue:
    """ TidalCatalogue adapter backed by a logged-in tidalapi session """
    def __init__(self, session: tidalapi.Session):
        self.session = session

    def search_albums(self, query: str) -> Sequence[tidalapi.Album]:
        return self.session.search(query, models=[tidalapi.album.Album])['albums']

    def search_tracks(self, query: str) -> Sequence[tidalapi.Track]:
        return self.session.search(query, models=[tidalapi.media.Track])['tracks']


@dataclass
class Resolution:
    tidal_ids: List[int] = field(default_factory=list)
    """ Tidal track id for each resolved Spotify track, in Spotify order, without duplicates """
    not_found: List[t_spotify.SpotifyTrack] = field(default_factory=list)
    """ Spotify tracks searched for in this run without finding a match """
    duplicates: List[t_spotify.SpotifyTrack] = field(default_factory=list)
    """ Spotify tracks dropped because an earlier track resolved to the same Tidal track """


class TrackResolver:
    """
    Resolves Spotify tracks to Tidal tracks.
    Matches are remembered for the lifetime of the resolver (so a track shared by several playlists is searched once),
    and failed searches are recorded in the match failure database so they are not retried on every run.
    """
    def __init__(self, catalogue: TidalCatalogue, failure_cache: MatchFailureDatabase,
                 match_cache: TrackMatchCache | None = None,
                 rate_limit: float = 10, max_concurrency: int = 10, backoff: Sequence[float] = BACKOFF_SECONDS):
        self.catalogue = catalogue
        self.failure_cache = failure_cache
        self.match_cache = match_cache if match_cache is not None else TrackMatchCache()
        self.rate_limit = rate_limit
        self.max_concurrency = max_concurrency
        self.backoff = backoff

    async def resolve(self, spotify_tracks: Sequence[t_spotify.SpotifyTrack],
                      existing_tidal_tracks: Sequence[tidalapi.Track] = (), label: str = "") -> Resolution:
        """
        Resolve spotify_tracks, preferring matches among existing_tidal_tracks (e.g. the current contents of the
        target Tidal playlist) and searching the Tidal catalogue for the rest.
        """
        self._prefill_from_existing(spotify_tracks, existing_tidal_tracks)
        not_found = await self._search_unresolved(spotify_tracks, label)

        resolution = Resolution(not_found=not_found)
        seen: Set[int] = set()
        for spotify_track in spotify_tracks:
            if not spotify_track['id']:
                continue
            tidal_id = self.match_cache.get(spotify_track['id'])
            if not tidal_id:
                continue
            if tidal_id in seen:
                resolution.duplicates.append(spotify_track)
            else:
                resolution.tidal_ids.append(tidal_id)
                seen.add(tidal_id)
        return resolution

    def _prefill_from_existing(self, spotify_tracks_: Sequence[t_spotify.SpotifyTrack], tidal_tracks_: Sequence[tidalapi.Track]):
        """ Remember matches between the Spotify tracks and the Tidal tracks already present, one-to-one where possible """
        spotify_tracks = list(spotify_tracks_)
        tidal_tracks = list(tidal_tracks_)

        # first match each Tidal track to one Spotify track
        for tidal_track in tidal_tracks:
            for idx, spotify_track in enumerate(spotify_tracks):
                if tidal_track.available and match(tidal_track, spotify_track):
                    self.match_cache.insert((spotify_track['id'], tidal_track.id))
                    spotify_tracks.pop(idx)
                    break
        # then match the Spotify tracks left over (to account for many-to-one style mappings)
        for spotify_track in spotify_tracks:
            for idx, tidal_track in enumerate(tidal_tracks):
                if tidal_track.available and match(tidal_track, spotify_track):
                    self.match_cache.insert((spotify_track['id'], tidal_track.id))
                    tidal_tracks.pop(idx)
                    break

    def _needs_search(self, spotify_track: t_spotify.SpotifyTrack) -> bool:
        track_id = spotify_track['id']
        return bool(track_id) and not self.match_cache.get(track_id) and not self.failure_cache.has_match_failure(track_id)

    async def _search_unresolved(self, spotify_tracks: Sequence[t_spotify.SpotifyTrack], label: str) -> List[t_spotify.SpotifyTrack]:
        """ Search the catalogue for every track not yet resolved, returning the tracks that could not be found """
        tracks_to_search = [t for t in spotify_tracks if self._needs_search(t)]
        if not tracks_to_search:
            return []

        desc = "Searching Tidal for {}/{} tracks in Spotify playlist '{}'".format(len(tracks_to_search), len(spotify_tracks), label)
        semaphore = asyncio.Semaphore(self.max_concurrency)
        rate_limiter_task = asyncio.create_task(self._run_rate_limiter(semaphore))
        try:
            results = await atqdm.gather(*[self._search(t, semaphore) for t in tracks_to_search], desc=desc)
        finally:
            rate_limiter_task.cancel()

        not_found = []
        for spotify_track, tidal_track in zip(tracks_to_search, results):
            if tidal_track:
                self.match_cache.insert((spotify_track['id'], tidal_track.id))
                self.failure_cache.remove_match_failure(spotify_track['id'])
            else:
                self.failure_cache.cache_match_failure(spotify_track['id'])
                not_found.append(spotify_track)
        return not_found

    async def _run_rate_limiter(self, semaphore: asyncio.Semaphore):
        ''' Leaky bucket algorithm for rate limiting. Periodically releases items from semaphore at rate_limit '''
        sleep_time = self.max_concurrency / self.rate_limit / 4  # aim to sleep approx time to drain 1/4 of 'bucket'
        t0 = datetime.datetime.now()
        while True:
            await asyncio.sleep(sleep_time)
            t = datetime.datetime.now()
            new_items = round(self.rate_limit * (t - t0).total_seconds())
            t0 = t
            for _ in range(new_items):
                semaphore.release()  # leak new_items from the 'bucket'

    async def _search(self, spotify_track: t_spotify.SpotifyTrack, semaphore: asyncio.Semaphore) -> tidalapi.Track | None:
        await semaphore.acquire()
        track = await retry(self._search_in_album, spotify_track, backoff=self.backoff)
        if track:
            return track
        await semaphore.acquire()
        return await retry(self._search_standalone, spotify_track, backoff=self.backoff)

    def _search_in_album(self, spotify_track: t_spotify.SpotifyTrack) -> tidalapi.Track | None:
        """ search for album name and first album artist, then pick the track by track number """
        album = spotify_track.get('album')
        if not (album and album.get('artists')):
            return None
        query = simple(album['name']) + " " + simple(album['artists'][0]['name'])
        for tidal_album in self.catalogue.search_albums(query):
            if tidal_album.num_tracks >= spotify_track['track_number'] and album_match(album, tidal_album):
                album_tracks = tidal_album.tracks()
                if len(album_tracks) < spotify_track['track_number']:
                    continue  # incorrect metadata :(
                track = album_tracks[spotify_track['track_number'] - 1]
                if match(track, spotify_track):
                    return track
        return None

    def _search_standalone(self, spotify_track: t_spotify.SpotifyTrack) -> tidalapi.Track | None:
        """ if album search fails then search for track name and first artist """
        query = simple(spotify_track['name']) + ' ' + simple(spotify_track['artists'][0]['name'])
        for track in self.catalogue.search_tracks(query):
            if match(track, spotify_track):
                return track
        return None


# ---- match rules ----

def normalize(s) -> str:
    return unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode('ascii')

def simple(input_string: str) -> str:
    # only take the first part of a string before any hyphens or brackets to account for different versions
    return input_string.split('-')[0].strip().split('(')[0].strip().split('[')[0].strip()

def isrc_match(tidal_track: tidalapi.Track, spotify_track) -> bool:
    if "isrc" in spotify_track["external_ids"]:
        return tidal_track.isrc == spotify_track["external_ids"]["isrc"]
    return False

def duration_match(tidal_track: tidalapi.Track, spotify_track, tolerance=2) -> bool:
    # the duration of the two tracks must be the same to within 2 seconds
    return abs(tidal_track.duration - spotify_track['duration_ms']/1000) < tolerance

def name_match(tidal_track, spotify_track) -> bool:
    def exclusion_rule(pattern: str, tidal_track: tidalapi.Track, spotify_track: t_spotify.SpotifyTrack):
        spotify_has_pattern = pattern in spotify_track['name'].lower()
        tidal_has_pattern = pattern in tidal_track.name.lower() or (not tidal_track.version is None and (pattern in tidal_track.version.lower()))
        return spotify_has_pattern != tidal_has_pattern

    # handle some edge cases
    if exclusion_rule("instrumental", tidal_track, spotify_track): return False
    if exclusion_rule("acapella", tidal_track, spotify_track): return False
    if exclusion_rule("remix", tidal_track, spotify_track): return False

    # the simplified version of the Spotify track name must be a substring of the Tidal track name
    # Try with both un-normalized and then normalized
    simple_spotify_track = simple(spotify_track['name'].lower()).split('feat.')[0].strip()
    return simple_spotify_track in tidal_track.name.lower() or normalize(simple_spotify_track) in normalize(tidal_track.name.lower())

def artist_match(tidal: tidalapi.Track | tidalapi.Album, spotify) -> bool:
    def split_artist_name(artist: str) -> Sequence[str]:
       if '&' in artist:
           return artist.split('&')
       elif ',' in artist:
           return artist.split(',')
       else:
           return [artist]

    def get_tidal_artists(tidal: tidalapi.Track | tidalapi.Album, do_normalize=False) -> Set[str]:
        result: list[str] = []
        for artist in tidal.artists:
            if do_normalize:
                artist_name = normalize(artist.name)
            else:
                artist_name = artist.name
            result.extend(split_artist_name(artist_name))
        return set([simple(x.strip().lower()) for x in result])

    def get_spotify_artists(spotify, do_normalize=False) -> Set[str]:
        result: list[str] = []
        for artist in spotify['artists']:
            if do_normalize:
                artist_name = normalize(artist['name'])
            else:
                artist_name = artist['name']
            result.extend(split_artist_name(artist_name))
        return set([simple(x.strip().lower()) for x in result])
    # There must be at least one overlapping artist between the Tidal and Spotify track
    # Try with both un-normalized and then normalized
    if get_tidal_artists(tidal).intersection(get_spotify_artists(spotify)) != set():
        return True
    return get_tidal_artists(tidal, True).intersection(get_spotify_artists(spotify, True)) != set()

def match(tidal_track, spotify_track) -> bool:
    if not spotify_track['id']: return False
    return isrc_match(tidal_track, spotify_track) or (
        duration_match(tidal_track, spotify_track)
        and name_match(tidal_track, spotify_track)
        and artist_match(tidal_track, spotify_track)
    )

def album_match(spotify_album, tidal_album, threshold=0.6) -> bool:
    return SequenceMatcher(None, simple(spotify_album['name']), simple(tidal_album.name)).ratio() >= threshold and artist_match(tidal_album, spotify_album)
