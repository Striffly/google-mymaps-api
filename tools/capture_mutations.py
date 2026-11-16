"""Print every request the My Maps editor sends to /mutate, to reverse-engineer new operations.

1. Start Chromium on a signed-in profile with remote debugging:
     chromium --user-data-dir=PROFILE --remote-debugging-port=9222
2. Open a test map in the editor, then run:  python tools/capture_mutations.py
3. Make the edit by hand; each mutation is printed as one JSON line (the decoded f.req).
"""

import argparse
import json
import sys
from urllib.parse import parse_qs

import requests
import websocket


def find_editor_tab(port):
    targets = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=5).json()
    for target in targets:
        if target["type"] == "page" and "/maps/d/" in target["url"]:
            return target
    sys.exit("No My Maps tab found: open a map in the editor first")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=9222, help="Chromium remote debugging port")
    args = parser.parse_args()

    tab = find_editor_tab(args.port)
    print(f"Listening on {tab['url']}", file=sys.stderr)
    connection = websocket.create_connection(tab["webSocketDebuggerUrl"])
    connection.send(json.dumps({"id": 1, "method": "Network.enable", "params": {"maxPostDataSize": 1000000}}))

    while True:
        message = json.loads(connection.recv())
        if message.get("method") != "Network.requestWillBeSent":
            continue
        request = message["params"]["request"]
        if "/mutate" not in request["url"]:
            continue
        body = request.get("postData", "")
        print(parse_qs(body).get("f.req", [body])[0], flush=True)


if __name__ == "__main__":
    main()
