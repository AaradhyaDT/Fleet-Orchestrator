import asyncio
import json
import urllib.request
import websockets
import sys

sys.stdout.reconfigure(encoding='utf-8')

async def inspect_several():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if 'hackerrank.com' in t.get('url', '') and t.get('type') == 'page']
    ws_url = pages[0]['webSocketDebuggerUrl']
    slugs = [
        'sugam-and-the-coin-piles',
        'sudhan-and-the-demodogs',
        'deja-vu-1-3',
        'product-of-three-numbers-4',
        'powered-addition'
    ]
    async with websockets.connect(ws_url) as ws:
        for s in slugs:
            expr = f"""
            (async () => {{
                const resp = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges/{s}');
                const data = await resp.json();
                return JSON.stringify(data.model);
            }})()
            """
            await ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'awaitPromise': True}}))
            m = json.loads(json.loads(await ws.recv())['result']['result']['value'])
            print(f"=== {m.get('name')} ({m.get('max_score')} pts, slug: {s}) ===")
            print(m.get('problem_statement')[:300])
            print("Constraints:", m.get('constraints'))

asyncio.run(inspect_several())
