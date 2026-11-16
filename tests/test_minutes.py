import csv
import hashlib
import io
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch,MagicMock
from fastapi.testclient import TestClient
from minutes.app import create_app
from minutes.extract import *
from minutes.models import Review,Edit,AddItem
from minutes.exports import export,csv_safe
from minutes.providers import transcribe,select_ai,MAX_AUDIO
from minutes.storage import Store

class ExtractionTests(unittest.TestCase):
    def test_demo_counts(self):
        s=parse_transcript(DEMO); items=build_items(s,select_offline(s),'offline')
        self.assertEqual([sum(i['kind']==k for i in items) for k in ['summary','decision','action']],[4,2,3])
    def test_timestamps(self):
        self.assertEqual(parse_timestamp('01:02:03'),3723)
        self.assertEqual(parse_timestamp('61:00'),3660)
    def test_bad_timestamps(self):
        for text in ['[00:60] bad','[01:60:00] bad','[foo] bad','[00:03 missing','[00:03] a\n[00:02] b']:
            with self.subTest(text=text),self.assertRaises(RuleError):parse_transcript(text)
    def test_plain_source(self):
        s=parse_transcript('I will write the notes.')[0]
        self.assertIsNone(s['speaker']);self.assertIsNone(s['timestamp']);self.assertEqual(commitment(s),(True,None,None))
    def test_literal_due(self):
        s=parse_transcript('Maya: I will review by Friday.')[0]
        self.assertEqual(commitment(s),(True,'Maya','Friday'))
    def test_named_owner(self):
        self.assertEqual(commitment(parse_transcript('Ravi will write tests by tomorrow.')[0]),(True,'Ravi','tomorrow'))
    def test_suggestions_not_actions(self):
        for text in ['We should consider tests.','We will test.','Maya said I will test.','Maybe I will test.','They will test.']:
            with self.subTest(text=text):self.assertFalse(commitment(parse_transcript(text)[0])[0])
    def test_reserved_decision_not_speaker(self):
        s=parse_transcript('Decision: use synthetic data.')[0]
        self.assertIsNone(s['speaker']);self.assertTrue(is_decision(s))
    def test_limits(self):
        for text in ['', 'x'*2001,'\n'.join(['hi']*301),'[00:01]']:
            with self.subTest(length=len(text)),self.assertRaises(RuleError):parse_transcript(text)
    def test_invalid_selections(self):
        s=parse_transcript('Hello')
        for selection in [Selection(summary=['S999']),Selection(summary=['S001','S001']),Selection(action=['S001']),Selection(decision=['S001']),Selection(),{}]:
            with self.subTest(selection=selection),self.assertRaises(RuleError):build_items(s,selection,'ai')
    def test_exact_source_quotes(self):
        s=parse_transcript(DEMO)
        for i in build_items(s,select_offline(s),'ai'):
            self.assertEqual(i['quote'],s[int(i['source_id'][1:])-1]['text']);self.assertEqual(i['provenance'],'ai-selected')

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name)
        s=parse_transcript(DEMO);self.r=self.store.create('Demo',DEMO,s,build_items(s,select_offline(s),'offline'),'offline');self.id=self.r['id']
    def tearDown(self):self.tmp.cleanup()
    def approve(self):return self.store.review(self.id,Review(revision=1,edits=[],reviewed=True))
    def test_persistence(self):self.assertEqual(Store(self.tmp.name).get(self.id),self.r)
    def test_hash(self):self.assertEqual(self.r['source_sha256'],hashlib.sha256(DEMO.encode()).hexdigest())
    def test_export_gate(self):
        for fmt in ['json','csv','markdown']:
            with self.subTest(fmt=fmt),self.assertRaises(RuleError) as e:export(self.r,fmt)
            self.assertEqual(e.exception.status,409)
    def test_approval_and_history(self):
        r=self.approve();self.assertTrue(r['reviewed']);self.assertEqual(r['revision'],2);self.assertEqual(len(self.store.revisions(self.id)),2)
    def test_edit_preserves_source(self):
        r=self.store.review(self.id,Review(revision=1,edits=[Edit(id='I001',text='Edited')],reviewed=True))
        self.assertEqual(r['transcript'],DEMO);self.assertEqual(r['items'][0]['quote'],self.r['items'][0]['quote']);self.assertTrue(r['items'][0]['edited'])
    def test_stale_review(self):
        self.approve()
        with self.assertRaises(RuleError) as e:self.approve()
        self.assertEqual(e.exception.status,409)
    def test_concurrent_reviews(self):
        def save(_):
            try:self.approve();return 200
            except RuleError as e:return e.status
        with ThreadPoolExecutor(max_workers=2) as pool:self.assertEqual(sorted(pool.map(save,range(2))),[200,409])
    def test_bad_edit_ids(self):
        for edits in [[Edit(id='missing',text='x')],[Edit(id='I001',text='x')]*2]:
            with self.subTest(edits=edits),self.assertRaises(RuleError):self.store.review(self.id,Review(revision=1,edits=edits))
        self.assertEqual(self.store.get(self.id)['revision'],1)
    def test_nonaction_metadata_rejected(self):
        with self.assertRaises(RuleError):self.store.review(self.id,Review(revision=1,edits=[Edit(id='I001',text='x',owner='A')]))
    def test_no_included_rejected(self):
        with self.assertRaises(RuleError):self.store.review(self.id,Review(revision=1,edits=[Edit(id=i['id'],text=i['text'],included=False) for i in self.r['items']],reviewed=True))
    def test_manual_add_invalidates_approval(self):
        self.approve();r=self.store.add(self.id,AddItem(revision=2,kind='action',text='A reviewer-authored task',source_id='S002'))
        self.assertFalse(r['reviewed']);self.assertEqual(r['items'][-1]['provenance'],'user-added');self.assertIsNone(r['items'][-1]['owner'])
    def test_manual_bad_source(self):
        with self.assertRaises(RuleError):self.store.add(self.id,AddItem(revision=1,kind='action',text='x',source_id='S999'))
    def test_stale_delete(self):
        self.approve()
        with self.assertRaises(RuleError):self.store.delete(self.id,1)
        self.assertEqual(self.store.get(self.id)['revision'],2)
    def test_delete_cascade(self):
        self.store.delete(self.id,1)
        with self.store.db() as c:self.assertEqual(c.execute('SELECT count(*) FROM history').fetchone()[0],0)
        self.assertEqual(self.store.recent(),[])
    def test_exports(self):
        r=self.approve();md,_,_=export(r,'markdown');data,_,_=export(r,'json');csvtext,_,_=export(r,'csv')
        self.assertIn('[S004](#s004)',md);self.assertEqual(json.loads(data)['source_sha256'],r['source_sha256'])
        rows=list(csv.DictReader(io.StringIO(csvtext)));self.assertEqual(len(rows),3);self.assertEqual(rows[-1]['due_text'],'Not stated')
    def test_excluded_actions(self):
        edits=[Edit(id=i['id'],text=i['text'],included=False) for i in self.r['items'] if i['kind']=='action']
        r=self.store.review(self.id,Review(revision=1,edits=edits,reviewed=True));self.assertEqual(len(list(csv.reader(io.StringIO(export(r,'csv')[0])))),1)
    def test_export_escape(self):
        r=self.approve();r['title']='<script>alert(1)</script>';self.assertNotIn('<script>',export(r,'markdown')[0])
    def test_csv_formula(self):
        for text in ['=1+1',' +SUM(A1)','-1','@x','\tbad']:
            self.assertTrue(csv_safe(text).startswith("'"))

class ApiTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.client=TestClient(create_app(self.tmp.name))
    def tearDown(self):self.client.close();self.tmp.cleanup()
    def create(self):return self.client.post('/api/analyze',json={'title':'Demo','transcript':DEMO}).json()
    def test_ui_and_health(self):
        self.assertIn('Meeting Minutes Studio',self.client.get('/').text);self.assertEqual(self.client.get('/api/health').json()['status'],'ok')
    def test_full_flow(self):
        r=self.create();base='/api/meetings/'+r['id'];self.assertEqual(self.client.get(base+'/export').status_code,409)
        r=self.client.put(base+'/review',json={'revision':1,'edits':[],'reviewed':True}).json()
        self.assertTrue(r['reviewed']);self.assertEqual(self.client.get(base+'/export?format=csv').status_code,200)
        self.assertEqual(self.client.request('DELETE',base,json={'revision':2}).status_code,200);self.assertEqual(self.client.get(base).status_code,404)
    def test_origin(self):self.assertEqual(self.client.post('/api/analyze',json={},headers={'Origin':'https://evil.example'}).status_code,403)
    def test_json_required(self):self.assertEqual(self.client.post('/api/analyze',content='x').status_code,415)
    def test_host(self):self.assertEqual(self.client.get('/',headers={'Host':'evil.example'}).status_code,400)
    def test_validation(self):
        for body in [{'title':'','transcript':DEMO},{'title':'x','transcript':' '},{'title':'x','transcript':DEMO,'mode':'unknown'}]:
            self.assertEqual(self.client.post('/api/analyze',json=body).status_code,422)
    def test_missing(self):self.assertEqual(self.client.get('/api/meetings/missing').status_code,404)
    def test_bad_ai_selection(self):
        with TestClient(create_app(self.tmp.name,selector=lambda *_:Selection(action=['S001']))) as c:
            self.assertEqual(c.post('/api/analyze',json={'title':'x','transcript':DEMO,'mode':'ai'}).status_code,502)
    def test_mock_audio_api(self):
        with TestClient(create_app(self.tmp.name,transcriber=lambda *args:{'transcript':'Hello','notice':'Mock'})) as c:
            self.assertEqual(c.post('/api/transcribe?filename=test.wav',content=b'wav',headers={'Content-Type':'audio/wav'}).json()['transcript'],'Hello')
        self.assertEqual(self.client.get('/api/meetings').json()['meetings'],[])

