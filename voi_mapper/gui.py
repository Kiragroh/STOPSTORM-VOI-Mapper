"""Local, ephemeral name-ranking UI. Never writes to the source DICOM dataset."""
import argparse
from collections import OrderedDict
import csv
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlsplit
import webbrowser

from .catalogue import DEFAULT_TG, import_tg263, load_catalogues
from .ollama import Cancelled, Ollama
from .ranking import finalize, lexical_rank, model_payload, parse_input, parse_model
from .__main__ import safe_cell

STATIC = Path(__file__).with_name('static')


class Application:
    def __init__(self, endpoint, catalogue=DEFAULT_TG, token_file=None):
        self.catalogues = load_catalogues(catalogue)
        self.ollama = Ollama(endpoint, token_file)
        self.csrf = secrets.token_urlsafe(32)
        self.jobs = OrderedDict()
        self.lock = threading.RLock()
        self.status_lock = threading.Lock()
        self.cached_status = (0, None)

    def status(self):
        with self.status_lock:
            if time.monotonic() - self.cached_status[0] > 8:
                self.cached_status = (time.monotonic(), self.ollama.status())
            return self.cached_status[1]

    def start(self, data):
        vocabulary = data.get('vocabulary', 'stopstorm')
        mode = data.get('mode', 'lexical')
        if vocabulary not in self.catalogues or mode not in {'lexical', 'llm'}:
            raise ValueError('Unsupported vocabulary or ranking mode.')
        model = data.get('model', '')
        if mode == 'llm' and (not isinstance(model, str) or not model or len(model) > 200):
            raise ValueError('Select an installed local model.')
        rows = parse_input(data.get('text', ''), data.get('csv', False), data.get('case', ''))
        with self.lock:
            if any(j['state'] in {'running', 'cancelling'} for j in self.jobs.values()):
                raise ValueError('Another batch is active. Wait or stop it first.')
            while len(self.jobs) >= 20:
                self.jobs.popitem(last=False)
            identifier = secrets.token_urlsafe(16)
            self.jobs[identifier] = {'id': identifier, 'state': 'running', 'done': 0, 'total': len(rows),
                'message': 'Preparing candidates', 'cancel': False, 'rows': [], 'mode': mode,
                'vocabulary': vocabulary, 'catalogue_version': self.catalogues[vocabulary]['version'],
                'model': model if mode == 'llm' else '', 'error': ''}
        threading.Thread(target=self.run, args=(identifier, rows), daemon=True).start()
        return identifier

    def run(self, identifier, rows):
        job = self.jobs[identifier]
        catalogue = self.catalogues[job['vocabulary']]
        cache = {}
        def cancelled():
            return job['cancel']
        def progress(message):
            with self.lock:
                job['message'] = message
        try:
            for row in rows:
                if cancelled():
                    raise Cancelled()
                name = row['name']
                if name not in cache:
                    shortlist = lexical_rank(name, catalogue, 40)
                    if job['mode'] == 'llm' and shortlist:
                        payload = model_payload(name, catalogue, shortlist, job['model'])
                        candidates = parse_model(self.ollama.chat(payload, cancelled, progress), shortlist)
                    else:
                        candidates = shortlist[:5]
                    cache[name] = candidates
                with self.lock:
                    job['rows'].append({**row, 'candidates': cache[name]})
                    job['done'] += 1
            with self.lock:
                finalize(job['rows'])
                job.update(state='completed', message='Review ready')
        except Cancelled:
            with self.lock:
                finalize(job['rows'])
                job.update(state='cancelled', message='Stopped; partial results retained')
        except Exception as exc:
            with self.lock:
                finalize(job['rows'])
                message = str(exc) if isinstance(exc, ValueError) else type(exc).__name__ + ': model request failed; check Ollama.'
                job.update(state='failed', message='Stopped with an error', error=message[:300])

    def snapshot(self, identifier):
        with self.lock:
            return json.loads(json.dumps(self.jobs[identifier]))

    def export(self, identifier):
        job = self.snapshot(identifier)
        if job['state'] in {'running', 'cancelling'}:
            raise ValueError('Wait for the batch to finish before exporting.')
        out = io.StringIO(newline='')
        writer = csv.writer(out)
        writer.writerow(['Case', 'ROI_ID', 'StructureName', 'Vocabulary', 'RankingMode', 'Model',
                         'Rank', 'Candidate', 'Score', 'ScoreBasis', 'Proposal', 'ReviewState', 'Note', 'RunState'])
        for row in job['rows']:
            for i, c in enumerate(row['candidates'] or [{}]):
                writer.writerow([safe_cell(str(v)) for v in [row['case'], row['roi_id'], row['name'],
                    job['catalogue_version'], job['mode'], job['model'], i + 1 if c else '',
                    c.get('name', ''), c.get('score', ''), c.get('basis', ''), row['proposal'],
                    row['state'], row['note'], job['state']]])
        return '\ufeff' + out.getvalue()


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, app):
        self.app = app
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def permitted(self):
        port = self.server.server_port
        hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
        host = self.headers.get('Host')
        origin = self.headers.get('Origin')
        return (host in hosts and (origin is None or origin == 'http://' + host)
                and self.headers.get('Sec-Fetch-Site', 'none') in {'none', 'same-origin'})

    def send(self, status, data, content_type='application/json; charset=utf-8', attachment=False):
        body = json.dumps(data).encode() if content_type.startswith('application/json') else data.encode() if isinstance(data, str) else data
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        if attachment:
            self.send_header('Content-Disposition', 'attachment; filename="voi-ranking.csv"')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # Closing a browser tab must not turn a completed response into a server error.

    def do_GET(self):
        if not self.permitted():
            return self.send(403, {'error': 'Local same-origin requests only'})
        app = self.server.app
        path = urlsplit(self.path).path
        try:
            if path == '/api/config':
                return self.send(200, {'csrf': app.csrf, 'endpoint': app.ollama.endpoint,
                    'catalogues': [{'id': k, 'label': v['version'], 'count': len(v['entries'])}
                                   for k, v in app.catalogues.items()]})
            if path == '/api/status':
                return self.send(200, app.status())
            parts = path.strip('/').split('/')
            if parts[:2] == ['api', 'jobs'] and len(parts) in {3, 4}:
                if len(parts) == 4 and parts[3] == 'export':
                    return self.send(200, app.export(parts[2]), 'text/csv; charset=utf-8', True)
                if len(parts) == 3:
                    return self.send(200, app.snapshot(parts[2]))
            assets = {'/': ('index.html', 'text/html; charset=utf-8'),
                      '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                      '/style.css': ('style.css', 'text/css; charset=utf-8'),
                      '/icons.svg': ('icons.svg', 'image/svg+xml')}
            if path in assets:
                name, mime = assets[path]
                return self.send(200, (STATIC / name).read_bytes(), mime)
            return self.send(404, {'error': 'Not found'})
        except KeyError:
            return self.send(404, {'error': 'Run expired or not found'})
        except ValueError as exc:
            return self.send(400, {'error': str(exc)})

    def do_POST(self):
        if not self.permitted() or not secrets.compare_digest(self.headers.get('X-VOI-CSRF', ''), self.server.app.csrf):
            return self.send(403, {'error': 'Local session required'})
        try:
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size <= 1_000_000 or not self.headers.get('Content-Type', '').startswith('application/json'):
                return self.send(413, {'error': 'Expected JSON, maximum 1 MB'})
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError('Expected an object')
            path = urlsplit(self.path).path
            if path == '/api/jobs':
                return self.send(202, {'id': self.server.app.start(data)})
            parts = path.strip('/').split('/')
            if len(parts) == 4 and parts[:2] == ['api', 'jobs'] and parts[3] == 'cancel':
                with self.server.app.lock:
                    job = self.server.app.jobs[parts[2]]
                    if job['state'] == 'running':
                        job.update(cancel=True, state='cancelling')
                return self.send(200, {'ok': True})
            return self.send(404, {'error': 'Not found'})
        except (ValueError, TypeError, AttributeError) as exc:
            return self.send(400, {'error': str(exc)[:250]})
        except KeyError:
            return self.send(404, {'error': 'Run not found'})


def main():
    parser = argparse.ArgumentParser(description='Local STOPSTORM VOI name-ranking tester')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--endpoint', default='http://127.0.0.1:11434')
    parser.add_argument('--catalogue', type=Path, default=DEFAULT_TG)
    parser.add_argument('--install-tg263', action='store_true', help='Download and import the pinned official worksheet (requires xlrd)')
    parser.add_argument('--coordinator-token-file', type=Path, help='Shared GPU coordinator credential; stays server-side')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    if args.install_tg263:
        import_tg263(destination=args.catalogue)
    app = Application(args.endpoint, args.catalogue, args.coordinator_token_file)
    server = Server(('127.0.0.1', args.port), app)
    url = f'http://127.0.0.1:{server.server_port}'
    print(f'VOI tester: {url}', flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
