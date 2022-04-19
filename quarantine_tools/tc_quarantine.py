class TCQuarantine:
    def __init__(
        self,
        provisioner_id,
        worker_type,
        worker_group,
        worker_name_root,
        padding=False,
        padding_length=0,
    ):
        self.provisioner_id = provisioner_id
        self.worker_type = worker_type
        self.worker_group = worker_group
        # used for generation of the full host name
        self.worker_name_root = worker_name_root

        # host formatting options
        self.padding = padding
        self.padding_length = padding_length

    def generate_hosts(self, device_numbers):
        hosts_to_act_on = []
        for h in device_numbers:
            if self.padding:
                if self.padding_length == 3:
                    # t-linux64-ms-
                    hosts_to_act_on.append("%s%03d" % (self.worker_name_root, h))
                else:
                    raise "not implemented yet!"
            else:
                hosts_to_act_on.append("%s%s" % (self.worker_name_root, h))

    def quarantine(self, quarantine_until, device_numbers):
        pass

    def lift_quarantine(self, device_numbers):
        # calls quarantine with a date in the past
        pass


BitbarP2UnitQuarantine = TCQuarantine(
    "proj-autophone", "gecko-t-bitbar-gw-unit-p2", "bitbar"
)