class ProviderTests(unittest.TestCase):
    def test_missing_config(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaises(RuleError) as e:select_ai('x',[])
            self.assertEqual(e.exception.status,503)
    def test_audio_validation(self):
        for data,name,mime,status in [(b'','x.wav','audio/wav',400),(b'x','x.exe','audio/wav',400),(b'x','x.wav','text/plain',415),(b'x'*(MAX_AUDIO+1),'x.wav','audio/wav',413)]:
            with self.subTest(name=name,status=status),self.assertRaises(RuleError) as e:transcribe(data,name,mime)
            self.assertEqual(e.exception.status,status)
    def test_audio_contract(self):
        mock=MagicMock();mock.__enter__.return_value=mock;mock.post.return_value.json.return_value={'text':'  I will test.  '}
        with patch.dict(os.environ,{'OPENAI_API_KEY':'fake','OPENAI_TRANSCRIBE_MODEL':'fake'}),patch('minutes.providers.httpx.Client',return_value=mock):
            result=transcribe(b'fake','../../record.wav','audio/wav')
        self.assertEqual(result['transcript'],'I will test.');self.assertEqual(mock.post.call_args.kwargs['files']['file'][0],'record.wav')
    def test_invalid_provider_response(self):
        mock=MagicMock();mock.__enter__.return_value=mock;mock.post.return_value.json.return_value={'text':None}
        with patch.dict(os.environ,{'OPENAI_API_KEY':'fake','OPENAI_TRANSCRIBE_MODEL':'fake'}),patch('minutes.providers.httpx.Client',return_value=mock):
            with self.assertRaises(RuleError) as e:transcribe(b'fake','x.wav','audio/wav')
        self.assertEqual(e.exception.status,502)

if __name__=='__main__':unittest.main()
