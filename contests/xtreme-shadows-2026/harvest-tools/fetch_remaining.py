import asyncio
import json
import urllib.request
import websockets
import sys

sys.stdout.reconfigure(encoding='utf-8')

remaining_slugs = [
    'deja-vu-1-3',
    'brain-rot-outbreak',
    'roshan-makes-them-equal',
    'shuffle-8',
    'product-of-three-numbers-4',
    'shrine',
    'powered-addition',
    'anugyas-lantern-festival',
    'prajwal-and-the-marble-ap',
    'utsav-and-the-monster-horde'
]

async def inspect_all_remaining():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if 'hackerrank.com' in t.get('url', '') and t.get('type') == 'page']
    ws_url = pages[0]['webSocketDebuggerUrl']
    
    results = {}
    async with websockets.connect(ws_url) as ws:
        for slug in remaining_slugs:
            expr = f"""
            (async () => {{
                const resp = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges/{slug}');
                const data = await resp.json();
                return JSON.stringify(data.model);
            }})()
            """
            await ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'awaitPromise': True}}))
            val = json.loads(json.loads(await ws.recv())['result']['result']['value'])
            results[slug] = {
                'name': val.get('name'),
                'max_score': val.get('max_score'),
                'statement': val.get('problem_statement'),
                'input': val.get('input_format'),
                'output': val.get('output_format'),
                'constraints': val.get('constraints')
            }
            print(f"Fetched {slug}")
            
    with open('remaining_problems_data.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("All remaining saved!")

asyncio.run(inspect_all_remaining())
