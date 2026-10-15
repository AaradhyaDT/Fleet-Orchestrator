import urllib.request
import json
import websocket

tabs_req = urllib.request.Request('http://localhost:9222/json')
with urllib.request.urlopen(tabs_req) as r:
    tabs = json.loads(r.read().decode())

t = [x for x in tabs if 'contests/create' in x.get('url', '')][0]
ws = websocket.create_connection(t['webSocketDebuggerUrl'], suppress_origin=True, timeout=5)

# Fill form
fill_js = """
(() => {
    // 1. Contest Name
    let nameInput = document.querySelector('#name');
    if (nameInput) {
        nameInput.value = 'Xtreme Shadows 2026 - Replica';
        nameInput.dispatchEvent(new Event('input', { bubbles: true }));
        nameInput.dispatchEvent(new Event('change', { bubbles: true }));
    }

    // 2. Organization Type
    if (window.$ && $('#organization_type').length) {
        $('#organization_type').select2('val', 'school');
        $('#organization_type').trigger('change');
    }

    // 3. Organization Name
    let orgName = document.querySelector('#organization_name');
    if (orgName) {
        orgName.value = 'IEEE KEC';
        orgName.dispatchEvent(new Event('input', { bubbles: true }));
        orgName.dispatchEvent(new Event('change', { bubbles: true }));
    }

    return {
        name: nameInput ? nameInput.value : null,
        orgType: window.$ ? $('#organization_type').val() : null,
        orgName: orgName ? orgName.value : null,
        startDate: document.querySelector('#startdate') ? document.querySelector('#startdate').value : null,
        startTime: document.querySelector('#starttime') ? document.querySelector('#starttime').value : null,
        endDate: document.querySelector('#enddate') ? document.querySelector('#enddate').value : null,
        endTime: document.querySelector('#endtime') ? document.querySelector('#endtime').value : null
    };
})()
"""

ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': fill_js, 'returnByValue': True}}))
res = json.loads(ws.recv())
print("Filled fields:", json.dumps(res.get('result', {}).get('result', {}).get('value'), indent=2))
ws.close()
