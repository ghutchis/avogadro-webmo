"""What the cache keeps, what it refuses to keep, and what it drops."""

import json

import pytest

from avogadro_webmo import cache

CFG = {"url": "https://host.example/cgi-bin/webmo/rest.cgi", "username": "guest"}


def done(number, name="X"):
    return {"jobNumber": number, "jobName": name, "jobStatus": "complete"}


@pytest.fixture
def memo(tmp_path):
    return cache.JobCache(tmp_path / "jobs.json")


def test_a_finished_job_is_remembered(memo):
    memo.put(1, done(1))
    assert memo.get(1) == done(1)
    assert memo.hits == 1


def test_numbers_and_strings_reach_the_same_entry(memo):
    memo.put(1963207, done(1963207))
    assert memo.get("1963207") is not None


def test_an_unfinished_job_is_not_remembered(memo):
    memo.put(2, {"jobNumber": 2, "jobStatus": "running"})
    assert memo.get(2) is None
    # ...so it is asked about again on the next listing.
    assert memo.misses == 1


def test_a_failed_job_counts_as_finished(memo):
    memo.put(3, {"jobNumber": 3, "jobStatus": "failed"})
    assert memo.get(3) is not None


def test_the_cache_is_per_server_and_per_user():
    other_user = dict(CFG, username="someone")
    other_host = dict(CFG, url="https://elsewhere.example/cgi-bin/webmo/rest.cgi")
    paths = {
        cache.cache_path(CFG),
        cache.cache_path(other_user),
        cache.cache_path(other_host),
    }
    assert len(paths) == 3


def test_two_installs_on_one_host_do_not_share_a_file():
    a = dict(CFG, url="https://host.example/one/cgi-bin/webmo/rest.cgi")
    b = dict(CFG, url="https://host.example/two/cgi-bin/webmo/rest.cgi")
    assert cache.cache_path(a) != cache.cache_path(b)


def test_a_round_trip_through_disk(tmp_path):
    path = tmp_path / "jobs.json"
    memo = cache.JobCache(path)
    memo.put(7, done(7, "benzene"))
    memo.save()

    reopened = cache.JobCache(path, json.loads(path.read_text()))
    assert reopened.get(7)["jobName"] == "benzene"


def test_an_unreadable_cache_is_discarded_not_raised(tmp_path, monkeypatch):
    path = tmp_path / "webmo" / "jobs.json"
    path.parent.mkdir(parents=True)
    path.write_text("{ this is not json")
    monkeypatch.setattr(cache, "cache_path", lambda cfg: path)
    assert cache.JobCache.load(CFG).entries == {}


def test_saving_where_it_cannot_write_is_survivable(tmp_path):
    # A directory where the file should be: write() fails, nothing raises.
    path = tmp_path / "jobs.json"
    path.mkdir()
    memo = cache.JobCache(path)
    memo.put(1, done(1))
    memo.save()


def test_eviction_keeps_the_newest(monkeypatch, tmp_path):
    monkeypatch.setattr(cache, "MAX_ENTRIES", 3)
    memo = cache.JobCache(tmp_path / "jobs.json")
    for number in range(10, 20):
        memo.put(number, done(number))
    memo.save()

    kept = sorted(int(number) for number in memo.entries)
    assert kept == [17, 18, 19]


def test_saving_an_untouched_cache_writes_nothing(tmp_path):
    path = tmp_path / "jobs.json"
    memo = cache.JobCache(path)
    memo.get(1)
    memo.save()
    assert not path.exists()
