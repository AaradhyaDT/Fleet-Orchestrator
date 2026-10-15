import urllib.request
import json
import asyncio
import websockets

async def check():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json').read())
    m1 = next((t for t in tabs if 'micro1' in t.get('url', '')), None)
    if not m1:
        return
    async with websockets.connect(m1['webSocketDebuggerUrl']) as ws:
        js = """
        (() => {
            const btns = Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim());
            const alerts = Array.from(document.querySelectorAll('[role="alert"], .toast, [class*="alert"], [class*="toast"], [class*="error"], [class*="success"], [class*="message"]')).map(a => a.innerText.trim()).filter(Boolean);
            return { btns, alerts };
        })()
        """
        msg = {'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js, 'returnByValue': True}}
        await ws.send(json.dumps(msg))
        res = json.loads(await ws.recv())
        print(json.dumps(res['result']['result']['value'], indent=2))

if __name__ == '__main__':
    asyncio.run(check())
