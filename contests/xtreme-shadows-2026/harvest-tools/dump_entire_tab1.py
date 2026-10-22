import asyncio
import json
import urllib.request
import websockets

async def dump_page():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if 'sum-of-2-numbers-3-1' in t.get('url', '') and t.get('type') == 'page']
    ws_url = pages[0]['webSocketDebuggerUrl']
    async with websockets.connect(ws_url) as ws:
        expr = """
        (() => {
            const samples = Array.from(document.querySelectorAll('.sample-testcase, .challenge-instruction, .challenge-body-html, .sample-input, .sample-output, pre, code')).map(e => ({
                tag: e.tagName,
                cls: e.className,
                text: e.innerText
            }));
            const entireText = document.body.innerText;
            return JSON.stringify({samples, entireText});
        })()
        """
        await ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr}}))
        res = await ws.recv()
        val = json.loads(json.loads(res)['result']['result']['value'])
        with open('sum_3_entire_text.txt', 'w', encoding='utf-8') as f:
            f.write(val['entireText'])
        print("Wrote sum_3_entire_text.txt, length:", len(val['entireText']))

asyncio.run(dump_page())
