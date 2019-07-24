import pytest

import worker_health


@pytest.fixture
def wh_instance():
    return worker_health.WorkerHealth()


def test_make_list_unique(wh_instance):
    a = [1, 2, 3, 1, 1, 1, 1]
    output = wh_instance.make_list_unique(a)
    assert output == [1, 2, 3]


def test_flatten_list(wh_instance):
    a = [[1, 2], [1, 2], [3, 4]]
    output = wh_instance.flatten_list(a)
    assert output == [1, 2, 1, 2, 3, 4]


def test_flatten_dict(wh_instance):
    a = {
        "pixel2-perf-2": ["pixel2-33", "pixel2-54", "pixel2-37"],
        "gecko-t-bitbar-gw-unit-p2": [],
        "gecko-t-bitbar-gw-perf-p2": [],
        "gecko-t-bitbar-gw-perf-g5": [],
        "gecko-t-bitbar-gw-batt-p2": [],
        "gecko-t-bitbar-gw-batt-g5": [],
    }
    output = wh_instance.flatten_dict(a)
    assert output == ["pixel2-33", "pixel2-37", "pixel2-54"]


def test_dict_merge_with_dedupe(wh_instance):
    a = {"a": [3, 1, 2, 3], "b": [4, 5, 6]}
    b = {"a": [1, 3], "b": [9]}
    c = {"a": [1, 2, 3], "b": [4, 5, 6, 9]}
    result = wh_instance.dict_merge_with_dedupe(a, b)
    assert c == result


def test_dict_merge_with_dedupe2(wh_instance):
    a = {"b": [4, 5, 6]}
    b = {"a": [1, 3]}
    c = {"a": [1, 3], "b": [4, 5, 6]}
    result = wh_instance.dict_merge_with_dedupe(a, b)
    assert c == result
