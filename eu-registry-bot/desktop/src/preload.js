const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    // File dialogs
    selectFile: (options) => ipcRenderer.invoke('select-file', options),
    selectDirectory: () => ipcRenderer.invoke('select-directory'),

    // External links
    openExternal: (url) => ipcRenderer.invoke('open-external', url),

    // API URL
    getApiUrl: () => ipcRenderer.invoke('get-api-url'),

    // Platform info
    platform: process.platform
});
