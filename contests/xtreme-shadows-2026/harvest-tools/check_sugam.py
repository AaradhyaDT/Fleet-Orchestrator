import asyncio
import json
import urllib.request
import websockets

async def check():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if 'hackerrank.com' in t.get('url', '') and t.get('type') == 'page']
    ws_url = pages[0]['webSocketDebuggerUrl']
    async with websockets.connect(ws_url) as ws:
        expr = """
        (async () => {
            const resp = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges/sugam-and-the-coin-piles/submissions/1416433986');
            const data = await resp.json();
            return JSON.stringify(data.model);
        })()
        """
        await ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'awaitPromise': True}}))
        val = json.loads(json.loads(await ws.recv())['result']['result']['value'])
        print("Status:", val.get('status'), "Score:", val.get('score'))

asyncio.run(check())
