import asyncio
import json
import urllib.request
import websockets

async def dump_tab8():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if 'the-maximum-portfolio-gain' in t.get('url', '') and t.get('type') == 'page']
    ws_url = pages[0]['webSocketDebuggerUrl']
    async with websockets.connect(ws_url) as ws:
        expr = """
        (() => {
            return JSON.stringify({
                title: document.title,
                text: document.body.innerText
            });
        })()
        """
        await ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr}}))
        val = json.loads(json.loads(await ws.recv())['result']['result']['value'])
        print("=== TEXT ===")
        print(val['text'])

asyncio.run(dump_tab8())
