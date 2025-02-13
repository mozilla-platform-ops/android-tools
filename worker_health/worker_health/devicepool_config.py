import os

import git
import yaml
from git.exc import GitCommandError


class DevicepoolConfig:

    def __init__(self):
        self.repo_url = "https://github.com/mozilla-platform-ops/mozilla-bitbar-devicepool.git"
        self.repo_path = os.path.expanduser("~/.cache/worker_health/mozilla-bitbar-devicepool")

        self.configured_devices = {}

        self.clone_or_update_repo()
        self.parse_config_file()

    def clone_or_update_repo(self):
        try:
            if not os.path.exists(self.repo_path):
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(self.repo_path), exist_ok=True)
                # Clone the repository
                git.Repo.clone_from(self.repo_url, self.repo_path)
            else:
                # Pull latest changes if repo exists
                repo = git.Repo(self.repo_path)
                origin = repo.remotes.origin
                origin.pull()
        except GitCommandError as e:
            print(f"Git operation failed: {e}")
            raise

    def parse_config_file(self):
        config_file_path = os.path.join(self.repo_path, "config", "config.yml")
        try:
            with open(config_file_path, "r") as file:
                config_data = yaml.safe_load(file)
        except FileNotFoundError:
            print(f"Config file not found: {config_file_path}")
        except yaml.YAMLError as e:
            print(f"Error parsing YAML file: {e}")

        for project in config_data["device_groups"]:
            # if the project contains 'test' or 'builder', skip it
            if "test" in project or "builder" in project:
                continue
            if config_data["device_groups"][project]:
                self.configured_devices[project] = list(config_data["device_groups"][project].keys())

    def get_configured_devices(self):
        return self.configured_devices
