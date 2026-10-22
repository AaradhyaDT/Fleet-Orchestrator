import asyncio
import json
import urllib.request
import websockets

async def inspect_tab(target_url_sub):
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if target_url_sub in t.get('url', '') and t.get('type') == 'page']
    if not pages:
        print("Not found")
        return
    ws_url = pages[0]['webSocketDebuggerUrl']
    async with websockets.connect(ws_url) as ws:
        expr = """
        (() => {
            const body = document.querySelector('.challenge-body-html') || document.body;
            return JSON.stringify({
                title: document.title,
                url: window.location.href,
                innerText: body.innerText,
                innerHTML: body.innerHTML
            });
        })()
        """
        await ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr}}))
        res = await ws.recv()
        val = json.loads(json.loads(res)['result']['result']['value'])
        print(f"TITLE: {val['title']}")
        print(f"URL: {val['url']}")
        print("=== INNER TEXT ===")
        print(val['innerText'])
        with open('sum_of_2_numbers_3_html.html', 'w', encoding='utf-8') as f:
            f.write(val['innerHTML'])

asyncio.run(inspect_tab('sum-of-2-numbers-3-1'))
