
const assert = require('node:assert/strict');
const Module = require('node:module');
const path = require('node:path');
const test = require('node:test');

function createDisposable() {
  return { dispose() {} };
}

function createEventEmitterClass() {
  return class EventEmitter {
    constructor() {
      this.listeners = new Set();
      this.event = (listener) => {
        this.listeners.add(listener);
        return { dispose: () => this.listeners.delete(listener) };
      };
    }

    fire(value) {
      for (const listener of this.listeners) {
        listener(value);
      }
    }

    dispose() {
      this.listeners.clear();
    }
  };
}

function createVscodeStub(repoRoot) {
  const commands = new Map();
  const EventEmitter = createEventEmitterClass();
  const endTaskProcessEmitter = new EventEmitter();
  const endTaskEmitter = new EventEmitter();
  let receiveMessageHandler;
  let disposeHandler;
  const postedMessages = [];
  const executedTasks = [];
  const terminatedTasks = [];

  const panel = {
    webview: {
      html: '',
      async postMessage(message) {
        postedMessages.push(message);
        return true;
      },
      onDidReceiveMessage(listener) {
        receiveMessageHandler = listener;
        return createDisposable();
      },
    },
    reveal() {},
    onDidDispose(listener) {
      disposeHandler = listener;
      return createDisposable();
    },
    dispose() {
      if (disposeHandler) {
        disposeHandler();
      }
    },
  };

  const output = {
    append() {},
    appendLine() {},
    show() {},
    dispose() {},
  };

  const statusBar = {
    text: '',
    tooltip: '',
    command: undefined,
    backgroundColor: undefined,
    show() {},
    dispose() {},
  };

  const terminal = {
    show() {},
    sendText() {},
    dispose() {},
  };

  const vscode = {
    ViewColumn: { Beside: 2 },
    StatusBarAlignment: { Left: 1 },
    ProgressLocation: { Notification: 1 },
    CommentMode: { Preview: 0 },
    CommentThreadCollapsibleState: { Expanded: 0 },
    ThemeColor: class ThemeColor {
      constructor(id) {
        this.id = id;
      }
    },
    ThemeIcon: class ThemeIcon {
      constructor(id) {
        this.id = id;
      }
    },
    EventEmitter,
    comments: {
      createCommentController() {
        return {
          createCommentThread() {
            return {
              comments: [],
              label: '',
              collapsibleState: 0,
              canReply: false,
            };
          },
          dispose() {},
        };
      },
    },
    commands: {
      registerCommand(id, callback) {
        commands.set(id, callback);
        return createDisposable();
      },
      async executeCommand(id, ...args) {
        const callback = commands.get(id);
        if (!callback) {
          throw new Error(`Missing command: ${id}`);
        }
        return await callback(...args);
      },
    },
    tasks: {
      async fetchTasks() {
        return [
          { name: 'run:aicode-server', source: 'workspace', definition: { label: 'run:aicode-server' } },
          { name: 'run:ollama-serve', source: 'workspace', definition: { label: 'run:ollama-serve' } },
          { name: 'test:aicode-all', source: 'workspace', definition: { label: 'test:aicode-all' } },
        ];
      },
      async executeTask(task) {
        const execution = {
          task,
          terminate() {
            terminatedTasks.push(task.name);
            endTaskProcessEmitter.fire({ execution, exitCode: 0 });
            endTaskEmitter.fire({ execution });
          },
        };
        executedTasks.push(task.name);
        return execution;
      },
      onDidEndTaskProcess(listener) {
        return endTaskProcessEmitter.event(listener);
      },
      onDidEndTask(listener) {
        return endTaskEmitter.event(listener);
      },
    },
    workspace: {
      workspaceFolders: [{ uri: { fsPath: repoRoot } }],
      getConfiguration() {
        return {
          get(key, defaultValue) {
            const values = {
              autoStartServer: false,
              autoStartOllama: false,
              showManagedProcessesInTerminal: false,
              stopServerOnDeactivate: true,
              baseUrl: 'http://127.0.0.1:8005',
            };
            return Object.prototype.hasOwnProperty.call(values, key) ? values[key] : defaultValue;
          },
        };
      },
      onDidChangeWorkspaceFolders() {
        return createDisposable();
      },
      openTextDocument: async () => ({ getText: () => '' }),
    },
    window: {
      createOutputChannel() {
        return output;
      },
      createStatusBarItem() {
        return statusBar;
      },
      createTreeView() {
        return createDisposable();
      },
      createTerminal() {
        return terminal;
      },
      createWebviewPanel() {
        return panel;
      },
      onDidCloseTerminal() {
        return createDisposable();
      },
      showInputBox: async () => undefined,
      showInformationMessage: async () => undefined,
      showWarningMessage: async () => undefined,
      showErrorMessage: async () => undefined,
      withProgress: async (_options, task) => await task(),
      showTextDocument: async () => ({ selection: { isEmpty: true } }),
      activeTextEditor: undefined,
    },
  };

  return {
    vscode,
    commands,
    panel,
    output,
    statusBar,
    postedMessages,
    executedTasks,
    terminatedTasks,
    sendToExtension(message) {
      if (!receiveMessageHandler) {
        throw new Error('Webview message handler not registered');
      }
      return receiveMessageHandler(message);
    },
  };
}

