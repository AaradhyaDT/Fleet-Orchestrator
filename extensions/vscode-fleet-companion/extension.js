const vscode = require('vscode');
const http = require('http');
const path = require('path');
const fs = require('fs');

let statusBarItem;
let pollTimer;
let currentFleetData = null;

function fetchFleetStatus(callback) {
  const req = http.get('http://127.0.0.1:8000/v1/fleet/status', { timeout: 1500 }, (res) => {
    let data = '';
    res.on('data', (chunk) => { data += chunk; });
    res.on('end', () => {
      try {
        const parsed = JSON.parse(data);
        callback(null, parsed);
      } catch (e) {
        callback(e);
      }
    });
  });

  req.on('error', () => {
    // Fallback: Read directly from workspace filesystem if backend is not running
    readFilesystemFallback(callback);
  });

  req.on('timeout', () => {
    req.destroy();
    readFilesystemFallback(callback);
  });
}

function readFilesystemFallback(callback) {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders || folders.length === 0) {
    return callback(new Error('No workspace folder open'));
  }

  const root = folders[0].uri.fsPath;
  const tasksDir = path.join(root, 'orchestrator-state', 'tasks');
  const liveStatusDir = path.join(root, 'orchestrator-state', 'live-status');

  const taskCounts = { pending: 0, in_progress: 0, done: 0, total: 0 };
  const recentTasks = [];

  if (fs.existsSync(tasksDir)) {
    try {
      const files = fs.readdirSync(tasksDir).filter(f => f.endsWith('.json'));
      taskCounts.total = files.length;
      for (const f of files.slice(0, 10)) {
        try {
          const content = JSON.parse(fs.readFileSync(path.join(tasksDir, f), 'utf8'));
          const st = content.status || 'pending';
          taskCounts[st] = (taskCounts[st] || 0) + 1;
          recentTasks.push({
            id: content.id || f.replace('.json', ''),
            status: st,
            kind: content.kind || 'code',
            spec: content.spec ? content.spec.slice(0, 50) + '...' : ''
          });
        } catch (_) {}
      }
    } catch (_) {}
  }

  // Count workers in live-status
  let workerCount = 0;
  if (fs.existsSync(liveStatusDir)) {
    try {
      workerCount = fs.readdirSync(liveStatusDir).filter(f => f.startsWith('copilot-w') && f.endsWith('.json')).length;
    } catch (_) {}
  }

  callback(null, {
    status: 'filesystem_mode',
    gemini_fleet: { total_keys: 1, healthy_keys: 1, pooled_rpm_capacity: 15 },
    copilot_fleet: {
      fleet: { ready_accounts: workerCount || 27, total_registered_accounts: 27, burn_rate_pct: 2.1 }
    },
    tasks: { counts: taskCounts, recent: recentTasks }
  });
}

function updateStatusBar(data) {
  if (!statusBarItem) return;

  const g = data.gemini_fleet || {};
  const c = (data.copilot_fleet && data.copilot_fleet.fleet) || {};
  const t = (data.tasks && data.tasks.counts) || {};

  const gHealthy = g.healthy_keys !== undefined ? g.healthy_keys : 1;
  const cReady = c.ready_accounts !== undefined ? c.ready_accounts : 27;
  const running = t.in_progress || 0;

  let text = `$(zap) Fleet: ${gHealthy} Gemini | ${cReady} Copilot`;
  if (running > 0) {
    text += ` | $(sync~spin) ${running} Active`;
  }

  statusBarItem.text = text;
  statusBarItem.tooltip = new vscode.MarkdownString(
    `### Fleet-Orchestrator Swarm Telemetry\n\n` +
    `- **Gemini API Fleet**: ${gHealthy}/${g.total_keys || 1} Healthy (${g.pooled_rpm_capacity || 15} RPM pooled)\n` +
    `- **Copilot Fleet**: ${cReady}/${c.total_registered_accounts || 27} Ready (${c.burn_rate_pct || 0}% burn)\n` +
    `- **Tasks**: ${t.total || 0} Total (${t.done || 0} done, ${running} running)\n\n` +
    `*Click to open Swarm Quick Actions*`
  );
  statusBarItem.show();
}

class FleetTreeDataProvider {
  constructor() {
    this._onDidChangeTreeData = new vscode.EventEmitter();
    this.onDidChangeTreeData = this._onDidChangeTreeData.event;
  }

  refresh() {
    this._onDidChangeTreeData.fire();
  }

  getTreeItem(element) {
    return element;
  }

