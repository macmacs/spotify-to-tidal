# tests/unit/test_profile.py

import pytest
import yaml

from spotify_to_tidal.profile import Profile


def test_default_profile_keeps_historical_file_names():
    profile = Profile()
    assert profile.config_file == "config.yml"
    assert profile.tidal_session_file == ".session.yml"
    assert profile.failure_db_file == ".cache.db"
    assert profile.not_found_report_file == "songs not found.txt"


def test_user_profile_suffixes_every_file():
    profile = Profile(user="max")
    assert profile.config_file == "config.max.yml"
    assert profile.tidal_session_file == ".session.max.yml"
    assert profile.failure_db_file == ".cache.max.db"
    assert profile.not_found_report_file == "songs not found.max.txt"


@pytest.mark.parametrize("config_path, expected", [
    ("conf/config.yml", "conf/config.max.yml"),
    ("../my.conf/config", "../my.conf/config.max"),
    ("config", "config.max"),
])
def test_user_config_path_keeps_its_directory(config_path, expected):
    assert Profile(user="max", config_path=config_path).config_file == expected


@pytest.mark.parametrize("user", ["", "a/b", "../x"])
def test_rejects_user_names_that_are_not_a_plain_name(user):
    with pytest.raises(ValueError):
        Profile(user=user)


def test_profiles_do_not_share_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yml").write_text(yaml.dump({"who": "default"}))
    (tmp_path / "config.max.yml").write_text(yaml.dump({"who": "max"}))

    default, max_ = Profile(), Profile(user="max")
    assert default.load_config() == {"who": "default"}
    assert max_.load_config() == {"who": "max"}

    max_.open_failure_cache().cache_match_failure("track")
    assert max_.open_failure_cache().has_match_failure("track")
    assert not default.open_failure_cache().has_match_failure("track")
