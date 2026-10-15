import asyncio
import json
import urllib.request
import websockets

async def dump_problem():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if 'hackerrank.com' in t.get('url', '') and t.get('type') == 'page']
    if not pages:
        print("No HackerRank page found")
        return
    ws_url = pages[0]['webSocketDebuggerUrl']
    async with websockets.connect(ws_url) as ws:
        expr = """
        (() => {
            const el = document.querySelector('.problem-statement') || 
                       document.querySelector('.challenge-body-html') || 
                       document.querySelector('.problem-body') || 
                       document.querySelector('.challenge-body') ||
                       document.querySelector('.theme-m-content');
            return el ? el.innerText : document.body.innerText;
        })()
        """
        await ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr}}))
        res = await ws.recv()
        val = json.loads(res)['result']['result']['value']
        with open('problem1.txt', 'w', encoding='utf-8') as out:
            out.write(val)
        print('Saved successfully! Length:', len(val))

asyncio.run(dump_problem())
