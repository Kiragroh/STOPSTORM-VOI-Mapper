"""Loopback-only Ollama transport and optional durable shared-queue adapter."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request
import uuid

from .core import check_endpoint


class Cancelled(Exception):
    pass


class Ollama:
    def __init__(self, endpoint, token_file=None):
        self.endpoint = check_endpoint(endpoint)
        self.token_file = Path(token_file) if token_file else None

    def request(self, path, payload=None, timeout=5, private=False, key=None):
        headers = {'Content-Type': 'application/json'}
        if private:
            headers['X-GPU-Token'] = self.token_file.read_text().strip()
        if key:
            headers['Idempotency-Key'] = key
        req = urllib.request.Request(self.endpoint + path,
            data=None if payload is None else json.dumps(payload).encode(), headers=headers)
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                raise ValueError('Redirect refused')
        with urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect).open(req, timeout=timeout) as response:
            return json.load(response)

    def models(self):
        return [m for m in self.request('/api/tags')['models']
                if not m.get('remote_host') and not m.get('remote_model')
                and not m.get('name', '').endswith((':cloud', '-cloud'))]

    def status(self):
        result = {'online': False, 'models': [], 'loaded': [], 'gpu': {'detected': None},
                  'coordinated': bool(self.token_file), 'queue_paused': None, 'error': ''}
        try:
            result['models'] = [{'name': m['name'], 'digest': m.get('digest', ''),
                                 'details': m.get('details', {})} for m in self.models()]
            result['online'] = True
            result['loaded'] = [{'name': m['name'], 'size_vram': m.get('size_vram', 0)}
                                for m in self.request('/api/ps')['models']]
        except (OSError, ValueError, KeyError):
            result['error'] = 'Ollama unavailable or status incomplete. Check the configured endpoint.'
        try:
            command = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.free,memory.total',
                '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=3,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if command.returncode == 0:
                devices = []
                for line in command.stdout.splitlines():
                    name, free, total = line.rsplit(',', 2)
                    devices.append({'name': name.strip(), 'free_mb': int(free), 'total_mb': int(total)})
                result['gpu'] = {'detected': bool(devices), 'devices': devices}
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
        if self.token_file:
            try:
                status = self.request('/status')
                result['queue_paused'] = status.get('paused')
            except (OSError, ValueError):
                result['error'] = 'Coordinator status unavailable.'
        return result

    def chat(self, payload, cancelled, progress):
        if cancelled():
            raise Cancelled()
        if payload['model'] not in {m['name'] for m in self.models()}:
            raise ValueError('Selected model is not installed locally. Refresh the model list.')
        if not self.token_file:
            info = self.request('/api/show', {'model': payload['model']})
            if info.get('remote_host') or info.get('remote_model'):
                raise ValueError('Cloud-backed model aliases are not supported.')
        if not self.token_file:
            # Detect the coordinator rather than silently losing ownership metadata.
            try:
                health = self.request('/health', timeout=2)
            except (OSError, ValueError):
                health = {}
            if health.get('service') == 'local-gpu-coordinator':
                raise ValueError('This endpoint requires --coordinator-token-file for attributed jobs.')
            progress('Model running; stop takes effect after the current request')
            result = self.request('/api/chat', payload, timeout=180)
            if cancelled():
                raise Cancelled()
            return result
        script = Path(__file__).with_name('gui.py').resolve()
        data = {'route': '/api/chat', 'owner': 'STOPSTORM-VOI-Mapper', 'priority': 10,
                'context': {'script': str(script), 'script_name': script.name,
                            'script_sha256': hashlib.sha256(script.read_bytes()).hexdigest(),
                            'chat_id': os.getenv('CODEX_THREAD_ID', '')}, 'body': payload}
        job = self.request('/jobs/ollama', data, private=True, key=uuid.uuid4().hex)['job_id']
        cancel_sent = False
        while True:
            if cancelled() and not cancel_sent:
                self.request('/jobs/' + job + '/cancel', {}, private=True)
                cancel_sent = True
            state = self.request('/jobs/' + job, private=True)
            progress('Coordinator: ' + state['state'] + ('; cancelling current request' if cancel_sent else ''))
            if state['state'] == 'completed':
                if cancelled():
                    raise Cancelled()
                return self.request('/jobs/' + job + '/result', private=True, timeout=30)
            if state['state'] in {'failed', 'cancelled', 'interrupted', 'recovery_blocked'}:
                if cancelled():
                    raise Cancelled()
                raise ValueError('Coordinator job ended: ' + state['state'])
            time.sleep(.5)