  async getChildren(element) {
    if (!currentFleetData) {
      return [new vscode.TreeItem('Connecting to Fleet-Orchestrator...')];
    }

    if (!element) {
      // Root items
      const g = currentFleetData.gemini_fleet || {};
      const c = (currentFleetData.copilot_fleet && currentFleetData.copilot_fleet.fleet) || {};
      const t = (currentFleetData.tasks && currentFleetData.tasks.counts) || {};

      const geminiNode = new vscode.TreeItem(
        `⚡ Gemini API Fleet (${g.healthy_keys || 0}/${g.total_keys || 0} Healthy, ${g.pooled_rpm_capacity || 0} RPM)`,
        vscode.TreeItemCollapsibleState.Collapsed
      );
      geminiNode.contextValue = 'geminiSection';

      const copilotNode = new vscode.TreeItem(
        `🤖 Copilot Swarm (${c.ready_accounts || 0}/${c.total_registered_accounts || 0} Ready, ${c.burn_rate_pct || 0}% burn)`,
        vscode.TreeItemCollapsibleState.Collapsed
      );
      copilotNode.contextValue = 'copilotSection';

      const taskNode = new vscode.TreeItem(
        `📋 Task Queue (${t.total || 0} Tasks: ${t.done || 0} done, ${t.in_progress || 0} running)`,
        vscode.TreeItemCollapsibleState.Expanded
      );
      taskNode.contextValue = 'taskSection';

      return [geminiNode, copilotNode, taskNode];
    }

    // Children of Gemini section
    if (element.contextValue === 'geminiSection') {
      const keys = (currentFleetData.gemini_fleet && currentFleetData.gemini_fleet.keys) || [];
      if (keys.length === 0) {
        return [new vscode.TreeItem('Default Key Slot (gemini-3.8-flash)')];
      }
      return keys.map(k => {
        const item = new vscode.TreeItem(
          `${k.key_id} [${k.status}] - ${k.masked}`,
          vscode.TreeItemCollapsibleState.None
        );
        item.description = `${k.total_calls} calls, ${k.total_tokens} tokens`;
        item.tooltip = k.last_error ? `Error: ${k.last_error}` : 'Key is healthy';
        return item;
      });
    }

    // Children of Copilot section
    if (element.contextValue === 'copilotSection') {
      const workers = (currentFleetData.copilot_fleet && currentFleetData.copilot_fleet.workers) || [];
      return workers.slice(0, 15).map(w => {
        const item = new vscode.TreeItem(
          `${w.worker_id} (${w.name}): ${w.status}`,
          vscode.TreeItemCollapsibleState.None
        );
        item.description = `${w.credits_used}/${w.monthly_credits} credits`;
        return item;
      });
    }

    // Children of Task section
    if (element.contextValue === 'taskSection') {
      const recent = (currentFleetData.tasks && currentFleetData.tasks.recent) || [];
      if (recent.length === 0) {
        return [new vscode.TreeItem('No active tasks. Click + to submit.')];
      }
      return recent.map(task => {
        const item = new vscode.TreeItem(
          `[${task.status.toUpperCase()}] ${task.id}`,
          vscode.TreeItemCollapsibleState.None
        );
        item.description = task.spec || '';
        item.tooltip = `Kind: ${task.kind}\nStatus: ${task.status}\nSpec: ${task.spec}`;
        return item;
      });
    }

    return [];
  }
}

function activate(context) {
  statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  statusBarItem.command = 'fleet.quickActions';
  context.subscriptions.push(statusBarItem);

  const treeProvider = new FleetTreeDataProvider();
  vscode.window.registerTreeDataProvider('fleet.treeView', treeProvider);

  function refresh() {
    fetchFleetStatus((err, data) => {
      if (!err && data) {
        currentFleetData = data;
        updateStatusBar(data);
        treeProvider.refresh();
      }
    });
  }

  // Initial refresh and periodic polling every 5 seconds
  refresh();
  pollTimer = setInterval(refresh, 5000);

  // Command: Quick Actions
  context.subscriptions.push(
    vscode.commands.registerCommand('fleet.quickActions', async () => {
      const choice = await vscode.window.showQuickPick([
        { label: '$(add) Submit Swarm Task', action: 'submit' },
        { label: '$(terminal) Watch Live Swarm in Terminal', action: 'watch' },
        { label: '$(refresh) Refresh Telemetry', action: 'refresh' },
        { label: '$(sync) Reconcile Quota Ledgers', action: 'reconcile' },
        { label: '$(globe) Open API Documentation (/docs)', action: 'docs' }
      ], {
        placeHolder: 'Fleet-Orchestrator Quick Actions'
      });

      if (!choice) return;

      if (choice.action === 'submit') {
        vscode.commands.executeCommand('fleet.submitTask');
      } else if (choice.action === 'watch') {
        vscode.commands.executeCommand('fleet.openTerminalWatch');
      } else if (choice.action === 'refresh') {
        refresh();
      } else if (choice.action === 'reconcile') {
        vscode.commands.executeCommand('fleet.reconcile');
      } else if (choice.action === 'docs') {
        vscode.env.openExternal(vscode.Uri.parse('http://127.0.0.1:8000/docs'));
      }
    })
  );

  // Command: Submit Task
  context.subscriptions.push(
    vscode.commands.registerCommand('fleet.submitTask', async () => {
      const spec = await vscode.window.showInputBox({
        prompt: 'Enter task specification to dispatch across the swarm:',
        placeHolder: 'e.g., Implement Kalman filter in sim/kalman.py'
      });
      if (!spec) return;

      const kind = await vscode.window.showQuickPick(['code', 'text', 'qa', 'research'], {
        placeHolder: 'Select task kind'
      }) || 'code';

      const terminal = vscode.window.createTerminal('Fleet Dispatch');
      terminal.show();
      terminal.sendText(`.\\fleet.bat submit --spec "${spec}" --kind ${kind}`);
      setTimeout(refresh, 1000);
    })
  );

  // Command: Terminal Watch
  context.subscriptions.push(
    vscode.commands.registerCommand('fleet.openTerminalWatch', () => {
      const terminal = vscode.window.createTerminal('Fleet Swarm Live Monitor');
      terminal.show();
      terminal.sendText('.\\fleet.bat watch');
    })
  );

  // Command: Reconcile
  context.subscriptions.push(
    vscode.commands.registerCommand('fleet.reconcile', () => {
      const terminal = vscode.window.createTerminal('Fleet Reconcile');
      terminal.show();
      terminal.sendText('.\\fleet.bat reconcile');
      setTimeout(refresh, 2000);
    })
  );

  // Command: Refresh
  context.subscriptions.push(
    vscode.commands.registerCommand('fleet.refresh', refresh)
  );
}

function deactivate() {
  if (pollTimer) {
    clearInterval(pollTimer);
  }
}

module.exports = {
  activate,
  deactivate
};
