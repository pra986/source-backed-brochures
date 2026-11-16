import json,tempfile,time,unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from fastapi.testclient import TestClient
from showroom.app import create_app
from showroom.db import Store,RuleError,verify_password
from showroom.models import Search,Plan
from showroom.assistant import answer,offline_plan,provider_plan
PASSWORD='Local-test-pass-123'
class Base(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.app=create_app(self.tmp.name);self.store=self.app.state.store;self.client=TestClient(self.app)
 def tearDown(self):self.client.close();self.tmp.cleanup()
 def register(self,email='pranil@example.test'):
  r=self.client.post('/api/auth/register',json={'name':'Demo Customer','email':email,'password':PASSWORD});self.assertEqual(r.status_code,200);return r.json()
 def user(self,email='pranil@example.test'):return self.store.register('Demo',email,PASSWORD)['id']
class InventoryTests(Base):
 def test_seed(self):self.assertEqual(len(self.store.search(Search(available_only=False))),12)
 def test_available(self):self.assertEqual(len(self.store.search(Search())),11)
 def test_budget(self):self.assertEqual([c['id'] for c in self.store.search(Search(max_price=800000))],['CAR-001','CAR-002'])
 def test_minimum_and_fuel(self):self.assertTrue(all(c['price_inr']>=1000000 and c['fuel']=='diesel' for c in self.store.search(Search(min_price=1000000,fuel='diesel'))))
 def test_brand(self):self.assertTrue(all(c['brand']=='Aster' for c in self.store.search(Search(brand='aster'))))
 def test_combined(self):self.assertEqual([c['id'] for c in self.store.search(Search(max_price=1200000,transmission='automatic',body_type='suv'))],['CAR-004'])
 def test_empty(self):self.assertEqual(self.store.search(Search(max_price=1)),[])
 def test_sql_like_brand(self):self.assertEqual(self.store.search(Search(brand="' OR 1=1 --")),[])
 def test_missing(self):
  with self.assertRaises(RuleError):self.store.car('CAR-999')
 def test_comparison(self):
  r=self.store.compare(['CAR-001','CAR-002']);self.assertEqual(r['lowest_price_ids'],['CAR-001']);self.assertEqual(r['cars'][1]['price_inr'],790000)
 def test_api_invalid_filters(self):
  for path in ['/api/cars?max_price=-1','/api/cars?fuel=hydrogen','/api/cars?min_price=20&max_price=10']:self.assertEqual(self.client.get(path).status_code,422)
 def test_api_invalid_compare(self):
  for ids in [['CAR-001'],['CAR-001','CAR-001'],['CAR-001']*4]:self.assertEqual(self.client.post('/api/compare',json={'ids':ids}).status_code,422)
class AuthTests(Base):
 def test_password_and_token_hashes(self):
  u=self.register()
  with self.store.connection() as db:
   stored=db.execute('SELECT password_hash FROM users WHERE id=?',(u['id'],)).fetchone()[0];token=db.execute('SELECT token_hash FROM sessions').fetchone()[0]
  self.assertNotEqual(stored,PASSWORD);self.assertTrue(verify_password(PASSWORD,stored));self.assertNotEqual(token,self.client.cookies['showroom_session']);self.assertEqual(self.client.get('/api/auth/me').json()['user']['id'],u['id'])
 def test_cookie_flags(self):
  r=self.client.post('/api/auth/register',json={'name':'Demo','email':'a@example.test','password':PASSWORD});self.assertIn('httponly',r.headers['set-cookie'].lower());self.assertIn('samesite=strict',r.headers['set-cookie'].lower())
 def test_logout(self):
  self.register();token=self.client.cookies['showroom_session'];self.client.post('/api/auth/logout',json={});self.assertIsNone(self.store.user(token))
 def test_signin(self):
  u=self.register();self.client.post('/api/auth/logout',json={});r=self.client.post('/api/auth/login',json={'email':'PRANIL@example.test','password':PASSWORD});self.assertEqual(r.status_code,200);self.assertEqual(r.json()['id'],u['id'])
 def test_wrong_credentials(self):
  self.register()
  for email in ['pranil@example.test','missing@example.test']:self.assertEqual(self.client.post('/api/auth/login',json={'email':email,'password':'wrong'}).status_code,401)
 def test_duplicate_email(self):
  self.register();self.assertEqual(self.client.post('/api/auth/register',json={'name':'Other','email':'PRANIL@example.test','password':PASSWORD}).status_code,409)
 def test_validation_does_not_echo_password(self):
  r=self.client.post('/api/auth/register',json={'name':'Demo','email':'invalid','password':'SECRET'});self.assertEqual(r.status_code,422);self.assertNotIn('SECRET',r.text)
 def test_session_expiry(self):
  self.register()
  with self.store.transaction() as db:db.execute('UPDATE sessions SET expires=?',(time.time()-1,))
  self.assertIsNone(self.client.get('/api/auth/me').json()['user'])
 def test_login_limit(self):
  for _ in range(8):self.client.post('/api/auth/login',json={'email':'x@example.test','password':'wrong'})
  self.assertEqual(self.client.post('/api/auth/login',json={'email':'x@example.test','password':'wrong'}).status_code,429)
 def test_origin(self):self.assertEqual(self.client.post('/api/chat',json={'message':'show cars'},headers={'Origin':'https://evil.example'}).status_code,403)
 def test_content_type(self):self.assertEqual(self.client.post('/api/chat',content='message=show+cars').status_code,415)
 def test_host(self):self.assertEqual(self.client.get('/api/cars',headers={'host':'evil.example'}).status_code,400)
class BookingTests(Base):
 def test_auth_required(self):
  for path,body in [('/api/booking-previews',{'car_id':'CAR-001'}),('/api/bookings/confirm',{'preview_id':'x','confirmed':True})]:self.assertEqual(self.client.post(path,json=body).status_code,401)
  self.assertEqual(self.client.get('/api/bookings').status_code,401)
 def test_preview_no_reservation(self):
  p=self.store.preview(self.user(),'CAR-001');self.assertGreater(p['expires'],time.time());self.assertEqual(self.store.car('CAR-001')['stock'],2)
 def test_explicit_confirm(self):
  self.register();p=self.client.post('/api/booking-previews',json={'car_id':'CAR-001'}).json()
  for body in [{'preview_id':p['id']},{'preview_id':p['id'],'confirmed':False}]:self.assertEqual(self.client.post('/api/bookings/confirm',json=body).status_code,422)
  self.assertEqual(self.store.car('CAR-001')['stock'],2)
 def test_confirm_replay(self):
  u=self.user();p=self.store.preview(u,'CAR-001');a=self.store.confirm(u,p['id']);b=self.store.confirm(u,p['id']);self.assertEqual(a['id'],b['id']);self.assertTrue(b['replayed']);self.assertEqual(self.store.car('CAR-001')['stock'],1)
 def test_stale_price(self):
  u=self.user();p=self.store.preview(u,'CAR-001')
  with self.store.transaction() as db:db.execute('UPDATE cars SET price_inr=price_inr+1 WHERE id=?',('CAR-001',))
  with self.assertRaisesRegex(RuleError,'Inventory changed'):self.store.confirm(u,p['id'])
  self.assertEqual(self.store.car('CAR-001')['stock'],2)
 def test_stale_version(self):
  u=self.user();p=self.store.preview(u,'CAR-001')
  with self.store.transaction() as db:db.execute('UPDATE cars SET version=version+1 WHERE id=?',('CAR-001',))
  with self.assertRaisesRegex(RuleError,'Inventory changed'):self.store.confirm(u,p['id'])
 def test_expired_preview(self):
  u=self.user();p=self.store.preview(u,'CAR-001')
  with self.store.transaction() as db:db.execute('UPDATE previews SET expires=?',(time.time()-1,))
  with self.assertRaisesRegex(RuleError,'expired'):self.store.confirm(u,p['id'])
 def test_out_of_stock(self):
  with self.assertRaisesRegex(RuleError,'out of stock'):self.store.preview(self.user(),'CAR-009')
 def test_preview_ownership(self):
  a=self.user();b=self.user('other@example.test');p=self.store.preview(a,'CAR-001')
  with self.assertRaises(RuleError) as e:self.store.confirm(b,p['id'])
  self.assertEqual(e.exception.status,404)
 def test_booking_scope(self):
  a=self.user();b=self.user('other@example.test');r=self.store.confirm(a,self.store.preview(a,'CAR-001')['id']);self.assertEqual(self.store.bookings(b),[])
  with self.assertRaises(RuleError):self.store.cancel(b,r['id'])
 def test_cancel_replay(self):
  u=self.user();p=self.store.preview(u,'CAR-001');b=self.store.confirm(u,p['id']);self.store.cancel(u,b['id']);self.assertTrue(self.store.cancel(u,b['id'])['replayed']);self.assertEqual(self.store.car('CAR-001')['stock'],2);self.assertEqual(self.store.confirm(u,p['id'])['status'],'cancelled');self.assertEqual(self.store.car('CAR-001')['stock'],2)
 def test_last_unit_race(self):
  u=self.user();previews=[self.store.preview(u,'CAR-004')['id'] for _ in range(2)]
  def attempt(p):
   try:return self.store.confirm(u,p)['status']
   except RuleError:return 'rejected'
  with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,previews))
  self.assertEqual(sorted(results),['confirmed','rejected']);self.assertEqual(self.store.car('CAR-004')['stock'],0)
 def test_concurrent_same_preview(self):
  u=self.user();p=self.store.preview(u,'CAR-001')['id']
  with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.store.confirm(u,p),range(2)))
  self.assertEqual(results[0]['id'],results[1]['id']);self.assertEqual(len(self.store.bookings(u)),1)
 def test_persistence(self):
  u=self.user();b=self.store.confirm(u,self.store.preview(u,'CAR-001')['id']);s=Store(self.tmp.name);self.assertEqual(s.bookings(u)[0]['id'],b['id']);self.assertEqual(s.car('CAR-001')['stock'],1)
 def test_full_api_flow(self):
  self.register();p=self.client.post('/api/booking-previews',json={'car_id':'CAR-001'}).json();r=self.client.post('/api/bookings/confirm',json={'preview_id':p['id'],'confirmed':True});self.assertEqual(r.status_code,200);self.assertEqual(len(self.client.get('/api/bookings').json()['bookings']),1);self.assertEqual(self.client.post('/api/bookings/'+r.json()['id']+'/cancel',json={}).json()['status'],'cancelled')
