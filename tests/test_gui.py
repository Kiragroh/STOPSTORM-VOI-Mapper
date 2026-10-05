import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from voi_mapper.catalogue import load_catalogues
from voi_mapper.gui import Application, Server
from voi_mapper.ranking import lexical_rank, parse_input, finalize, parse_model, model_payload, review_guard
from voi_mapper.ollama import Ollama, Cancelled


class RankingTests(unittest.TestCase):
    def setUp(self):
        self.catalogue = load_catalogues(Path('missing-file'))['stopstorm']

    def test_exact_alias_and_weak(self):
        self.assertEqual(lexical_rank('Heart', self.catalogue)[0]['score'], 100)
        top = lexical_rank('Lunge links', self.catalogue)[0]
        self.assertEqual((top['name'], top['score']), ('Lung Left', 95))
        self.assertLess(lexical_rank('zxqqw987', self.catalogue)[0]['score'], 90)

    def test_laterality_and_review(self):
        self.assertEqual(review_guard('Lung_R', 'Lung Left', 'stopstorm'), 'Laterality conflict')
        self.assertEqual(review_guard('Lung_R', 'Lung_L', 'tg263'), 'Laterality conflict')
        for n in ['PTV_1', 'Heart_PRV', 'Vena cava', 'ICD lead']:
            target = 'ICD' if n == 'ICD lead' else 'Target_PTV'
            self.assertTrue(review_guard(n, target, 'stopstorm'))

    def test_candidates_are_not_invented(self):
        result = lexical_rank('GTV', self.catalogue)
        self.assertEqual(result[0]['name'], 'CardTV')
        self.assertEqual(lexical_rank('', self.catalogue), [])

    def test_missing_side_and_tied_scores(self):
        self.assertIn('Side not specified', review_guard('lung', 'Lung Left', 'stopstorm'))
        self.assertEqual(review_guard('LAD', 'H_CA_left anterior descending artery', 'stopstorm'), '')
        rows=[{'case':'A','name':'uncertain','candidates':[
            {'name':'Heart','score':95,'warning':''},{'name':'Lungs','score':94,'warning':''}]}]
        self.assertEqual(finalize(rows)[0]['proposal'], '')

    def test_status_does_not_invent_gpu(self):
        client=Ollama('http://localhost:11434')
        with patch.object(client,'request',return_value={'models':[]}), patch('voi_mapper.ollama.subprocess.run',side_effect=FileNotFoundError):
            status=client.status()
            self.assertTrue(status['online'])
            self.assertIsNone(status['gpu']['detected'])
            self.assertEqual(status['loaded'],[])

    def test_status_offline(self):
        client=Ollama('http://localhost:11434')
        with patch.object(client,'request',side_effect=OSError), patch('voi_mapper.ollama.subprocess.run',side_effect=FileNotFoundError):
            status=client.status()
            self.assertFalse(status['online'])
            self.assertIsNone(status['gpu']['detected'])

    def test_queue_context_and_cancellation(self):
        client=Ollama('http://localhost:11436','token-not-read-in-test')
        def request(path,payload=None,**kwargs):
            if path=='/api/tags':return {'models':[{'name':'qwen'}]}
            if path=='/api/show':return {'capabilities':['completion']}
            if path=='/jobs/ollama':
                self.assertEqual(payload['context']['script_name'],'gui.py')
                self.assertEqual(len(payload['context']['script_sha256']),64)
                return {'job_id':'owned-job'}
            if path.endswith('/cancel'):return {'state':'cancelling'}
            if path=='/jobs/owned-job':return {'state':'cancelled'}
            raise AssertionError(path)
        with patch.object(client,'request',side_effect=request) as call:
            calls=iter([False,True,True])
            with self.assertRaises(Cancelled):client.chat({'model':'qwen'},lambda:next(calls),lambda x:None)
            self.assertTrue(any(c.args[0]=='/jobs/owned-job/cancel' for c in call.call_args_list))

    def test_csv_and_limits(self):
        rows = parse_input('Case,ROI_ID,StructureName\nA,1,"Heart, whole"\n', True)
        self.assertEqual(rows[0]['name'], 'Heart, whole')
        for text in ['', '\n'.join(['Heart']*501), 'x'*257]:
            with self.assertRaises(ValueError):
                parse_input(text)
        with self.assertRaises(ValueError):
            parse_input('Case,ROI_ID,StructureName\nA,1,Heart\nA,1,Lungs', True)

    def test_duplicates_only_with_case(self):
        rows = parse_input('Heart\nHerz', case='A')
        for row in rows:
            row['candidates'] = lexical_rank(row['name'], self.catalogue)
        finalize(rows)
        self.assertTrue(all(r['state'] == 'conflict' and not r['proposal'] for r in rows))
        for row in rows:
            row['case'] = ''
        self.assertTrue(all(r['proposal'] == 'Heart' for r in finalize(rows)))

    def test_model_validation_and_sort(self):
        shortlist = lexical_rank('Heart', self.catalogue)
        def response(items):
            return {'message': {'content': json.dumps({'candidates': items})}}
        result = parse_model(response([{'id':0,'score':99}]), shortlist)
        self.assertEqual(result[0]['name'], 'Heart')
        self.assertEqual(parse_model(response([]), shortlist), [])
        for items in [[{'id':0,'score':101}], [{'id':0,'score':True}],
                      [{'id':999,'score':99}], [{'id':0,'score':90}]*2]:
            with self.assertRaises(ValueError):
                parse_model(response(items), shortlist)

    def test_no_identifiers_in_prompt(self):
        payload = model_payload('Heart', self.catalogue, lexical_rank('Heart',self.catalogue), 'qwen')
        self.assertNotIn('case', json.dumps(payload).lower())
        self.assertIn('NOT a calibrated probability', payload['messages'][0]['content'])

    def test_remote_endpoints_refused(self):
        for endpoint in ['http://example.org:11434','https://localhost:11434','http://localhost:11434/api']:
            with self.assertRaises(ValueError): Ollama(endpoint)

    def test_remote_models_filtered(self):
        client=Ollama('http://localhost:11434')
        with patch.object(client,'request',return_value={'models':[{'name':'local'}, {'name':'remote','remote_host':'https://example.org'}]}):
            self.assertEqual(client.models(), [{'name':'local'}])

    def test_cloud_alias_rejected_before_inference(self):
        client=Ollama('http://localhost:11434')
        with patch.object(client,'models',return_value=[{'name':'local-alias'}]), patch.object(client,'request',return_value={'remote_host':'https://example.org'}) as request:
            with self.assertRaisesRegex(ValueError,'Cloud-backed'):
                client.chat({'model':'local-alias'},lambda:False,lambda s:None)
            self.assertEqual(request.call_args.args[0],'/api/show')

    def test_cancel_before_inference(self):
        client=Ollama('http://localhost:11434')
        with self.assertRaises(Cancelled):client.chat({},lambda:True,lambda s:None)


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=Application('http://127.0.0.1:1',Path('missing-file'))
        cls.server=Server(('127.0.0.1',0),cls.app)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()

    def request(self,path,body=None,headers=None):
        h={'Content-Type':'application/json','X-VOI-CSRF':self.app.csrf}
        h.update(headers or {})
        req=urllib.request.Request(self.url+path,data=json.dumps(body).encode() if body is not None else None,headers=h)
        return urllib.request.urlopen(req,timeout=5)

    def test_local_static_and_config(self):
        with self.request('/') as r:
            self.assertIn(b'Name matcher',r.read())
            self.assertIn("frame-ancestors 'none'",r.headers['Content-Security-Policy'])
        with self.request('/api/config') as r:self.assertEqual(json.load(r)['csrf'],self.app.csrf)

    def test_rebinding_csrf_and_traversal(self):
        for path,body,headers in [('/api/config',None,{'Host':'evil.test'}),
            ('/api/config',None,{'Origin':'https://evil.test'}),
            ('/api/config',None,{'Sec-Fetch-Site':'cross-site'}),
            ('/api/jobs',{'text':'Heart'},{'X-VOI-CSRF':'bad'})]:
            with self.assertRaises(urllib.error.HTTPError) as exc:self.request(path,body,headers)
            self.assertEqual(exc.exception.code,403)
        with self.assertRaises(urllib.error.HTTPError):self.request('/../core.py')

    def test_batch_export_safe_cells(self):
        with self.request('/api/jobs',{'text':'Heart\nHerz\n=SUM(A1)','case':'A'}) as r:identifier=json.load(r)['id']
        for _ in range(50):
            result=self.app.snapshot(identifier)
            if result['state']!='running':break
            time.sleep(.01)
        self.assertEqual(result['state'],'completed')
        self.assertEqual(result['rows'][0]['state'],'conflict')
        with self.request('/api/jobs/'+identifier+'/export') as r:
            csv=r.read().decode('utf-8-sig')
            self.assertIn("'=SUM(A1)",csv)
            self.assertIn('ScoreBasis',csv)

    def test_bad_inputs_and_model_errors(self):
        for body in [{}, {'text':'Heart','vocabulary':'fake'}, {'text':'Heart','mode':'llm'}]:
            with self.assertRaises(urllib.error.HTTPError) as exc:self.request('/api/jobs',body)
            self.assertEqual(exc.exception.code,400)

    def test_cancel_and_failure_states(self):
        entered=threading.Event()
        def waiting(payload,cancelled,progress):
            entered.set()
            while not cancelled():time.sleep(.01)
            raise Cancelled()
        with patch.object(self.app.ollama,'chat',side_effect=waiting):
            with self.request('/api/jobs',{'text':'Heart','mode':'llm','model':'test'}) as r:identifier=json.load(r)['id']
            self.assertTrue(entered.wait(3))
            with self.request('/api/jobs/'+identifier+'/cancel',{}) as r:self.assertTrue(json.load(r)['ok'])
            for _ in range(100):
                job=self.app.snapshot(identifier)
                if job['state']=='cancelled':break
                time.sleep(.01)
            self.assertEqual(job['state'],'cancelled')
        with patch.object(self.app.ollama,'chat',side_effect=ValueError('Model not ready')):
            with self.request('/api/jobs',{'text':'Heart','mode':'llm','model':'test'}) as r:identifier=json.load(r)['id']
            for _ in range(100):
                job=self.app.snapshot(identifier)
                if job['state']=='failed':break
                time.sleep(.01)
            self.assertEqual(job['state'],'failed')
            self.assertEqual(job['error'],'Model not ready')


if __name__=='__main__':unittest.main()