test('panel ready handshake posts init and live server status back to the webview', async () => {
  const repoRoot = path.resolve(__dirname, '..', '..');
  const stub = createVscodeStub(repoRoot);
  const extensionModulePath = require.resolve('../out/extension.js');
  const originalLoad = Module._load;
  const originalFetch = global.fetch;

  global.fetch = async (url) => {
    if (String(url).endsWith('/healthz')) {
      return {
        ok: true,
        async json() {
          return {
            status: 'ok',
            workspace_root: repoRoot,
            model: 'qwen2.5-coder:7b',
            base_url: 'http://127.0.0.1:11434',
            ollama: {
              reachable: true,
              detail: 'reachable; configured model is available',
              model_available: true,
            },
            runtime: {
              manifest_version: 1,
              app_version: '0.1.0',
              routing_generation: 4,
              readiness_suite_version: 2,
            },
          };
        },
        async text() {
          return '';
        },
      };
    }
    if (String(url).endsWith('/api/tags')) {
      return {
        ok: true,
        async json() {
          return { models: [{ model: 'qwen2.5-coder:7b' }] };
        },
        async text() {
          return '';
        },
      };
    }
    throw new Error(`Unexpected fetch: ${url}`);
  };

  Module._load = function patchedLoad(request, parent, isMain) {
    if (request === 'vscode') {
      return stub.vscode;
    }
    return originalLoad.call(this, request, parent, isMain);
  };

  delete require.cache[extensionModulePath];
  const extension = require(extensionModulePath);

  try {
    extension.activate({ extensionPath: path.resolve(repoRoot, 'vscode-extension'), subscriptions: [] });
    await stub.commands.get('aicode.openPanel')();
    assert.equal(stub.postedMessages.length, 0);
    await stub.sendToExtension({ type: 'boot' });
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(
      stub.postedMessages.length,
      0,
      'Boot should not flush queued panel state before the webview is ready.',
    );
    await stub.sendToExtension({ type: 'ready' });
    await new Promise((resolve) => setTimeout(resolve, 0));
    await new Promise((resolve) => setTimeout(resolve, 0));

    const types = stub.postedMessages.map((message) => message.type);
    assert.ok(types.includes('init'), `Expected init message, got: ${types.join(', ')}`);
    assert.ok(types.includes('serverStatus'), `Expected serverStatus message, got: ${types.join(', ')}`);

    const initMessage = stub.postedMessages.find((message) => message.type === 'init');
    const statusMessages = stub.postedMessages.filter((message) => message.type === 'serverStatus');
    const statusMessage = statusMessages[statusMessages.length - 1];

    assert.equal(initMessage.status.healthy, false);
    assert.ok(statusMessage, 'Expected at least one serverStatus message');
    assert.equal(typeof statusMessage.status.healthy, 'boolean');
    assert.equal(typeof statusMessage.runtimeLabel, 'string');
    assert.ok(statusMessage.status.extensionBuild, 'Expected extension build metadata in server status');
    assert.equal(statusMessage.status.extensionBuild.runtime_mode, 'development-host');
  } finally {
    await extension.deactivate();
    for (const disposable of [stub.panel, stub.output, stub.statusBar]) {
      if (disposable && typeof disposable.dispose === 'function') {
        disposable.dispose();
      }
    }
    Module._load = originalLoad;
    global.fetch = originalFetch;
    delete require.cache[extensionModulePath];
  }
});

