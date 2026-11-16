import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from brochure.app import create_app, select_evidence
from brochure.core import Engine, InputError, parse_page, normalize_url, public_addresses, PublicFetcher
from brochure.storage import Store

class TestProject(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(self.temp.name)
        self.engine=Engine(self.store)
        self.client=TestClient(create_app(self.temp.name))
    def tearDown(self):
        self.client.close()
        self.temp.cleanup()
    def test_demo_has_sources(self):
        r=self.engine.run('Studio','',demo=True)
        self.assertEqual(len(r['pages']),4)
        self.assertIn('synthetic', r['markdown'])
        self.assertTrue(all(x in {e['id'] for e in r['evidence']} for x in r['selected_ids']))
    def test_cache_and_refresh(self):
        self.engine.run('Studio','',demo=True)
        self.assertEqual(self.engine.run('Studio','',demo=True)['cache_hits'],4)
        self.assertEqual(self.engine.run('Studio','',demo=True,refresh=True)['cache_hits'],0)
    def test_runs_reopen_from_new_store(self):
        r=self.engine.run('Studio','',demo=True)
        self.assertEqual(Store(self.temp.name).get(r['id'])['markdown'],r['markdown'])
    def test_immutable_snapshot(self):
        r=self.engine.run('Studio','',demo=True)
        self.engine.run('Other','',demo=True,refresh=True)
        self.assertEqual(self.store.get(r['id'])['company'],'Studio')
    def test_unknown_ai_evidence_rejected(self):
        with self.assertRaises(InputError):
            self.engine.run('Studio','',demo=True,ai=True,selector=lambda *_:['E999'])
        self.assertEqual(self.store.recent(),[])
    def test_ai_only_selects_source_excerpts(self):
        r=self.engine.run('Studio','',demo=True,ai=True,selector=lambda *_:['E2','E1','E2'])
        self.assertEqual(r['selected_ids'],['E2','E1'])
        self.assertIn(r['evidence'][1]['text'],r['markdown'])
    def test_malformed_ai_selection(self):
        for output in [None,[],{},[{}], 'E1']:
            with self.assertRaises(InputError):
                self.engine.run('Studio','',demo=True,ai=True,selector=lambda *_:output)
    def test_parser_excludes_script_and_navigation(self):
        p=parse_page('https://company.example/','<title>Title</title><nav>Ignore</nav><script>bad()</script><p>A reliable sentence describing the company.</p>')
        self.assertNotIn('bad',p.text)
        self.assertNotIn('Ignore',p.text)
        self.assertEqual(p.title,'Title')
    def test_same_origin_links_only(self):
        p=parse_page('https://company.example/','<a href="/about#x">About</a><a href="https://elsewhere.example/">No</a><a href="javascript:alert(1)">No</a>')
        self.assertEqual(p.links,['https://company.example/about'])
    def test_url_credentials_and_schemes(self):
        for u in ['file:///etc/passwd','https://u:p@example.com','ftp://example.com','http://example.com:8080','https://example.com:80']:
            with self.assertRaises(InputError):normalize_url(u)
    def test_normalization(self):
        self.assertEqual(normalize_url('https://EXAMPLE.com:443/about#x'),'https://example.com/about')
    def test_private_and_mixed_dns_rejected(self):
        for addresses in [['127.0.0.1'],['10.0.0.1'],['169.254.169.254'],['8.8.8.8','::1']]:
            answer=[(2,1,6,'',(a,443)) for a in addresses]
            with patch('socket.getaddrinfo',return_value=answer):
                with self.assertRaises(InputError):public_addresses('site.example',443)
    def test_public_dns_allowed(self):
        with patch('socket.getaddrinfo',return_value=[(2,1,6,'',('8.8.8.8',443))]):
            self.assertEqual(public_addresses('site.example',443),['8.8.8.8'])
    def test_cross_origin_redirect_rejected_before_fetch(self):
        with self.assertRaises(InputError):PublicFetcher()('https://evil.example/',('https','safe.example'))
    def test_page_count_and_partial_failure(self):
        calls=[]
        def fetch(url,allowed):
            calls.append(url)
            if url.endswith('/about'):raise InputError('test unavailable')
            return url, '<p>This company builds practical inventory tools for local businesses.</p>'+''.join(f'<a href="/{x}">{x}</a>' for x in ['about','products','careers','team','privacy'])
        r=Engine(self.store,fetch).run('Test','https://company.example/')
        self.assertLessEqual(len(calls),4)
        self.assertEqual(len(r['warnings']),1)
        self.assertGreater(len(r['evidence']),0)
    def test_no_evidence_is_error(self):
        with self.assertRaises(InputError):Engine(self.store,lambda *a:('https://company.example/','<p>Hi</p>')).run('Test','https://company.example/')
    def test_demo_cache_cannot_leak_into_live(self):
        self.engine.run('Studio','',demo=True)
        def reject(*a):raise InputError('live fetch attempted')
        with self.assertRaisesRegex(InputError,'live fetch attempted'):
            Engine(self.store,reject).run('Test','https://demo.example/')
    def test_api_end_to_end_exports(self):
        response=self.client.post('/api/generate',json={'company':'Studio','demo':True})
        self.assertEqual(response.status_code,200)
        r=response.json()
        self.assertEqual(self.client.get('/api/runs').json()[0]['id'],r['id'])
        self.assertEqual(self.client.get('/api/runs/'+r['id']).json()['markdown'],r['markdown'])
        self.assertEqual(self.client.get('/api/runs/'+r['id']+'/export?format=json').json()['pages'],r['pages'])
        self.assertIn('attachment',self.client.get('/api/runs/'+r['id']+'/export').headers['content-disposition'])
    def test_missing_run_and_invalid_format(self):
        self.assertEqual(self.client.get('/api/runs/missing').status_code,404)
        r=self.client.post('/api/generate',json={'demo':True}).json()
        self.assertEqual(self.client.get('/api/runs/'+r['id']+'/export?format=xml').status_code,400)
    def test_api_invalid_live_url(self):
        self.assertEqual(self.client.post('/api/generate',json={'demo':False,'url':'file:///etc/passwd'}).status_code,400)
    def test_input_validation(self):
        self.assertEqual(self.client.post('/api/generate',json={'company':''}).status_code,422)
        self.assertEqual(self.client.post('/api/generate',json={'company':'  '}).status_code,400)
    def test_ui_and_health(self):
        self.assertIn('Company brochures',self.client.get('/').text)
        self.assertEqual(self.client.get('/api/health').json()['status'],'ok')
    def test_unconfigured_ai_is_explicit(self):
        with patch.dict('os.environ',{'OPENAI_API_KEY':'','OPENAI_MODEL':''}):
            self.assertEqual(self.client.post('/api/generate',json={'demo':True,'ai':True}).status_code,400)
    def test_provider_response_contract(self):
        provider=MagicMock()
        provider.post.return_value.json.return_value={'choices':[{'message':{'content':json.dumps({'evidence_ids':['E1']})}}]}
        with patch.dict('os.environ',{'OPENAI_API_KEY':'fake-test-key','OPENAI_MODEL':'test-model'}),patch('httpx.Client') as cls:
            cls.return_value.__enter__.return_value=provider
            self.assertEqual(select_evidence('Test',[{'id':'E1'}]),['E1'])
    def test_provider_errors_hide_response(self):
        import httpx
        with patch.dict('os.environ',{'OPENAI_API_KEY':'fake-test-key','OPENAI_MODEL':'test-model'}),patch('httpx.Client') as cls:
            cls.return_value.__enter__.return_value.post.side_effect=httpx.ConnectError('private details')
            with self.assertRaisesRegex(InputError,'provider failed'):select_evidence('Test',[])

class TestFetcherTransport(unittest.TestCase):
    def response(self,status=200,headers=None,body=b'<p>A public company provides useful software.</p>'):
        r=MagicMock();r.status=status
        values={'Content-Type':'text/html',**(headers or {})}
        r.getheader.side_effect=lambda key,default=None:values.get(key,default)
        r.read.return_value=body
        return r
    def test_transport_pins_validated_peer(self):
        with patch('brochure.core.public_addresses',return_value=['8.8.8.8']),patch('brochure.core.socket.create_connection') as dial,patch('brochure.core.http.client.HTTPConnection') as cls:
            conn=cls.return_value;conn.getresponse.return_value=self.response()
            # Exercise our connect closure rather than replacing the pinning behavior.
            conn.request.side_effect=lambda *a,**k:conn.connect()
            final,text=PublicFetcher()('http://company.example/')
            dial.assert_called_once_with(('8.8.8.8',80),timeout=8)
            self.assertEqual(final,'http://company.example/')
            conn.close.assert_called_once()
    def test_tls_keeps_hostname_verification(self):
        with patch('brochure.core.public_addresses',return_value=['8.8.8.8']),patch('brochure.core.socket.create_connection') as dial,patch('brochure.core.ssl.create_default_context') as tls,patch('brochure.core.http.client.HTTPConnection') as cls:
            conn=cls.return_value;conn.getresponse.return_value=self.response()
            conn.request.side_effect=lambda *a,**k:conn.connect()
            PublicFetcher()('https://company.example/')
            tls.return_value.wrap_socket.assert_called_once_with(dial.return_value,server_hostname='company.example')
    def test_redirect_target_checked_before_second_connection(self):
        with patch('brochure.core.public_addresses',return_value=['8.8.8.8']) as dns,patch('brochure.core.http.client.HTTPConnection') as cls:
            cls.return_value.getresponse.return_value=self.response(302,{'Location':'https://elsewhere.example/'})
            with self.assertRaisesRegex(InputError,'Cross-origin'):
                PublicFetcher()('https://company.example/',('https','company.example'))
            self.assertEqual(dns.call_count,1)
    def test_large_or_non_html_body_rejected(self):
        for r in [self.response(body=b'x'*600001),self.response(headers={'Content-Type':'application/pdf'})]:
            with patch('brochure.core.public_addresses',return_value=['8.8.8.8']),patch('brochure.core.http.client.HTTPConnection') as cls:
                cls.return_value.getresponse.return_value=r
                with self.assertRaises(InputError):PublicFetcher()('https://company.example/')
    def test_redirect_limit(self):
        with patch('brochure.core.public_addresses',return_value=['8.8.8.8']),patch('brochure.core.http.client.HTTPConnection') as cls:
            cls.return_value.getresponse.return_value=self.response(302,{'Location':'/loop'})
            with self.assertRaisesRegex(InputError,'too many'):PublicFetcher()('https://company.example/')
            self.assertEqual(cls.call_count,4)
