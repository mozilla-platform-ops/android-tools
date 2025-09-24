from worker_health import utils


def get_worker_types(provisioner, verbosity):
    # https://queue.taskcluster.net/v1/provisioners/proj-autophone/worker-types?limit=100
    return utils.get_jsonc(
        "https://firefox-ci-tc.services.mozilla.com/api/queue/v1/provisioners/%s/worker-types?limit=100"
        # "https://queue.taskcluster.net/v1/provisioners/%s/worker-types?limit=100"
        % provisioner,
        verbosity,
    )
