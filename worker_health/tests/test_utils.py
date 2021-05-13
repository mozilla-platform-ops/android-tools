from worker_health import utils


def test_consecutive_non_ones_from_end():
    test_data = [1, 0, 1, 1, 1, 0]  # should be 1
    test_data_2 = [1, 0, 0, 0]  # should be 3s

    assert utils.consecutive_non_ones_from_end(test_data) == 1
    assert utils.consecutive_non_ones_from_end(test_data_2) == 3
