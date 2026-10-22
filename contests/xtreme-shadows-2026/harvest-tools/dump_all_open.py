import asyncio
import json
import urllib.request
import websockets

async def dump_all():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if t.get('type') == 'page' and 'hackerrank.com' in t.get('url', '')]
    for p in pages:
        if '/challenges/' not in p['url']:
            continue
        slug = p['url'].split('/challenges/')[1].split('/')[0]
        ws_url = p['webSocketDebuggerUrl']
        async with websockets.connect(ws_url) as ws:
            expr = """
            (() => {
                const el = document.querySelector('.challenge-body-html');
                return el ? el.innerText : '';
            })()
            """
            await ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr}}))
            res = await ws.recv()
            val = json.loads(res)['result']['result']['value']
            with open(f"{slug}.txt", "w", encoding="utf-8") as f:
                f.write(val)
            print(f"Dumped: {slug} (length {len(val)})")

if __name__ == '__main__':
    asyncio.run(dump_all())
