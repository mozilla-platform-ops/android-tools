import requests
import json


def view_workers(provisioner, workerType, continuation=None):
    """
    Query workers information using GraphQL API.

    Args:
        url (str): The GraphQL endpoint URL.
        provisioner (str): The provisioner ID.
        workerType (str): The worker type.
        continuation (str): The continuation string for pagination.

    Returns:
        dict: The parsed JSON response.
    """
    url = "https://firefox-ci-tc.services.mozilla.com/graphql"
    headers = {"content-type": "application/json"}
    payload = {
        "operationName": "ViewWorkers",
        "variables": {
            "provisionerId": provisioner,
            "workerType": workerType,
            "workersConnection": json.loads(continuation) if continuation else None,
        },
        "query": """
            query ViewWorkers($provisionerId: String!, $workerType: String!, $workersConnection: PageConnection, $quarantined: Boolean) {
              workers(provisionerId: $provisionerId, workerType: $workerType, connection: $workersConnection, isQuarantined: $quarantined) {
                pageInfo {
                  hasNextPage
                  hasPreviousPage
                  cursor
                  previousCursor
                  nextCursor
                  __typename
                }
                edges {
                  node {
                    latestTask {
                      run {
                        workerGroup
                        workerId
                        taskId
                        runId
                        started
                        resolved
                        state
                        __typename
                      }
                      __typename
                    }
                    workerGroup
                    workerId
                    quarantineUntil
                  }
                }
              }
            }
        """,
    }
    # Remove None values from variables
    payload["variables"] = {
        k: v for k, v in payload["variables"].items() if v is not None
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()


# main
if __name__ == "__main__":
    # Example usage:
    result = view_workers(
        provisioner="proj-autophone",
        workerType="gecko-t-bitbar-gw-perf-a55",
    )
    print(json.dumps(result, indent=2))
