"""Authoritative inventory and transactional booking rules. Amounts are integer INR."""
from contextlib import contextmanager
import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from pathlib import Path
from .models import Search

class RuleError(Exception):
    def __init__(self, detail, status=400):
        super().__init__(detail); self.detail=detail; self.status=status

# Fictional brands/models, deliberately not real-world specifications or prices.
SEED=[
 ('CAR-001','Aster','City','Comfort',675000,'petrol','manual','hatchback',5,2),
 ('CAR-002','Aster','City','Auto',790000,'petrol','automatic','hatchback',5,2),
 ('CAR-003','Sahyadri','Trail','Base',980000,'petrol','manual','suv',5,2),
 ('CAR-004','Sahyadri','Trail','Auto',1180000,'petrol','automatic','suv',5,1),
 ('CAR-005','Nexaura','Volt','Urban',1350000,'electric','automatic','suv',5,2),
 ('CAR-006','Aster','Line','Tour',1050000,'diesel','manual','sedan',5,1),
 ('CAR-007','Nexaura','Glide','Plus',1580000,'hybrid','automatic','sedan',5,2),
 ('CAR-008','Sahyadri','Summit','Family',1890000,'diesel','automatic','suv',7,1),
 ('CAR-009','Nexaura','Spark','Entry',925000,'electric','automatic','hatchback',4,0),
 ('CAR-010','Aster','Line','Auto',1120000,'petrol','automatic','sedan',5,2),
 ('CAR-011','Sahyadri','Trail','Diesel',1280000,'diesel','manual','suv',5,2),
 ('CAR-012','Nexaura','Glide','Eco',1490000,'hybrid','automatic','sedan',5,1)
]

def digest(token): return hashlib.sha256(token.encode()).hexdigest()
def password_hash(password, salt=None):
    salt=salt or secrets.token_hex(16)
    value=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1,dklen=32).hex()
    return salt+':'+value

def verify_password(password, stored):
    salt,_=stored.split(':')
    return hmac.compare_digest(password_hash(password,salt),stored)

DUMMY_HASH=password_hash('dummy-password', '00'*16)

