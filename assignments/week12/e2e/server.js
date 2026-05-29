const http = require('http');

const PORT = 3050;

const server = http.createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  res.end(`
    <!DOCTYPE html>
    <html>
      <head>
        <title>Logos-Log Mock Portal</title>
        <style>
          body { font-family: sans-serif; text-align: center; margin-top: 50px; background: #fafafa; }
          button { padding: 10px 20px; font-size: 16px; cursor: pointer; background: #0070f3; color: white; border: none; border-radius: 5px; }
          #result-message { font-weight: bold; color: green; margin-top: 20px; }
        </style>
      </head>
      <body>
        <h1>Welcome to Logos-Log E2E Portal</h1>
        <p>This is a mock dashboard to verify E2E test flows and feature toggles.</p>
        <button id="toggle-flag">Trigger Feature Flag</button>
        <p id="result-message"></p>
        <script>
          document.getElementById('toggle-flag').addEventListener('click', () => {
            document.getElementById('result-message').innerText = 'Feature Flag Active!';
          });
        </script>
      </body>
    </html>
  `);
});

server.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});
