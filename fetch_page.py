import asyncio
import json
import urllib.request
import websockets

async def dump_problem():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if 'sum-of-2' in t.get('url', '') and t.get('type') == 'page']
    if not pages:
        pages = [t for t in tabs if 'hackerrank.com' in t.get('url', '') and t.get('type') == 'page']
    ws_url = pages[0]['webSocketDebuggerUrl']
    async with websockets.connect(ws_url) as ws:
        expr = """
        (() => {
            const el = document.querySelector('.problem-statement') || 
                       document.querySelector('.challenge-body-html') || 
                       document.querySelector('.problem-body') || 
                       document.querySelector('.challenge-body') ||
                       document.querySelector('.theme-m-content');
            const math = Array.from(document.querySelectorAll('script[type*="math"]')).map(s => s.textContent);
            return JSON.stringify({
                text: el ? el.innerText : document.body.innerText,
                html: el ? el.innerHTML : document.body.innerHTML,
                math: math
            });
        })()
        """
        await ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr}}))
        res = await ws.recv()
        val_raw = json.loads(res)['result']['result']['value']
        data = json.loads(val_raw)
        with open('problem1.txt', 'w', encoding='utf-8') as out:
            out.write(data['text'])
        with open('problem_html.txt', 'w', encoding='utf-8') as out:
            out.write(data['html'])
        with open('problem_math.json', 'w', encoding='utf-8') as out:
            json.dump(data['math'], out, indent=2)
        print('Saved successfully! Length:', len(val_raw))

asyncio.run(dump_problem())
