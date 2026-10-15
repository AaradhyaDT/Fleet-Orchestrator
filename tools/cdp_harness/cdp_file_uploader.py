import asyncio
import json
import urllib.request
from pathlib import Path
import websockets

async def attach_cv():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json').read())
    m1 = next(t for t in tabs if 'micro1' in t.get('url', ''))
    resume_file = "F:\\AaradhyaDT\\AaradhyaDT.github.io\\assets\\docs\\AARADHYA_DEV_TAMRAKAR_CV.pdf"
    
    async with websockets.connect(m1['webSocketDebuggerUrl']) as ws:
        # Get objectId
        await ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': 'document.querySelector("input[type=\'file\']")'}}))
        obj_id = json.loads(await ws.recv())['result']['result']['objectId']
        
        # Attach file
        await ws.send(json.dumps({
            'id': 2,
            'method': 'DOM.setFileInputFiles',
            'params': {'objectId': obj_id, 'files': [resume_file]}
        }))
        await ws.recv()
        
        # Dispatch change event
        await ws.send(json.dumps({
            'id': 3,
            'method': 'Runtime.evaluate',
            'params': {'expression': 'document.querySelector("input[type=\'file\']").dispatchEvent(new Event("change", { bubbles: true }))'}
        }))
        await ws.recv()

        # Check file name
        await ws.send(json.dumps({
            'id': 4,
            'method': 'Runtime.evaluate',
            'params': {'expression': 'document.querySelector("input[type=\'file\']").files[0].name', 'returnByValue': True}
        }))
        res = json.loads(await ws.recv())
        print("Attached resume:", res['result']['result']['value'])

if __name__ == '__main__':
    asyncio.run(attach_cv())
