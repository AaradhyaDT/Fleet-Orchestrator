import asyncio
import json
import urllib.request
import websockets
import base64

async def fetch_sample_zip():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if 'sum-of-2-numbers-3-1' in t.get('url', '') and t.get('type') == 'page']
    ws_url = pages[0]['webSocketDebuggerUrl']
    async with websockets.connect(ws_url) as ws:
        expr = """
        (async () => {
            const resp = await fetch('https://www.hackerrank.com/rest/contests/xtreme-shadows-2026/challenges/sum-of-2-numbers-3-1/download_testcases');
            const blob = await resp.blob();
            return new Promise((resolve) => {
                const reader = new FileReader();
                reader.onloadend = () => resolve(reader.result);
                reader.readAsDataURL(blob);
            });
        })()
        """
        await ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'awaitPromise': True}}))
        res = await ws.recv()
        val = json.loads(res)['result']['result']['value']
        data_base64 = val.split(',')[1]
        with open('sample_testcases_sum3.zip', 'wb') as f:
            f.write(base64.b64decode(data_base64))
        print("Successfully downloaded sample_testcases_sum3.zip")

asyncio.run(fetch_sample_zip())
