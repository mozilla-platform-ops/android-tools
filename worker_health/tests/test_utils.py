import pytest
import requests

from urllib.error import URLError

from worker_health import utils


def test_consecutive_non_ones_from_end():
    test_data = [1, 0, 1, 1, 1, 0]  # should be 1
    test_data_2 = [1, 0, 0, 0]  # should be 3s

    assert utils.consecutive_non_ones_from_end(test_data) == 1
    assert utils.consecutive_non_ones_from_end(test_data_2) == 3


def test_graph_percentage():
    assert utils.graph_percentage(0.5) == "[=====     ]"
    assert utils.graph_percentage(1) == "[==========]"
    assert utils.graph_percentage(0) == "[          ]"


def test_fetch_url():
    url, res, exc = utils.fetch_url("http://badurl.comaaa/bad")
    assert isinstance(exc, URLError)


def test_get_jsonc2():
    with pytest.raises(requests.exceptions.ConnectionError):
        url, res, exc = utils.get_jsonc2("http://badurl.comaaa/bad")
