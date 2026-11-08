#!/usr/bin/env python3

import asyncio
from typing import List, Mapping, Sequence
import spotipy
import tidalapi
from .tidalapi_patch import add_multiple_tracks_to_playlist, clear_tidal_playlist, get_all_favorites, get_all_playlists, get_all_playlist_tracks
from .paging import Page, fetch_all
from .track_resolution import Resolution, TrackResolver
from tqdm import tqdm

from .type import spotify as t_spotify

def _spotify_track_page(result) -> Page:
    """ Converts one page of Spotify playlist items / saved tracks into a Page of tracks """
    return Page(items=[item['track'] for item in result['items'] if item['track'] is not None], total=result['total'], limit=result['limit'])


async def get_tracks_from_spotify_playlist(spotify_session: spotipy.Spotify, spotify_playlist):
    def _get_tracks_from_spotify_playlist(offset: int) -> Page:
        fields = "next,total,limit,items(track(name,album(name,artists),artists,track_number,duration_ms,id,external_ids(isrc))),type"
        return _spotify_track_page(spotify_session.playlist_tracks(playlist_id=spotify_playlist["id"], fields=fields, offset=offset))

    print(f"Loading tracks from Spotify playlist '{spotify_playlist['name']}'")
    items = await fetch_all(_get_tracks_from_spotify_playlist)
    track_filter = lambda item: item.get('type', 'track') == 'track' # type may be 'episode' also
    sanity_filter = lambda item: ('album' in item
                                  and 'name' in item['album']
                                  and 'artists' in item['album']
                                  and len(item['album']['artists']) > 0
                                  and item['album']['artists'][0]['name'] is not None)
    return list(filter(sanity_filter, filter(track_filter, items)))

def _describe(spotify_track: t_spotify.SpotifyTrack) -> str:
    return f"{spotify_track['id']}: {','.join([a['name'] for a in spotify_track['artists']])} - {spotify_track['name']}"

def report_duplicates(resolution: Resolution):
    for spotify_track in resolution.duplicates:
        artist_names = ', '.join([artist['name'] for artist in spotify_track['artists']])
        print(f'Duplicate found: Track "{spotify_track["name"]}" by {artist_names} will be ignored')

def report_not_found(resolution: Resolution, playlist_name: str, report_file: str):
    """ Prints the tracks that could not be found and appends them to the not-found report """
    if not resolution.not_found:
        return
    lines = [_describe(t) for t in resolution.not_found]
    for line in lines:
        print('\033[91m' + "Could not find the track " + line + '\033[0m')
    header = f"==========================\nPlaylist: {playlist_name}\n==========================\n"
    with open(report_file, "a", encoding="utf-8") as file:
        file.write(header)
        for line in lines:
            file.write(f"{line}\n")

async def sync_playlist(spotify_session: spotipy.Spotify, tidal_session: tidalapi.Session, resolver: TrackResolver, spotify_playlist, tidal_playlist: tidalapi.Playlist | None, report_file: str):
    """ sync given playlist to tidal """
    # Get the tracks from both Spotify and Tidal, creating a new Tidal playlist if necessary
    spotify_tracks = await get_tracks_from_spotify_playlist(spotify_session, spotify_playlist)
    if len(spotify_tracks) == 0:
        return # nothing to do
    if tidal_playlist:
        old_tidal_tracks = await get_all_playlist_tracks(tidal_playlist)
    else:
        print(f"No playlist found on Tidal corresponding to Spotify playlist: '{spotify_playlist['name']}', creating new playlist")
        tidal_playlist =  tidal_session.user.create_playlist(spotify_playlist['name'], spotify_playlist['description'])
        old_tidal_tracks = []

    resolution = await resolver.resolve(spotify_tracks, old_tidal_tracks, label=spotify_playlist['name'])
    report_not_found(resolution, spotify_playlist['name'], report_file)
    report_duplicates(resolution)
    new_tidal_track_ids = resolution.tidal_ids

    # Update the Tidal playlist if there are changes
    old_tidal_track_ids = [t.id for t in old_tidal_tracks]
    if new_tidal_track_ids == old_tidal_track_ids:
        print("No changes to write to Tidal playlist")
    elif new_tidal_track_ids[:len(old_tidal_track_ids)] == old_tidal_track_ids:
        # Append new tracks to the existing playlist if possible
        add_multiple_tracks_to_playlist(tidal_playlist, new_tidal_track_ids[len(old_tidal_track_ids):])
    else:
        # Erase old playlist and add new tracks from scratch if any reordering occured
        clear_tidal_playlist(tidal_playlist)
        add_multiple_tracks_to_playlist(tidal_playlist, new_tidal_track_ids)

