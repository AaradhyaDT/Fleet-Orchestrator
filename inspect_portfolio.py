import asyncio
import json
import urllib.request
import websockets

async def inspect_portfolio():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if 'the-maximum-portfolio-gain' in t.get('url', '') and t.get('type') == 'page']
    if not pages:
        # Fallback to fetching via API
        pages = [t for t in tabs if 'hackerrank.com' in t.get('url', '') and t.get('type') == 'page']
    ws_url = pages[0]['webSocketDebuggerUrl']
    async with websockets.connect(ws_url) as ws:
        expr = """
        (async () => {
            const resp = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges/the-maximum-portfolio-gain');
            return JSON.stringify(await resp.json());
        })()
        """
        await ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'awaitPromise': True}}))
        val = json.loads(json.loads(await ws.recv())['result']['result']['value'])
        m = val['model']
        with open('portfolio_gain.json', 'w', encoding='utf-8') as f:
            json.dump(m, f, indent=2)
        print("Title:", m.get('name'))
        print("Score:", m.get('max_score'))
        print("=== Statement ===")
        print(m.get('problem_statement'))
        print("=== Input Format ===")
        print(m.get('input_format'))
        print("=== Constraints ===")
        print(m.get('constraints'))
        print("=== Output Format ===")
        print(m.get('output_format'))

asyncio.run(inspect_portfolio())
