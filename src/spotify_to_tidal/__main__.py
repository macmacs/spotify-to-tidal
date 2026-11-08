import yaml
import argparse
import sys

from . import sync as _sync
from . import auth as _auth
from . import cache as _cache
from .track_resolution import TidalSessionCatalogue, TrackResolver

def get_user_specific_filename(base_filename: str, username: str = None) -> str:
    """Generate user-specific filename with .username suffix before extension"""
    if username is None:
        return base_filename
    
    if '.' in base_filename:
        name, ext = base_filename.rsplit('.', 1)
        return f"{name}.{username}.{ext}"
    else:
        return f"{base_filename}.{username}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config.yml', help='location of the config file')
    parser.add_argument('--user', help='username for user-specific config files and artifacts')
    parser.add_argument('--uri', help='synchronize a specific URI instead of the one in the config')
    parser.add_argument('--sync-favorites', action=argparse.BooleanOptionalAction, help='synchronize the favorites')
    args = parser.parse_args()

    # Use user-specific config file if --user is provided
    if args.user:
        config_file = get_user_specific_filename(args.config, args.user)
    else:
        config_file = args.config

    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    print("Opening Spotify session")
    spotify_session = _auth.open_spotify_session(config['spotify'])
    print("Opening Tidal session")
    tidal_session = _auth.open_tidal_session(username=args.user)
    if not tidal_session.check_login():
        sys.exit("Could not connect to Tidal")
    resolver = TrackResolver(TidalSessionCatalogue(tidal_session),
                             failure_cache=_cache.MatchFailureDatabase(username=args.user),
                             rate_limit=config.get('rate_limit', 10),
                             max_concurrency=config.get('max_concurrency', 10))
    report_file = get_user_specific_filename("songs not found.txt", args.user)
    if args.uri:
        # if a playlist ID is explicitly provided as a command line argument then use that
        spotify_playlist = spotify_session.playlist(args.uri)
        tidal_playlists = _sync.get_tidal_playlists_wrapper(tidal_session)
        tidal_playlist = _sync.pick_tidal_playlist_for_spotify_playlist(spotify_playlist, tidal_playlists)
        _sync.sync_playlists_wrapper(spotify_session, tidal_session, resolver, [tidal_playlist], report_file)
        sync_favorites = args.sync_favorites # only sync favorites if command line argument explicitly passed
    elif args.sync_favorites:
        sync_favorites = True # sync only the favorites
    elif config.get('sync_playlists', None):
        # if the config contains a sync_playlists list of mappings then use that
        _sync.sync_playlists_wrapper(spotify_session, tidal_session, resolver, _sync.get_playlists_from_config(spotify_session, tidal_session, config), report_file)
        sync_favorites = args.sync_favorites is None and config.get('sync_favorites_default', True)
    else:
        # otherwise sync all the user playlists in the Spotify account and favorites unless explicitly disabled
        _sync.sync_playlists_wrapper(spotify_session, tidal_session, resolver, _sync.get_user_playlist_mappings(spotify_session, tidal_session, config), report_file)
        sync_favorites = args.sync_favorites is None and config.get('sync_favorites_default', True)

    if sync_favorites:
        _sync.sync_favorites_wrapper(spotify_session, tidal_session, resolver, report_file)

if __name__ == '__main__':
    main()
    sys.exit(0)
