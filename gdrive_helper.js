#!/usr/bin/env node
// Google Drive connector helper — called as a subprocess from Python via gdrive.py
// Uses @replit/connectors-sdk for authenticated requests to Google Drive API

const { ReplitConnectors } = require('@replit/connectors-sdk');

async function main() {
  const [,, cmd, ...args] = process.argv;
  const c = new ReplitConnectors();

  async function driveGet(path) {
    const r = await c.proxy('google-drive', path, { method: 'GET' });
    return r.json();
  }

  try {
    if (cmd === 'list') {
      const folderId = args[0] || 'root';
      const q = folderId === 'root'
        ? `'root' in parents and trashed=false`
        : `'${folderId}' in parents and trashed=false`;
      const fields = 'files(id,name,mimeType,size,modifiedTime,iconLink,webViewLink)';
      const data = await driveGet(`/drive/v3/files?q=${encodeURIComponent(q)}&fields=${encodeURIComponent(fields)}&orderBy=folder,name&pageSize=100`);
      console.log(JSON.stringify(data));

    } else if (cmd === 'search') {
      const query = args.join(' ');
      const q = `name contains '${query.replace(/'/g,"\\'")}' and trashed=false`;
      const fields = 'files(id,name,mimeType,size,modifiedTime,webViewLink)';
      const data = await driveGet(`/drive/v3/files?q=${encodeURIComponent(q)}&fields=${encodeURIComponent(fields)}&orderBy=modifiedTime desc&pageSize=50`);
      console.log(JSON.stringify(data));

    } else if (cmd === 'download') {
      const fileId = args[0];
      const mimeType = args[1] || '';
      let path;
      if (mimeType === 'application/vnd.google-apps.document') {
        path = `/drive/v3/files/${fileId}/export?mimeType=text%2Fplain`;
      } else {
        path = `/drive/v3/files/${fileId}?alt=media`;
      }
      const r = await c.proxy('google-drive', path, { method: 'GET' });
      const buf = Buffer.from(await r.arrayBuffer());
      process.stdout.write(buf);

    } else if (cmd === 'meta') {
      const fileId = args[0];
      const data = await driveGet(`/drive/v3/files/${fileId}?fields=id,name,mimeType,size`);
      console.log(JSON.stringify(data));

    } else {
      console.error('Unknown command:', cmd);
      process.exit(1);
    }
  } catch (e) {
    process.stderr.write(JSON.stringify({ error: e.message }) + '\n');
    process.exit(1);
  }
}

main();
