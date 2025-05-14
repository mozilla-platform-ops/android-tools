import requests
import json


# TODO: add a function view_quarantined_worker_details()
#  that will run the equivalent of the following curl:
#    curl 'https://firefox-ci-tc.services.mozilla.com/graphql' --compressed -X POST -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:138.0) Gecko/20100101 Firefox/138.0' -H 'Accept: */*' -H 'Accept-Language: en-US,en;q=0.5' -H 'Accept-Encoding: gzip, deflate, br, zstd' -H 'Referer: https://firefox-ci-tc.services.mozilla.com/' -H 'content-type: application/json' -H 'Authorization: Bearer eyJjbGllbnRJZCI6Im1vemlsbGEtYXV0aDAvYWR8TW96aWxsYS1MREFQfGFlcmlja3NvbiIsImFjY2Vzc1Rva2VuIjoiU0JFQUtxWGd5SWlMS1haUjFvaHVZSng1c01kRDlDOWZLTVBYTmgxZTB6OCIsImNlcnRpZmljYXRlIjoie1widmVyc2lvblwiOjEsXCJzY29wZXNcIjpbXCJhc3N1bWU6bW96aWxsYS1ncm91cDphY3RpdmVfc2NtX2ZpcmVmb3hjaVwiLFwiYXNzdW1lOm1vemlsbGEtZ3JvdXA6YWN0aXZlX3NjbV9sZXZlbF8xXCIsXCJhc3N1bWU6bW96aWxsYS1ncm91cDphY3RpdmVfc2NtX2xldmVsXzJcIixcImFzc3VtZTptb3ppbGxhLWdyb3VwOmFjdGl2ZV9zY21fbGV2ZWxfM1wiLFwiYXNzdW1lOm1vemlsbGEtZ3JvdXA6YWxsX3NjbV9maXJlZm94Y2lcIixcImFzc3VtZTptb3ppbGxhLWdyb3VwOmFsbF9zY21fbGV2ZWxfMVwiLFwiYXNzdW1lOm1vemlsbGEtZ3JvdXA6YWxsX3NjbV9sZXZlbF8yXCIsXCJhc3N1bWU6bW96aWxsYS1ncm91cDphbGxfc2NtX2xldmVsXzNcIixcImFzc3VtZTptb3ppbGxhLWdyb3VwOmJ1aWxkdGVhbVwiLFwiYXNzdW1lOm1vemlsbGEtZ3JvdXA6aW52ZW50b3J5XCIsXCJhc3N1bWU6bW96aWxsYS1ncm91cDpyZWxvcHNcIixcImFzc3VtZTptb3ppbGxhLWdyb3VwOnRlYW1fbW9jb1wiLFwiYXNzdW1lOm1vemlsbGEtZ3JvdXA6dGVhbV9tb2NvX2JlbmVmaXRlZFwiLFwiYXNzdW1lOm1vemlsbGEtZ3JvdXA6dGVhbV9yZWxvcHNcIixcImFzc3VtZTptb3ppbGxhLWdyb3VwOnZwbl9hZF9kYlwiLFwiYXNzdW1lOm1vemlsbGEtZ3JvdXA6dnBuX2JpdGJhcl9kZXZpY2Vwb29sXCIsXCJhc3N1bWU6bW96aWxsYS1ncm91cDp2cG5fY29ycFwiLFwiYXNzdW1lOm1vemlsbGEtZ3JvdXA6dnBuX2RlZmF1bHRcIixcImFzc3VtZTptb3ppbGxhLWdyb3VwOnZwbl9naXRpX3B1cHBldF9yd1wiLFwiYXNzdW1lOm1vemlsbGEtZ3JvdXA6dnBuX2luZm9ibG94XCIsXCJhc3N1bWU6bW96aWxsYS1ncm91cDp2cG5faXRfbmFnaW9zX3dlYlwiLFwiYXNzdW1lOm1vemlsbGEtZ3JvdXA6dnBuX25ldG9wc19pY2luZ2FcIixcImFzc3VtZTptb3ppbGxhLWdyb3VwOnZwbl9vYnNlcnZpdW1cIixcImFzc3VtZTptb3ppbGxhLWdyb3VwOnZwbl9wYW5vcmFtYVwiLFwiYXNzdW1lOm1vemlsbGEtZ3JvdXA6dnBuX3FhX2JlcjNcIixcImFzc3VtZTptb3ppbGxhLWdyb3VwOnZwbl9yZWxlbmdcIixcImFzc3VtZTptb3ppbGxhLWdyb3VwOnZwbl9yZWxlbmdfbmFnaW9zXCIsXCJhc3N1bWU6bW96aWxsYS1ncm91cDp2cG5fcmVsZW5nX3JlcG9cIixcImFzc3VtZTptb3ppbGxhLWdyb3VwOnZwbl92Y2VudGVyX3JlbG9wc1wiLFwiYXNzdW1lOm1vemlsbGlhbnMtZ3JvdXA6YXV0b3Bob25lLWFkbWluc1wiLFwiYXNzdW1lOm1vemlsbGlhbnMtZ3JvdXA6Y2hhdGdwdC1hY2Nlc3NcIixcImFzc3VtZTptb3ppbGxpYW5zLWdyb3VwOmNsb3Vkc2VydmljZXNfYXdzX2FkbWluXCIsXCJhc3N1bWU6bW96aWxsaWFucy1ncm91cDpnaGVfZ2hlLWF1dGgtZGV2X3VzZXJzXCIsXCJhc3N1bWU6bW96aWxsaWFucy1ncm91cDpnaGVfbW9jby1naGUtYWRtaW5fdXNlcnNcIixcImFzc3VtZTptb3ppbGxpYW5zLWdyb3VwOmdoZV9tb3ppbGxhLWl0X3VzZXJzXCIsXCJhc3N1bWU6bW96aWxsaWFucy1ncm91cDpnaGVfbW96aWxsYS1wbGF0Zm9ybS1vcHNfdXNlcnNcIixcImFzc3VtZTptb3ppbGxpYW5zLWdyb3VwOmdoZV9tb3ppbGxhX3VzZXJzXCIsXCJhc3N1bWU6bW96aWxsaWFucy1ncm91cDpvYnNfZ3JhZmFuYV9lZGl0b3ItYWNjZXNzXCIsXCJhc3N1bWU6bW96aWxsaWFucy1ncm91cDpzcmVcIixcImFzc3VtZTpsb2dpbi1pZGVudGl0eTptb3ppbGxhLWF1dGgwL2FkfE1vemlsbGEtTERBUHxhZXJpY2tzb25cIl0sXCJzdGFydFwiOjE3NDcyNjI5OTI4NTAsXCJleHBpcnlcIjoxNzQ3MjY0NzkyODUwLFwic2VlZFwiOlwiOWs0VEZ2a0hUazJFa2YydWdyR1Jad2FLZnNPelVRU0k2OFE1Ui0xMVRUc1FcIixcInNpZ25hdHVyZVwiOlwiREg5dnE1WW51SWVQZVhsM01McjRQekVjVWo2ekZ4Sm9xQ0JXZU9LeE1GTT1cIixcImlzc3VlclwiOlwic3RhdGljL3Rhc2tjbHVzdGVyL3dlYi1zZXJ2ZXJcIn0ifQ==' -H 'Origin: https://firefox-ci-tc.services.mozilla.com' -H 'DNT: 1' -H 'Connection: keep-alive' -H 'Cookie: connect.sid=s%3AFDT8jqMk-ymveeCGm9iRCdxF8epRGgTJ.LQuJm8ll1%2FliZrw87VV5McW9tObGHsPXyZfMPg6%2F8%2BU' -H 'Sec-Fetch-Dest: empty' -H 'Sec-Fetch-Mode: cors' -H 'Sec-Fetch-Site: same-origin' -H 'Priority: u=4' -H 'TE: trailers' --data-raw '{"operationName":"ViewWorker","variables":{"workerPoolId":"proj-autophone/gecko-t-bitbar-gw-perf-a55","provisionerId":"proj-autophone","workerType":"gecko-t-bitbar-gw-perf-a55","workerGroup":"bitbar","workerId":"a55-50"},"query":"query ViewWorker($provisionerId: String!, $workerType: String!, $workerGroup: String!, $workerId: ID!, $workerPoolId: String!, $workerTypesConnection: PageConnection) {\n  worker(\n    provisionerId: $provisionerId\n    workerType: $workerType\n    workerGroup: $workerGroup\n    workerId: $workerId\n  ) {\n    provisionerId\n    workerType\n    workerGroup\n    workerId\n    quarantineUntil\n    quarantineDetails {\n      updatedAt\n      clientId\n      quarantineUntil\n      quarantineInfo\n      __typename\n    }\n    expires\n    firstClaim\n    lastDateActive\n    state\n    capacity\n    providerId\n    workerPoolId\n    recentTasks {\n      taskId\n      run {\n        taskId\n        runId\n        started\n        resolved\n        state\n        __typename\n      }\n      __typename\n    }\n    latestTasks {\n      taskId\n      metadata {\n        name\n        source\n        description\n        owner\n        __typename\n      }\n      __typename\n    }\n    actions {\n      name\n      title\n      context\n      url\n      description\n      __typename\n    }\n    __typename\n  }\n  WorkerManagerWorker(\n    workerPoolId: $workerPoolId\n    workerGroup: $workerGroup\n    workerId: $workerId\n  ) {\n    workerPoolId\n    workerGroup\n    workerId\n    providerId\n    state\n    created\n    expires\n    capacity\n    lastModified\n    lastChecked\n    __typename\n  }\n  workerTypes(provisionerId: $provisionerId, connection: $workerTypesConnection) {\n    edges {\n      node {\n        workerType\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n  provisioners {\n    edges {\n      node {\n        provisionerId\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}"}'


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


