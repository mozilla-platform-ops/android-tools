from worker_health import utils


# extracted functions from Fitness
class TCHelper:
    def __init__(
        self,
        provisioner,
        log_level=0,
    ):
        self.args = None
        self.provisioner = provisioner
        self.log_level = log_level

    def get_worker_jobs(self, queue, worker_type, worker):
        # TODO: need to get worker-group...
        url = (
            "https://firefox-ci-tc.services.mozilla.com/api/queue/v1/provisioners/%s/worker-types/%s/workers/%s/%s"
            % (self.provisioner, queue, worker_type, worker)
        )
        # print(url)
        return utils.get_jsonc(url, self.log_level)

    def get_task_status(self, taskid):
        _url, output, exception = utils.get_jsonc2(
            "https://firefox-ci-tc.services.mozilla.com/api/queue/v1/task/%s/status"
            % taskid
            # "https://queue.taskcluster.net/v1/task/%s/status" % taskid
        )
        return taskid, output, exception