class AssistantTests(Base):
 def test_lakh_budget(self):
  p=offline_plan('Show automatic cars under 12 lakh');self.assertEqual(p.filters.max_price,1200000);self.assertEqual(p.filters.transmission,'automatic')
 def test_range_and_numeric(self):
  self.assertEqual(offline_plan('cars below INR 8,00,000').filters.max_price,800000);p=offline_plan('cars between 8 and 12 lakh');self.assertEqual((p.filters.min_price,p.filters.max_price),(800000,1200000))
 def test_crore(self):self.assertEqual(offline_plan('cars above 1 crore').filters.min_price,10000000)
 def test_fuel_body_brand(self):
  p=offline_plan('Show Sahyadri diesel suv cars');self.assertEqual((p.filters.brand,p.filters.fuel,p.filters.body_type),('sahyadri','diesel','suv'))
 def test_compare_and_details(self):
  r=answer(self.store,'Compare CAR-001 and CAR-002');self.assertEqual(r['trace']['tool'],'compare');self.assertEqual(len(r['cars']),2);self.assertEqual(answer(self.store,'Details CAR-003')['cars'][0]['id'],'CAR-003')
 def test_unknown_facts(self):
  for q in ['What is its mileage?','What is the safety rating?','Can I get a discount?']:self.assertEqual(answer(self.store,q)['trace']['tool'],'help')
 def test_chat_no_booking(self):self.assertEqual(answer(self.store,'Book CAR-001 now')['trace']['tool'],'help');self.assertEqual(self.store.car('CAR-001')['stock'],2)
 def test_ambiguous_and_negation(self):self.assertEqual(offline_plan('not diesel cars').action,'help');self.assertEqual(offline_plan('petrol or diesel cars').action,'help')
 def test_bad_range_or_empty(self):
  for q in ['  ','cars between 12 and 8 lakh']:
   with self.assertRaises(RuleError):offline_plan(q)
 def test_empty_results(self):self.assertIn('No current demo cars',answer(self.store,'cars under 1 lakh')['message'])
 def test_unknown_id(self):
  with self.assertRaises(RuleError):answer(self.store,'details CAR-999')
 def test_ai_plan_same_tools(self):
  r=answer(self.store,'custom wording','ai',router=lambda _:Plan(action='search',filters=Search(max_price=800000)));self.assertEqual(len(r['cars']),2);self.assertTrue(r['trace']['readonly'])
 def test_ai_invalid_ids_and_counts(self):
  for plan in [Plan(action='details',ids=['../x']),Plan(action='compare',ids=['CAR-001']),Plan(action='details',ids=[])]:
   with self.assertRaises(RuleError):answer(self.store,'x','ai',router=lambda _:plan)
 def test_ai_no_key(self):
  with patch.dict('os.environ',{'OPENAI_API_KEY':'','OPENAI_MODEL':''}):self.assertEqual(self.client.post('/api/chat',json={'message':'cars','mode':'ai'}).status_code,503)
 def test_provider_contract_rejects_writes(self):
  for payload,valid in [({'action':'search','filters':{'max_price':1000000},'ids':[]},True),({'action':'book','ids':['CAR-001']},False)]:
   with patch.dict('os.environ',{'OPENAI_API_KEY':'fake-key','OPENAI_MODEL':'test-model'}),patch('httpx.Client') as cls:
    cls.return_value.__enter__.return_value.post.return_value.json.return_value={'choices':[{'message':{'content':json.dumps(payload)}}]}
    if valid:self.assertEqual(provider_plan('test').action,'search')
    else:
     with self.assertRaises(RuleError):provider_plan('test')
 def test_health_and_ui(self):self.assertTrue(self.client.get('/api/health').json()['synthetic']);self.assertIn('Showroom Copilot',self.client.get('/').text)

