import json

import requests


def get_tc_workers(provisioner, workerType):
    url = "https://firefox-ci-tc.services.mozilla.com/graphql"

    workerPoolId = f"{provisioner}/{workerType}"

    # Format the query for better readability
    query = {
        "operationName": "ViewWorkers",
        "variables": {
            "workerPoolId": workerPoolId,
            "provisionerId": provisioner,
            "workerType": workerType,
            "workersConnection": {"limit": 1000},
            "quarantined": None,
            "workerState": None,
        },
        "query": """
            query ViewWorkers(
                $provisionerId: String!,
                $workerType: String!,
                $workerPoolId: String!,
                $workersConnection: PageConnection,
                $quarantined: Boolean,
                $workerState: String
            ) {
                workers(
                    provisionerId: $provisionerId
                    workerType: $workerType
                    connection: $workersConnection
                    isQuarantined: $quarantined
                    workerState: $workerState
                ) {
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
                            workerId
                            workerGroup
                            latestTask {
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
                            firstClaim
                            quarantineUntil
                            lastDateActive
                            state
                            capacity
                            providerId
                            workerPoolId
                            __typename
                        }
                        __typename
                    }
                    __typename
                }
                WorkerPool(workerPoolId: $workerPoolId) {
                    workerPoolId
                    __typename
                }
                workerType(provisionerId: $provisionerId, workerType: $workerType) {
                    actions {
                        name
                        description
                        title
                        url
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
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json=query, headers=headers)

    # Print the results
    if response.status_code == 200:
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"Error: {response.status_code}")
        print(response.text)


provisioner = "proj-autophone"
workerType = "gecko-t-bitbar-gw-perf-a55"
get_tc_workers(provisioner, workerType)