def view_quarantined_worker_details(
    provisionerId,
    workerType,
    workerGroup,
    workerId,
    workerPoolId,
    auth_token=None,
):
    """
    Query detailed information about a quarantined worker using GraphQL API.

    Args:
        provisionerId (str): The provisioner ID.
        workerType (str): The worker type.
        workerGroup (str): The worker group.
        workerId (str): The worker ID.
        workerPoolId (str): The worker pool ID.
        auth_token (str, optional): Bearer token for Authorization header.

    Returns:
        dict: The parsed JSON response.
    """
    url = "https://firefox-ci-tc.services.mozilla.com/graphql"
    headers = {
        "content-type": "application/json",
    }
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    payload = {
        "operationName": "ViewWorker",
        "variables": {
            "workerPoolId": workerPoolId,
            "provisionerId": provisionerId,
            "workerType": workerType,
            "workerGroup": workerGroup,
            "workerId": workerId,
            "workerTypesConnection": None,
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
    # result = view_workers(
    #     provisioner="proj-autophone",
    #     workerType="gecko-t-bitbar-gw-perf-a55",
    # )

    result = view_quarantined_worker_details(
        provisionerId="proj-autophone",
        workerType="gecko-t-bitbar-gw-perf-a55",
        workerGroup="bitbar",
        workerId="a55-23",
        workerPoolId="proj-autophone/gecko-t-bitbar-gw-perf-a55",
    )

    print(json.dumps(result["data"]["worker"]["quarantineDetails"], indent=2))

    # print(result['data']["quarantineDetails"])
