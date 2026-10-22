import asyncio
import json
import urllib.request
import websockets

async def check_math():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json/list').read())
    pages = [t for t in tabs if 'hackerrank.com' in t.get('url', '') and t.get('type') == 'page']
    ws_url = pages[0]['webSocketDebuggerUrl']
    async with websockets.connect(ws_url) as ws:
        expr = """
        (() => {
            const scripts = Array.from(document.querySelectorAll('script[type*="math/tex"]')).map(s => s.textContent);
            const scripts_all = Array.from(document.querySelectorAll('script')).filter(s => s.type && s.type.includes('math')).map(s => ({type: s.type, text: s.textContent}));
            let jax_data = [];
            if (window.MathJax && MathJax.Hub && MathJax.Hub.getAllJax) {
                jax_data = MathJax.Hub.getAllJax().map(j => j.originalText);
            }
            return JSON.stringify({
                url: window.location.href,
                scripts,
                scripts_all,
                jax_data
            });
        })()
        """
        await ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr}}))
        res = await ws.recv()
        val = json.loads(res)['result']['result']['value']
        print(val)

asyncio.run(check_math())
