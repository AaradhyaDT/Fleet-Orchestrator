import asyncio
import json
import urllib.request
import websockets

async def check():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if 'hackerrank.com' in t.get('url', '') and t.get('type') == 'page']
    ws_url = pages[0]['webSocketDebuggerUrl']
    async with websockets.connect(ws_url) as ws:
        slugs = [
            'sudhan-and-the-demodogs',
            'prajwal-and-the-marble-ap',
            'utsav-and-the-monster-horde',
            'deja-vu-1-3',
            'brain-rot-outbreak'
        ]
        for slug in slugs:
            expr = f"""
            (async () => {{
                const res = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges/{slug}/submissions');
                const d = await res.json();
                return JSON.stringify(d.models[0] || null);
            }})()
            """
            await ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'awaitPromise': True}}))
            raw = json.loads(await ws.recv())['result']['result']['value']
            val = json.loads(raw)
            if val:
                print(f"{slug}: status={val.get('status')}, score={val.get('score')}")
            else:
                print(f"{slug}: no submission yet")

asyncio.run(check())
