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
