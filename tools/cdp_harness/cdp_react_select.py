import asyncio
import json
import urllib.request
import websockets

async def check_options():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json').read())
    micro1_tab = next(t for t in tabs if 'micro1-eval-hackathon' in t.get('url', ''))
    ws_url = micro1_tab['webSocketDebuggerUrl']
    
    async with websockets.connect(ws_url) as ws:
        # Focus on Experience and Country and inspect rendered options
        js = """
        (() => {
            const expInput = document.querySelector('input[aria-label="Experience (in years)"]');
            if (expInput) {
                expInput.focus();
                expInput.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
            }
            return 'focused';
        })()
        """
        await ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js}}))
        await ws.recv()
        await asyncio.sleep(1)
        
        # Check what options appeared in the DOM
        js_opts = """
        (() => {
            const opts = Array.from(document.querySelectorAll('[id*="option"], [class*="option"], [role="option"]')).map(o => o.innerText);
            return opts;
        })()
        """
        await ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': js_opts, 'returnByValue': True}}))
        resp = await ws.recv()
        print("Experience Options:", json.loads(resp).get('result', {}).get('result', {}).get('value'))

if __name__ == '__main__':
    asyncio.run(check_options())
