import asyncio
import json
import urllib.request
import websockets
import sys

sys.stdout.reconfigure(encoding='utf-8')

async def check():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if 'hackerrank.com' in t.get('url', '') and t.get('type') == 'page']
    ws_url = pages[0]['webSocketDebuggerUrl']
    async with websockets.connect(ws_url) as ws:
        expr = """
        (async () => {
            const resp = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges/prajwal-and-the-marble-ap');
            const data = await resp.json();
            return JSON.stringify(data.model);
        })()
        """
        await ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'awaitPromise': True}}))
        val = json.loads(json.loads(await ws.recv())['result']['result']['value'])
        print("Name:", val.get('name'))
        print("Statement:", val.get('problem_statement'))
        print("Input:", val.get('input_format'))
        print("Output:", val.get('output_format'))
        print("Constraints:", val.get('constraints'))

asyncio.run(check())