test('explicit start and stop commands use VS Code workspace tasks when available', async () => {
  const repoRoot = path.resolve(__dirname, '..', '..');
  const stub = createVscodeStub(repoRoot);
  const extensionModulePath = require.resolve('../out/extension.js');
  const originalLoad = Module._load;
  const originalFetch = global.fetch;

  global.fetch = async (url) => {
    if (String(url).endsWith('/healthz')) {
      if (!stub.executedTasks.includes('run:aicode-server')) {
        throw new Error('server offline');
      }
      return {
        ok: true,
        async json() {
          return {
            status: 'ok',
            workspace_root: repoRoot,
            model: 'qwen2.5-coder:7b',
            base_url: 'http://127.0.0.1:11434',
            ollama: {
              reachable: true,
              detail: 'reachable',
              model_available: true,
            },
            runtime: {
              manifest_version: 1,
              app_version: '0.1.0',
              routing_generation: 4,
              readiness_suite_version: 2,
            },
          };
        },
        async text() {
          return '';
        },
      };
    }
    if (String(url).endsWith('/api/tags')) {
      return {
        ok: true,
        async json() {
          return { models: [{ model: 'qwen2.5-coder:7b' }] };
        },
        async text() {
          return '';
        },
      };
    }
    throw new Error(`Unexpected fetch: ${url}`);
  };

  Module._load = function patchedLoad(request, parent, isMain) {
    if (request === 'vscode') {
      return stub.vscode;
    }
    return originalLoad.call(this, request, parent, isMain);
  };

  delete require.cache[extensionModulePath];
  const extension = require(extensionModulePath);

  try {
    extension.activate({ extensionPath: path.resolve(repoRoot, 'vscode-extension'), subscriptions: [] });
    await stub.commands.get('aicode.startServer')();
    assert.ok(stub.executedTasks.includes('run:aicode-server'));
    await stub.commands.get('aicode.stopServer')();
    assert.ok(stub.terminatedTasks.includes('run:aicode-server'));
  } finally {
    await extension.deactivate();
    for (const disposable of [stub.panel, stub.output, stub.statusBar]) {
      if (disposable && typeof disposable.dispose === 'function') {
        disposable.dispose();
      }
    }
    Module._load = originalLoad;
    global.fetch = originalFetch;
    delete require.cache[extensionModulePath];
  }
});

test('stream status/event updates stay scoped to the active task flow', async () => {
  const repoRoot = path.resolve(__dirname, '..', '..');
  const stub = createVscodeStub(repoRoot);
  const extensionModulePath = require.resolve('../out/extension.js');
  const originalLoad = Module._load;
  const originalFetch = global.fetch;
  const requestId = 'req-activity-1';
  const command = 'status';

  global.fetch = async (url) => {
    const target = String(url);
    if (target.endsWith('/healthz')) {
      return {
        ok: true,
        async json() {
          return {
            status: 'ok',
            workspace_root: repoRoot,
            model: 'qwen2.5-coder:7b',
            base_url: 'http://127.0.0.1:11434',
            ollama: {
              reachable: true,
              detail: 'reachable',
              model_available: true,
            },
            runtime: {
              manifest_version: 1,
              app_version: '0.1.0',
              routing_generation: 4,
              readiness_suite_version: 2,
            },
          };
        },
        async text() {
          return '';
        },
      };
    }
    if (target.endsWith('/api/tags')) {
      return {
        ok: true,
        async json() {
          return { models: [{ model: 'qwen2.5-coder:7b' }] };
        },
        async text() {
          return '';
        },
      };
    }
    if (target.endsWith('/v1/aicode/command/stream')) {
      const encoder = new TextEncoder();
      const payload = [
        'event: route\ndata: {"action":"status","confidence":0.9}\n\n',
        'event: status\ndata: {"message":"Executing command"}\n\n',
        'event: event\ndata: {"kind":"route","message":"Routed to status"}\n\n',
        'event: delta\ndata: {"text":"ok"}\n\n',
        'event: done\ndata: {"action":"status","confidence":0.9,"response":"ok","next_step":"If you want, I can run a full status validation next."}\n\n',
      ];
      let index = 0;
      return {
        ok: true,
        body: {
          getReader() {
            return {
              async read() {
                if (index >= payload.length) {
                  return { value: undefined, done: true };
                }
                const value = encoder.encode(payload[index]);
                index += 1;
                return { value, done: false };
              },
            };
          },
        },
      };
    }
    throw new Error(`Unexpected fetch: ${target}`);
  };

  Module._load = function patchedLoad(request, parent, isMain) {
    if (request === 'vscode') {
      return stub.vscode;
    }
    return originalLoad.call(this, request, parent, isMain);
  };

  delete require.cache[extensionModulePath];
  const extension = require(extensionModulePath);

  try {
    extension.activate({ extensionPath: path.resolve(repoRoot, 'vscode-extension'), subscriptions: [] });
    await stub.commands.get('aicode.openPanel')();
    await stub.sendToExtension({ type: 'ready' });
    await new Promise((resolve) => setTimeout(resolve, 0));
    stub.postedMessages.length = 0;

    await stub.sendToExtension({ type: 'ask', requestId, command });
    await new Promise((resolve) => setTimeout(resolve, 0));
    await new Promise((resolve) => setTimeout(resolve, 0));

    const scoped = stub.postedMessages
      .filter((message) => message.requestId === requestId)
      .filter((message) => ['streamStart', 'streamRoute', 'streamStatus', 'streamEvent', 'streamDone'].includes(message.type))
      .map((message) => message.type);

    assert.deepEqual(scoped, ['streamStart', 'streamRoute', 'streamStatus', 'streamEvent', 'streamDone']);
  } finally {
    await extension.deactivate();
    for (const disposable of [stub.panel, stub.output, stub.statusBar]) {
      if (disposable && typeof disposable.dispose === 'function') {
        disposable.dispose();
      }
    }
    Module._load = originalLoad;
    global.fetch = originalFetch;
    delete require.cache[extensionModulePath];
  }
});