class BoundaryTests(Base):
 def test_unsupported_budget_syntax_clarifies(self):
  for text in ['show cars under -2 lakh','show cars under 10k','cars between eight and ten lakh']:
   self.assertEqual(offline_plan(text).action,'help')
 def test_api_replay_uses_original_snapshot(self):
  self.register();p=self.client.post('/api/booking-previews',json={'car_id':'CAR-001'}).json();payload={'preview_id':p['id'],'confirmed':True};a=self.client.post('/api/bookings/confirm',json=payload).json();b=self.client.post('/api/bookings/confirm',json=payload).json();self.assertEqual(a['id'],b['id']);self.assertEqual(json.loads(a['car_snapshot'])['price_inr'],a['price_inr'])
 def test_wrong_user_api_cannot_cancel_or_confirm(self):
  self.register();p=self.client.post('/api/booking-previews',json={'car_id':'CAR-001'}).json();booking=self.client.post('/api/bookings/confirm',json={'preview_id':p['id'],'confirmed':True}).json();self.client.post('/api/auth/logout',json={});self.register('other@example.test');self.assertEqual(self.client.get('/api/bookings').json()['bookings'],[]);self.assertEqual(self.client.post('/api/bookings/'+booking['id']+'/cancel',json={}).status_code,404);self.assertEqual(self.client.post('/api/bookings/confirm',json={'preview_id':p['id'],'confirmed':True}).status_code,404)
 def test_cookie_secure_configuration(self):
  with patch.dict('os.environ',{'COOKIE_SECURE':'1'}):
   r=self.client.post('/api/auth/register',json={'name':'Demo','email':'secure@example.test','password':PASSWORD});self.assertIn('secure',r.headers['set-cookie'].lower())
 def test_session_token_not_in_user_response(self):
  r=self.register();self.assertEqual(set(r),{'id','name','email'});self.assertNotIn('password',self.client.get('/api/auth/me').text)