async def sync_favorites(spotify_session: spotipy.Spotify, tidal_session: tidalapi.Session, resolver: TrackResolver, report_file: str):
    """ sync user favorites to tidal """
    async def get_tracks_from_spotify_favorites() -> List[dict]:
        _get_favorite_tracks = lambda offset: _spotify_track_page(spotify_session.current_user_saved_tracks(offset=offset))
        tracks = await fetch_all(_get_favorite_tracks)
        tracks.reverse()
        return tracks

    print("Loading favorite tracks from Spotify")
    spotify_tracks = await get_tracks_from_spotify_favorites()
    print("Loading existing favorite tracks from Tidal")
    old_tidal_tracks = await get_all_favorites(tidal_session.user.favorites, order='DATE')
    resolution = await resolver.resolve(spotify_tracks, old_tidal_tracks, label="Favorites")
    report_not_found(resolution, "Favorites", report_file)

    existing_favorite_ids = set([track.id for track in old_tidal_tracks])
    new_tidal_favorite_ids = [tidal_id for tidal_id in resolution.tidal_ids if tidal_id not in existing_favorite_ids]
    if new_tidal_favorite_ids:
        for tidal_id in tqdm(new_tidal_favorite_ids, desc="Adding new tracks to Tidal favorites"):
            tidal_session.user.favorites.add_track(tidal_id)
    else:
        print("No new tracks to add to Tidal favorites")

def sync_playlists_wrapper(spotify_session: spotipy.Spotify, tidal_session: tidalapi.Session, resolver: TrackResolver, playlists, report_file: str):
  for spotify_playlist, tidal_playlist in playlists:
    # sync the spotify playlist to tidal
    asyncio.run(sync_playlist(spotify_session, tidal_session, resolver, spotify_playlist, tidal_playlist, report_file) )

def sync_favorites_wrapper(spotify_session: spotipy.Spotify, tidal_session: tidalapi.Session, resolver: TrackResolver, report_file: str):
    asyncio.run(main=sync_favorites(spotify_session, tidal_session, resolver, report_file))

def get_tidal_playlists_wrapper(tidal_session: tidalapi.Session) -> Mapping[str, tidalapi.Playlist]:
    tidal_playlists = asyncio.run(get_all_playlists(tidal_session.user))
    return {playlist.name: playlist for playlist in tidal_playlists}

def pick_tidal_playlist_for_spotify_playlist(spotify_playlist, tidal_playlists: Mapping[str, tidalapi.Playlist]):
    if spotify_playlist['name'] in tidal_playlists:
      # if there's an existing tidal playlist with the name of the current playlist then use that
      tidal_playlist = tidal_playlists[spotify_playlist['name']]
      return (spotify_playlist, tidal_playlist)
    else:
      return (spotify_playlist, None)

def get_user_playlist_mappings(spotify_session: spotipy.Spotify, tidal_session: tidalapi.Session, config):
    results = []
    spotify_playlists = asyncio.run(get_playlists_from_spotify(spotify_session, config))
    tidal_playlists = get_tidal_playlists_wrapper(tidal_session)
    for spotify_playlist in spotify_playlists:
        results.append( pick_tidal_playlist_for_spotify_playlist(spotify_playlist, tidal_playlists) )
    return results

async def get_playlists_from_spotify(spotify_session: spotipy.Spotify, config):
    # get all the playlists from the Spotify account
    def _get_playlists_page(offset: int) -> Page:
        result = spotify_session.current_user_playlists(offset=offset)
        return Page(items=result['items'], total=result['total'], limit=result['limit'])

    print("Loading Spotify playlists")
    exclude_list = set([x.split(':')[-1] for x in config.get('excluded_playlists', [])])
    playlists = await fetch_all(_get_playlists_page)
    user_id = spotify_session.current_user()['id']

    # filter out playlists that don't belong to us or are on the exclude list
    my_playlist_filter = lambda p: p and p['owner']['id'] == user_id
    exclude_filter = lambda p: not p['id'] in exclude_list
    return list(filter( exclude_filter, filter( my_playlist_filter, playlists )))

def get_playlists_from_config(spotify_session: spotipy.Spotify, tidal_session: tidalapi.Session, config):
    # get the list of playlist sync mappings from the configuration file
    def get_playlist_ids(config):
        return [(item['spotify_id'], item['tidal_id']) for item in config['sync_playlists']]
    output = []
    for spotify_id, tidal_id in get_playlist_ids(config=config):
        try:
            spotify_playlist = spotify_session.playlist(playlist_id=spotify_id)
        except spotipy.SpotifyException as e:
            print(f"Error getting Spotify playlist {spotify_id}")
            raise e
        try:
            tidal_playlist = tidal_session.playlist(playlist_id=tidal_id)
        except Exception as e:
            print(f"Error getting Tidal playlist {tidal_id}")
            raise e
        output.append((spotify_playlist, tidal_playlist))
    return output
