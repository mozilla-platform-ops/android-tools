#!/usr/bin/env python

import json
import os
import requests


class QuarantineGraphQL:
    """Class for interacting with TaskCluster via GraphQL API."""

    root_url = "https://firefox-ci-tc.services.mozilla.com"
    graphql_endpoint = f"{root_url}/graphql"

    def __init__(self):
        with open(os.path.expanduser("~/.tc_token")) as json_file:
            data = json.load(json_file)
        self.client_id = data["clientId"]
        self.access_token = data["accessToken"]

    def get_auth_header(self):
        """Generate the authorization header using credentials."""
        return f"Bearer {self.access_token}"

    def view_worker(
        self,
        provisioner_id,
        worker_type,
        worker_group,
        worker_id,
        worker_pool_id,
    ):
        """
        Query worker information using GraphQL API.

        Args:
            provisioner_id: The provisioner ID
            worker_type: The worker type
            worker_group: The worker group
            worker_id: The worker ID
            worker_pool_id: The worker pool ID

        Returns:
            dict: The parsed JSON response
        """
        # Set headers similar to the curl command
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "*/*",
            "content-type": "application/json",
            "Authorization": self.get_auth_header(),
            "Origin": self.root_url,
            "Connection": "keep-alive",
        }

        # Set the GraphQL query and variables
        payload = {
            "operationName": "ViewWorker",
            "variables": {
                "workerPoolId": worker_pool_id,
                "provisionerId": provisioner_id,
                "workerType": worker_type,
                "workerGroup": worker_group,
                "workerId": worker_id,
            },
            "query": """
                query ViewWorker($provisionerId: String!, $workerType: String!, $workerGroup: String!, $workerId: ID!, $workerPoolId: String!, $workerTypesConnection: PageConnection) {
                  worker(
                    provisionerId: $provisionerId
                    workerType: $workerType
                    workerGroup: $workerGroup
                    workerId: $workerId
                  ) {
                    provisionerId
                    workerType
                    workerGroup
                    workerId
                    quarantineUntil
                    quarantineDetails {
                      updatedAt
                      clientId
                      quarantineUntil
                      quarantineInfo
                      __typename
                    }
                    expires
                    firstClaim
                    lastDateActive
                    state
                    capacity
                    providerId
                    workerPoolId
                    recentTasks {
                      taskId
                      run {
                        taskId
                        runId
                        started
                        resolved
                        state
                        __typename
                      }
                      __typename
                    }
                    latestTasks {
                      taskId
                      metadata {
                        name
                        source
                        description
                        owner
                        __typename
                      }
                      __typename
                    }
                    actions {
                      name
                      title
                      context
                      url
                      description
                      __typename
                    }
                    __typename
                  }
                  WorkerManagerWorker(
                    workerPoolId: $workerPoolId
                    workerGroup: $workerGroup
                    workerId: $workerId
                  ) {
                    workerPoolId
                    workerGroup
                    workerId
                    providerId
                    state
                    created
                    expires
                    capacity
                    lastModified
                    lastChecked
                    __typename
                  }
                  workerTypes(provisionerId: $provisionerId, connection: $workerTypesConnection) {
                    edges {
                      node {
                        workerType
                        __typename
                      }
                      __typename
                    }
                    __typename
                  }
                  provisioners {
                    edges {
                      node {
                        provisionerId
                        __typename
                      }
                      __typename
                    }
                    __typename
                  }
                }
            """,
        }

        # Make the request
        response = requests.post(self.graphql_endpoint, json=payload, headers=headers)
        response.raise_for_status()  # Raise an exception for HTTP errors

        return response.json()


# Example usage
if __name__ == "__main__":
    client = QuarantineGraphQL()
    result = client.view_worker(
        provisioner_id="proj-autophone",
        worker_type="gecko-t-bitbar-gw-perf-a55",
        worker_group="bitbar",
        worker_id="a55-50",
        worker_pool_id="proj-autophone/gecko-t-bitbar-gw-perf-a55",
    )
    print(json.dumps(result, indent=2))
