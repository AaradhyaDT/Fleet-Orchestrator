import asyncio
import json
import urllib.request
import websockets

async def test_hr_run():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if 'sum-of-2-numbers-3-1' in t.get('url', '') and t.get('type') == 'page']
    ws_url = pages[0]['webSocketDebuggerUrl']
    async with websockets.connect(ws_url) as ws:
        # Check window.HR or document headers or test compile_tests
        expr = """
        (() => {
            const csrf = document.querySelector('meta[name="csrf-token"]') ? document.querySelector('meta[name="csrf-token"]').content : '';
            return JSON.stringify({
                csrf: csrf,
                hasJQuery: typeof jQuery !== 'undefined',
                hasBackbone: typeof Backbone !== 'undefined'
            });
        })()
        """
        await ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr}}))
        res = await ws.recv()
        print(json.loads(res)['result']['result']['value'])

asyncio.run(test_hr_run())
