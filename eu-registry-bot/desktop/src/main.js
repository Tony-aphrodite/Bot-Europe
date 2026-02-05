const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

let mainWindow;
let pythonProcess = null;
const API_PORT = 5000;

function getResourcePath() {
    if (app.isPackaged) {
        return path.dirname(app.getPath('exe'));
    }
    return path.join(__dirname, '..', '..');
}

function getApiServerPath() {
    const resourcePath = getResourcePath();

    // Check for bundled executable (production)
    const exePaths = [
        path.join(resourcePath, 'api_server.exe'),
        path.join(resourcePath, 'api_server'),
    ];

    for (const exePath of exePaths) {
        if (fs.existsSync(exePath)) {
            return { type: 'exe', path: exePath };
        }
    }

    // Fall back to Python script (development)
    const scriptPath = path.join(resourcePath, 'api', 'server.py');
    if (fs.existsSync(scriptPath)) {
        return { type: 'python', path: scriptPath };
    }

    return null;
}

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        minWidth: 900,
        minHeight: 600,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js')
        },
        titleBarStyle: 'hiddenInset',
        frame: process.platform === 'darwin' ? true : true,
        backgroundColor: '#1a1a2e',
        icon: path.join(__dirname, 'assets', 'icon.png')
    });

    mainWindow.loadFile(path.join(__dirname, 'renderer', 'pages', 'index.html'));

    if (process.env.NODE_ENV === 'development') {
        mainWindow.webContents.openDevTools();
    }

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

function startPythonAPI() {
    const apiServer = getApiServerPath();
    const cwd = getResourcePath();

    if (!apiServer) {
        console.error('API server not found!');
        return;
    }

    console.log(`Starting API: ${apiServer.type} - ${apiServer.path}`);

    if (apiServer.type === 'exe') {
        pythonProcess = spawn(apiServer.path, [], {
            cwd: cwd,
            env: { ...process.env, FLASK_PORT: API_PORT }
        });
    } else {
        const pythonPath = process.platform === 'win32' ? 'python' : 'python3';
        pythonProcess = spawn(pythonPath, [apiServer.path], {
            cwd: cwd,
            env: { ...process.env, FLASK_PORT: API_PORT }
        });
    }

    pythonProcess.stdout.on('data', (data) => {
        console.log(`API: ${data}`);
    });

    pythonProcess.stderr.on('data', (data) => {
        console.error(`API Error: ${data}`);
    });

    pythonProcess.on('close', (code) => {
        console.log(`API process exited with code ${code}`);
    });
}

function stopPythonAPI() {
    if (pythonProcess) {
        if (process.platform === 'win32') {
            spawn('taskkill', ['/pid', pythonProcess.pid, '/f', '/t']);
        } else {
            pythonProcess.kill();
        }
        pythonProcess = null;
    }
}

// IPC Handlers
ipcMain.handle('select-file', async (event, options) => {
    const result = await dialog.showOpenDialog(mainWindow, {
        properties: ['openFile'],
        filters: options.filters || [{ name: 'All Files', extensions: ['*'] }]
    });
    return result.filePaths[0] || null;
});

ipcMain.handle('select-directory', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
        properties: ['openDirectory']
    });
    return result.filePaths[0] || null;
});

ipcMain.handle('open-external', async (event, url) => {
    await shell.openExternal(url);
});

ipcMain.handle('get-api-url', () => {
    return `http://localhost:${API_PORT}`;
});

ipcMain.handle('get-app-path', () => {
    return getResourcePath();
});

// App lifecycle
app.whenReady().then(() => {
    startPythonAPI();

    setTimeout(() => {
        createWindow();
    }, 2000);
});

app.on('window-all-closed', () => {
    stopPythonAPI();
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', () => {
    if (mainWindow === null) {
        createWindow();
    }
});

app.on('before-quit', () => {
    stopPythonAPI();
});
