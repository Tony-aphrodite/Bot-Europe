const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow;
let pythonProcess = null;
const API_PORT = 5000;

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

    // Open DevTools in development
    if (process.env.NODE_ENV === 'development') {
        mainWindow.webContents.openDevTools();
    }

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

function startPythonAPI() {
    const pythonPath = process.platform === 'win32' ? 'python' : 'python3';
    const apiScript = path.join(__dirname, '..', '..', 'api', 'server.py');

    pythonProcess = spawn(pythonPath, [apiScript], {
        cwd: path.join(__dirname, '..', '..'),
        env: { ...process.env, FLASK_PORT: API_PORT }
    });

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
        pythonProcess.kill();
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

// App lifecycle
app.whenReady().then(() => {
    startPythonAPI();

    // Wait for API to start
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
