import asyncio
import json
import urllib.request
import websockets

async def list_challenges():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if 'hackerrank.com' in t.get('url', '') and t.get('type') == 'page']
    ws_url = pages[0]['webSocketDebuggerUrl']
    async with websockets.connect(ws_url) as ws:
        expr = """
        (async () => {
            const resp = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges?offset=0&limit=50');
            return await resp.text();
        })()
        """
        await ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'awaitPromise': True}}))
        res = await ws.recv()
        val = json.loads(res)['result']['result']['value']
        data = json.loads(val)
        with open('all_challenges.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        for m in data.get('models', []):
            print(f"{m.get('name')} | slug: {m.get('slug')} | score: {m.get('max_score')} | solved: {m.get('solved')}")

asyncio.run(list_challenges())
