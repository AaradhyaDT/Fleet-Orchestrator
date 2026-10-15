import asyncio
import json
import urllib.request
import websockets
import sys

sys.stdout.reconfigure(encoding='utf-8')

async def inspect_nitesh():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if 'nitesh-and-the-green-research-card' in t.get('url', '') and t.get('type') == 'page']
    ws_url = pages[0]['webSocketDebuggerUrl']
    async with websockets.connect(ws_url) as ws:
        expr = """
        (async () => {
            const resp = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges/nitesh-and-the-green-research-card');
            const data = await resp.json();
            return JSON.stringify({
                model: data.model,
                pageText: document.body.innerText
            });
        })()
        """
        await ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'awaitPromise': True}}))
        val = json.loads(json.loads(await ws.recv())['result']['result']['value'])
        m = val['model']
        print("Name:", m.get('name'))
        print("Score:", m.get('max_score'))
        print("=== Statement ===")
        print(m.get('problem_statement'))
        print("=== Input Format ===")
        print(m.get('input_format'))
        print("=== Constraints ===")
        print(m.get('constraints'))
        print("=== Output Format ===")
        print(m.get('output_format'))
        print("=== Samples from Page ===")
        txt = val['pageText']
        idx = txt.find("Sample Input")
        if idx != -1:
            print(txt[idx:idx+1500])

asyncio.run(inspect_nitesh())
