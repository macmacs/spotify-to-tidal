""" Profile: the local files (config, Tidal login, caches, reports) that belong to one user of the tool """
import os
from dataclasses import dataclass

import yaml

from .cache import MatchFailureDatabase


def _for_user(path: str, user: str | None) -> str:
    """ 'dir/name.ext' -> 'dir/name.<user>.ext'; unchanged for the default profile """
    if user is None:
        return path
    directory, filename = os.path.split(path)
    root, ext = os.path.splitext(filename)
    return os.path.join(directory, f"{root}.{user}{ext}")


@dataclass(frozen=True)
class Profile:
    """
    user=None is the default profile and uses the historical, unsuffixed file names.
    Any other user gets its own copy of every file, e.g. config.yml -> config.<user>.yml.
    """
    user: str | None = None
    config_path: str = 'config.yml'

    def __post_init__(self):
        if self.user is not None and (not self.user or os.sep in self.user or '/' in self.user):
            raise ValueError(f"Invalid profile user name: {self.user!r}")

    @property
    def config_file(self) -> str:
        return _for_user(self.config_path, self.user)

    @property
    def tidal_session_file(self) -> str:
        return _for_user('.session.yml', self.user)

    @property
    def failure_db_file(self) -> str:
        return _for_user('.cache.db', self.user)

    @property
    def not_found_report_file(self) -> str:
        return _for_user('songs not found.txt', self.user)

    def load_config(self) -> dict:
        with open(self.config_file, 'r') as f:
            return yaml.safe_load(f)

    def open_failure_cache(self) -> MatchFailureDatabase:
        return MatchFailureDatabase(self.failure_db_file)
