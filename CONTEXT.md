# spotify_to_tidal

Copies a user's Spotify playlists and favorites into their Tidal account, matching each Spotify track to the same recording on Tidal.

## Language

### Profiles

**Profile**:
One person's own config, Tidal login, match failures and not-found report, kept apart from every other profile on the same machine. The default profile has no name.
_Avoid_: user, account (both clash with Spotify and Tidal accounts)

### Syncing

**Sync**:
One run that copies the selected Spotify playlists and/or favorites into Tidal. Never deletes Tidal favorites.
_Avoid_: migration, import, transfer

**Favorites**:
The user's saved tracks: "Liked Songs" on Spotify, favorite tracks on Tidal.
_Avoid_: saved tracks, likes, library

**Playlist mapping**:
A pair of one Spotify playlist and the Tidal playlist it is synced into (matched by name, or given explicitly in the config). The Tidal side may not exist yet.
_Avoid_: playlist pair, link

### Matching

**Track resolution**:
Finding the Tidal track that corresponds to each Spotify track, first among tracks already on Tidal, then by searching the Tidal catalogue.
_Avoid_: lookup, search (search is only one step of resolution)

**Track match**:
A Spotify track and a Tidal track judged to be the same recording: same ISRC, or same duration, name and at least one artist.
_Avoid_: mapping, hit

**Match failure**:
A Spotify track for which no Tidal track was found. Remembered between runs so the track is not searched again until its retry time.
_Avoid_: miss, 404, song not found

**Duplicate**:
A Spotify track whose track match is a Tidal track already used earlier in the same playlist; it is left out.

**Tidal catalogue**:
Everything searchable on Tidal (albums and tracks), as opposed to what is already in the user's Tidal playlists or favorites.
_Avoid_: Tidal API, Tidal library
