from typing import Callable, List
import tidalapi
from tqdm import tqdm

from .paging import Page, fetch_all

def _remove_indices_from_playlist(playlist: tidalapi.UserPlaylist, indices: List[int]):
    headers = {'If-None-Match': playlist._etag}
    index_string = ",".join(map(str, indices))
    playlist.request.request('DELETE', (playlist._base_url + '/items/%s') % (playlist.id, index_string), headers=headers)
    playlist._reparse()

def clear_tidal_playlist(playlist: tidalapi.UserPlaylist, chunk_size: int=20):
    with tqdm(desc="Erasing existing tracks from Tidal playlist", total=playlist.num_tracks) as progress:
        while playlist.num_tracks:
            indices = range(min(playlist.num_tracks, chunk_size))
            _remove_indices_from_playlist(playlist, indices)
            progress.update(len(indices))

def add_multiple_tracks_to_playlist(playlist: tidalapi.UserPlaylist, track_ids: List[int], chunk_size: int=20):
    offset = 0
    with tqdm(desc="Adding new tracks to Tidal playlist", total=len(track_ids)) as progress:
        while offset < len(track_ids):
            count = min(chunk_size, len(track_ids) - offset)
            playlist.add(track_ids[offset:offset+chunk_size])
            offset += count
            progress.update(count)

def _tidal_page_fetcher(url, session, parser, params: dict) -> Callable[[int], Page]:
    """
        Page function for a Tidal endpoint, for use with fetch_all
        The main library doesn't provide the total number of items or expose the raw json, so use this instead
    """
    def fetch_page(offset: int) -> Page:
        raw = session.request.map_request(url, params={**params, 'offset': offset})
        return Page(items=session.request.map_json(raw, parse=parser), total=raw['totalNumberOfItems'], limit=raw['limit'])
    return fetch_page

async def get_all_favorites(favorites: tidalapi.Favorites, order: str = "NAME", order_direction: str = "ASC", chunk_size: int=100) -> List[tidalapi.Track]:
    """ Get all favorites from Tidal playlist in chunks """
    params = {
        "limit": chunk_size,
        "order": order,
        "orderDirection": order_direction,
    }
    return await fetch_all(_tidal_page_fetcher(f"{favorites.base_url}/tracks", session=favorites.session, parser=favorites.session.parse_track, params=params))

async def get_all_playlists(user: tidalapi.User, chunk_size: int=10) -> List[tidalapi.Playlist]:
    """ Get all user playlists from Tidal in chunks """
    print(f"Loading playlists from Tidal user")
    params = {
        "limit": chunk_size,
    }
    return await fetch_all(_tidal_page_fetcher(f"users/{user.id}/playlists", session=user.session, parser=user.playlist.parse_factory, params=params))

async def get_all_playlist_tracks(playlist: tidalapi.Playlist, chunk_size: int=20) -> List[tidalapi.Track]:
    """ Get all tracks from Tidal playlist in chunks """
    params = {
        "limit": chunk_size,
    }
    print(f"Loading tracks from Tidal playlist '{playlist.name}'")
    return await fetch_all(_tidal_page_fetcher(f"{playlist._base_url%playlist.id}/tracks", session=playlist.session, parser=playlist.session.parse_track, params=params))
