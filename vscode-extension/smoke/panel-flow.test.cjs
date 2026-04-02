
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
  let receiveMessageHandler;
  let disposeHandler;
  const postedMessages = [];

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
    await stub.sendToExtension({ type: 'ready' });
    await new Promise((resolve) => setTimeout(resolve, 0));
    await new Promise((resolve) => setTimeout(resolve, 0));

    const types = stub.postedMessages.map((message) => message.type);
    assert.ok(types.includes('init'), `Expected init message, got: ${types.join(', ')}`);
    assert.ok(types.includes('serverStatus'), `Expected serverStatus message, got: ${types.join(', ')}`);

    const initMessage = stub.postedMessages.find((message) => message.type === 'init');
    const statusMessage = stub.postedMessages.find((message) => message.type === 'serverStatus');

    assert.equal(initMessage.status.healthy, false);
    assert.equal(statusMessage.status.healthy, true);
    assert.equal(statusMessage.runtimeLabel, 'Runtime: healthy');
    assert.ok(statusMessage.status.extensionBuild, 'Expected extension build metadata in server status');
    assert.equal(statusMessage.status.extensionBuild.runtime_mode, 'development-host');
    assert.equal(statusMessage.status.integrityIssue, undefined);
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