class Store:
    def __init__(self, directory):
        Path(directory).mkdir(parents=True, exist_ok=True)
        self.path=Path(directory)/'showroom.sqlite3'
        with self.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS cars (
                  id TEXT PRIMARY KEY, brand TEXT, model TEXT, variant TEXT,
                  price_inr INTEGER CHECK(price_inr>=0), fuel TEXT, transmission TEXT,
                  body_type TEXT, seats INTEGER, stock INTEGER CHECK(stock>=0), version INTEGER DEFAULT 1);
                CREATE TABLE IF NOT EXISTS users (
                  id TEXT PRIMARY KEY, name TEXT, email TEXT UNIQUE, password_hash TEXT);
                CREATE TABLE IF NOT EXISTS sessions (
                  token_hash TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id), expires REAL);
                CREATE TABLE IF NOT EXISTS previews (
                  id TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id), car_id TEXT REFERENCES cars(id),
                  price_inr INTEGER, version INTEGER, expires REAL, created REAL);
                CREATE TABLE IF NOT EXISTS bookings (
                  id TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id), car_id TEXT REFERENCES cars(id),
                  preview_id TEXT UNIQUE REFERENCES previews(id), price_inr INTEGER, car_snapshot TEXT,
                  status TEXT CHECK(status IN ('confirmed','cancelled')), created REAL, cancelled REAL);
            ''')
            db.executemany('INSERT OR IGNORE INTO cars(id,brand,model,variant,price_inr,fuel,transmission,body_type,seats,stock) VALUES(?,?,?,?,?,?,?,?,?,?)',SEED)
    @contextmanager
    def connection(self):
        db=sqlite3.connect(self.path,timeout=10,isolation_level=None)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try: yield db
        finally: db.close()
    @contextmanager
    def transaction(self):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback(); raise
    def register(self,name,email,password):
        user={'id':secrets.token_hex(16),'name':name,'email':email.strip().lower()}
        hashed=password_hash(password)
        try:
            with self.transaction() as db:
                db.execute('INSERT INTO users VALUES(?,?,?,?)',(*user.values(),hashed))
        except sqlite3.IntegrityError as exc:
            raise RuleError('An account with that email already exists.',409) from exc
        return user
    def login(self,email,password):
        with self.connection() as db: row=db.execute('SELECT * FROM users WHERE email=?',(email.strip().lower(),)).fetchone()
        # Equal-cost work even if the email is unknown.
        stored=row['password_hash'] if row else DUMMY_HASH
        valid=verify_password(password,stored)
        if not row or not valid: raise RuleError('Email or password is incorrect.',401)
        return {k:row[k] for k in ('id','name','email')}
    def session(self,user_id):
        token=secrets.token_urlsafe(32)
        with self.transaction() as db:
            db.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))
            db.execute('INSERT INTO sessions VALUES(?,?,?)',(digest(token),user_id,time.time()+86400))
        return token
    def user(self,token):
        if not token:return None
        with self.connection() as db:
            r=db.execute('SELECT u.id,u.name,u.email FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>?',(digest(token),time.time())).fetchone()
        return dict(r) if r else None
    def logout(self,token):
        if token:
            with self.transaction() as db: db.execute('DELETE FROM sessions WHERE token_hash=?',(digest(token),))
    def search(self,filters:Search):
        conditions,values=[],[]
        for name,op,value in [('price_inr','<=',filters.max_price),('price_inr','>=',filters.min_price),('brand','=',filters.brand),('fuel','=',filters.fuel),('transmission','=',filters.transmission),('body_type','=',filters.body_type)]:
            if value is not None:
                conditions.append(f'{name} {op} ? COLLATE NOCASE'); values.append(value)
        if filters.available_only: conditions.append('stock>0')
        sql='SELECT * FROM cars'+(' WHERE '+' AND '.join(conditions) if conditions else '')+' ORDER BY price_inr,id'
        with self.connection() as db: return [dict(r) for r in db.execute(sql,values)]
    def car(self,car_id):
        with self.connection() as db: row=db.execute('SELECT * FROM cars WHERE id=?',(car_id,)).fetchone()
        if not row: raise RuleError('Car not found.',404)
        return dict(row)
    def compare(self,ids):
        cars=[self.car(x) for x in ids]
        return {'cars':cars,'lowest_price_ids':[c['id'] for c in cars if c['price_inr']==min(c['price_inr'] for c in cars)],'notice':'Synthetic catalog; no mileage, safety rating or real-world performance is inferred.'}
    def preview(self,user_id,car_id):
        with self.transaction() as db:
            c=db.execute('SELECT * FROM cars WHERE id=?',(car_id,)).fetchone()
            if not c: raise RuleError('Car not found.',404)
            if c['stock']<1: raise RuleError('This demo car is out of stock.',409)
            p={'id':secrets.token_hex(16),'user_id':user_id,'car_id':car_id,'price_inr':c['price_inr'],'version':c['version'],'expires':time.time()+600,'created':time.time()}
            db.execute('INSERT INTO previews VALUES(?,?,?,?,?,?,?)',tuple(p.values()))
        return dict(p,car=dict(c),notice='This is a demo booking request, not a sale, payment or real vehicle reservation. Prices exclude fees. The preview does not hold stock.')
    def confirm(self,user_id,preview_id):
        with self.transaction() as db:
            p=db.execute('SELECT * FROM previews WHERE id=? AND user_id=?',(preview_id,user_id)).fetchone()
            if not p: raise RuleError('Preview not found.',404)
            prior=db.execute('SELECT * FROM bookings WHERE preview_id=?',(preview_id,)).fetchone()
            if prior:return dict(prior,replayed=True)
            if p['expires']<time.time(): raise RuleError('Preview expired. Request a new preview.',409)
            c=db.execute('SELECT * FROM cars WHERE id=?',(p['car_id'],)).fetchone()
            if not c or c['stock']<1: raise RuleError('This demo car is no longer available.',409)
            if c['version']!=p['version'] or c['price_inr']!=p['price_inr']:
                raise RuleError('Inventory changed. Review and confirm a new preview.',409)
            db.execute('UPDATE cars SET stock=stock-1,version=version+1 WHERE id=?',(c['id'],))
            booking={'id':secrets.token_hex(16),'user_id':user_id,'car_id':c['id'],'preview_id':preview_id,'price_inr':p['price_inr'],'car_snapshot':json.dumps(dict(c)),'status':'confirmed','created':time.time(),'cancelled':None}
            db.execute('INSERT INTO bookings VALUES(?,?,?,?,?,?,?,?,?)',tuple(booking.values()))
            return dict(booking,replayed=False)
    def bookings(self,user_id):
        with self.connection() as db: return [dict(r) for r in db.execute('SELECT * FROM bookings WHERE user_id=? ORDER BY created DESC',(user_id,))]
    def cancel(self,user_id,booking_id):
        with self.transaction() as db:
            r=db.execute('SELECT * FROM bookings WHERE id=? AND user_id=?',(booking_id,user_id)).fetchone()
            if not r: raise RuleError('Booking not found.',404)
            if r['status']=='cancelled':return dict(r,replayed=True)
            now=time.time()
            db.execute("UPDATE bookings SET status='cancelled',cancelled=? WHERE id=?",(now,booking_id))
            db.execute('UPDATE cars SET stock=stock+1,version=version+1 WHERE id=?',(r['car_id'],))
            return dict(r,status='cancelled',cancelled=now,replayed=False)
