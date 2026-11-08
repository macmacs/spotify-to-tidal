A command line tool for importing your Spotify playlists into Tidal. Due to various performance optimisations, it is particularly suited for periodic synchronisation of very large collections.

Installation
-----------
Clone this git repository and then run:

```bash
python3 -m pip install -e .
```

Or let a setup script create a virtual environment for you, see [SETUP.md](SETUP.md).

Setup
-----
0. Copy the file config.example.yml to config.yml (or to config.NAME.yml and run with `--user NAME` to keep a separate profile)
0. Go [here](https://developer.spotify.com/documentation/general/guides/authorization/app-settings/) and register a new app on developer.spotify.com.
0. Copy and paste your client ID and client secret to the Spotify part of the config file
0. Copy and paste the value in 'redirect_uri' of the config file to Redirect URIs at developer.spotify.com and press ADD
0. Enter your Spotify username to the config file

Usage
----
To synchronize all of your Spotify playlists with your Tidal account run the following from the project root directory
Windows ignores python module paths by default, but you can run them using `python3 -m spotify_to_tidal`

```bash
spotify_to_tidal
```

You can also just synchronize a specific playlist by doing the following:

```bash
spotify_to_tidal --uri 1ABCDEqsABCD6EaABCDa0a # accepts playlist id or full playlist uri
```

or sync just your 'Liked Songs' with:

```bash
spotify_to_tidal --sync-favorites
```

See config.example.yml for more configuration options, and `spotify_to_tidal --help` for more options.

Multiple profiles
----
Several people can share one checkout by giving each a profile with `--user NAME`. Every file the tool reads or writes then gets the name added before its extension (`--config` paths too: `--config conf/config.yml --user NAME` reads `conf/config.NAME.yml`):

| File | Default profile | `--user NAME` |
|---|---|---|
| Config | `config.yml` | `config.NAME.yml` |
| Tidal login | `.session.yml` | `.session.NAME.yml` |
| Match failure cache | `.cache.db` | `.cache.NAME.db` |
| Not-found report | `songs not found.txt` | `songs not found.NAME.txt` |

```bash
spotify_to_tidal --user NAME
```

Generated files
----
- `.session.yml`: your Tidal login. Written after the first login in the browser and reused on later runs. `.session.example.yml` shows the format, you only need to write it by hand to copy a login to another machine.
- `.cache.db`: tracks that could not be found on Tidal. They are not searched again for about a week, which keeps later syncs fast.
- `songs not found.txt`: the tracks that could not be found, grouped by playlist. Appended to on every run.

These files and your config files are ignored by git, so your credentials stay out of the repository.

Development
----
Run the tests from the project root with:

```bash
python3 -m pytest
```

---

#### Join our amazing community as a code contributor
<br><br>
<a href="https://github.com/spotify2tidal/spotify_to_tidal/graphs/contributors">
  <img class="dark-light" src="https://contrib.rocks/image?repo=spotify2tidal/spotify_to_tidal&anon=0&columns=25&max=100&r=true" />
</a>
