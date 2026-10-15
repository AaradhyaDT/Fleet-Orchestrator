import urllib.request
import json
import websocket

def get_tabs():
    req = urllib.request.Request('http://localhost:9222/json')
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def inspect_contests():
    tabs = get_tabs()
    # Check all URLs
    for t in tabs:
        if t.get('type') == 'page':
            print("PAGE:", t.get('title'), "-->", t.get('url'))

if __name__ == '__main__':
    inspect_contests()
