import asyncio
import json
import urllib.request
import websockets

async def dump_tab(target_substr, filename):
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if target_substr in t.get('url', '') and t.get('type') == 'page']
    if not pages:
        print('Not found:', target_substr)
        return
    ws_url = pages[0]['webSocketDebuggerUrl']
    async with websockets.connect(ws_url) as ws:
        expr = """
        (() => {
            const el = document.querySelector('.challenge-body-html') || 
                       document.querySelector('.problem-statement') || 
                       document.querySelector('.theme-m-content') || document.body;
            return JSON.stringify({
                text: el.innerText,
                html: el.innerHTML
            });
        })()
        """
        await ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr}}))
        res = await ws.recv()
        val = json.loads(json.loads(res)['result']['result']['value'])
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(val['text'])
        with open('p3_html.txt', 'w', encoding='utf-8') as f:
            f.write(val['html'])
        print(f"Saved {filename}, len={len(val['text'])}")

if __name__ == '__main__':
    asyncio.run(dump_tab('sum-of-2-numbers-3', 'problem3.txt'))
