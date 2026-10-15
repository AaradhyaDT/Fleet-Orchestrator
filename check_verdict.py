import asyncio
import json
import urllib.request
import websockets

async def check_sub():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if 'sum-of-2-numbers-3-1' in t.get('url', '') and t.get('type') == 'page']
    ws_url = pages[0]['webSocketDebuggerUrl']
    async with websockets.connect(ws_url) as ws:
        for _ in range(10):
            await asyncio.sleep(2)
            expr = """
            (async () => {
                const resp = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges/sum-of-2-numbers-3-1/submissions');
                return JSON.stringify(await resp.json());
            })()
            """
            await ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'awaitPromise': True}}))
            val = json.loads(json.loads(await ws.recv())['result']['result']['value'])
            models = val.get('models', [])
            if models:
                sub = models[0]
                print(f"Latest submission: id={sub.get('id')}, status={sub.get('status')}, score={sub.get('score')}")
                if sub.get('status') != 'Processing':
                    break

asyncio.run(check_sub())
