"""Local demonstration API. All booking writes are authenticated and confirmed."""
import os
import time
import threading
from collections import defaultdict
from pathlib import Path
from typing import Annotated
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import ValidationError
from .db import Store, RuleError
from .models import Register, Login, Preview, Confirm, Chat, Search, Compare, Fuel, Transmission, Body
from .assistant import answer

def create_app(directory=None,router=None):
    app=FastAPI(title='Showroom Copilot',version='0.1.0')
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=os.getenv('TRUSTED_HOSTS','127.0.0.1,localhost,testserver').split(','))
    store=Store(directory or os.getenv('SHOWROOM_DATA_DIR','.data'))
    app.state.store=store
    login_attempts=defaultdict(list)
    lock=threading.Lock()
    chat_gate=threading.BoundedSemaphore(2)
    @app.middleware('http')
    async def write_boundary(request,call_next):
        if request.method in {'POST','PUT','PATCH','DELETE'}:
            if request.headers.get('origin') and request.headers['origin']!=f'{request.url.scheme}://{request.headers.get("host")}':
                return JSONResponse(status_code=403,content={'detail':'Cross-origin writes are not allowed.'})
            if request.headers.get('content-type','').split(';')[0]!='application/json':
                return JSONResponse(status_code=415,content={'detail':'Send an application/json request.'})
            length=request.headers.get('content-length','0')
            if not length.isdigit() or int(length)>16000:
                return JSONResponse(status_code=413,content={'detail':'Request body is too large.'})
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='same-origin'
        response.headers['Cache-Control']='no-store'
        return response
    @app.exception_handler(RuleError)
    async def rule_error(request,exc):return JSONResponse(status_code=exc.status,content={'detail':exc.detail})
    @app.exception_handler(RequestValidationError)
    async def request_validation_error(request,exc):
        return JSONResponse(status_code=422,content={'detail':'Invalid request fields. Check required values, supported filters and password length (10-128 for registration).'})
    @app.exception_handler(ValidationError)
    async def validation_error(request,exc):return JSONResponse(status_code=422,content={'detail':'Invalid input parameters.'})
    def current(request:Request):
        u=store.user(request.cookies.get('showroom_session'))
        if not u:raise HTTPException(401,'Sign in before creating a booking request.')
        return u
    def set_session(response,user_id):
        response.set_cookie('showroom_session',store.session(user_id),max_age=86400,httponly=True,samesite='strict',secure=os.getenv('COOKIE_SECURE')=='1')
    @app.get('/',response_class=HTMLResponse)
    def index():return (Path(__file__).parent/'static/index.html').read_text()
    @app.get('/api/health')
    def health():return {'status':'ok','synthetic':True,'ai_configured':bool(os.getenv('OPENAI_API_KEY') and os.getenv('OPENAI_MODEL'))}
    @app.post('/api/auth/register')
    def register(body:Register,response:Response):
        u=store.register(body.name,body.email,body.password.get_secret_value());set_session(response,u['id']);return u
    @app.post('/api/auth/login')
    def login(body:Login,request:Request,response:Response):
        key=request.client.host if request.client else 'local'
        with lock:
            now=time.time(); login_attempts[key]=[t for t in login_attempts[key] if t>now-60]
            if len(login_attempts[key])>=8:raise HTTPException(429,'Too many sign-in attempts. Try again in a minute.')
            login_attempts[key].append(now)
        u=store.login(body.email,body.password.get_secret_value());set_session(response,u['id']);return u
    @app.post('/api/auth/logout')
    def logout(request:Request,response:Response):
        store.logout(request.cookies.get('showroom_session'));response.delete_cookie('showroom_session');return {'signed_out':True}
    @app.get('/api/auth/me')
    def me(request:Request):return {'user':store.user(request.cookies.get('showroom_session'))}
    @app.get('/api/cars')
    def cars(max_price:Annotated[int|None,Query(ge=0,le=100_000_000)]=None,min_price:Annotated[int|None,Query(ge=0,le=100_000_000)]=None,brand:Annotated[str|None,Query(max_length=60)]=None,fuel:Fuel|None=None,transmission:Transmission|None=None,body_type:Body|None=None,available_only:bool=True):
        filters=Search(max_price=max_price,min_price=min_price,brand=brand,fuel=fuel,transmission=transmission,body_type=body_type,available_only=available_only)
        return {'cars':store.search(filters),'synthetic':True,'currency':'INR'}
    @app.get('/api/cars/{car_id}')
    def car(car_id:str):return store.car(car_id)
    @app.post('/api/compare')
    def compare(body:Compare):return store.compare(body.ids)
    @app.post('/api/chat')
    def chat(body:Chat):
        if not chat_gate.acquire(blocking=False):raise HTTPException(429,'Two chat requests are already running.')
        try:return answer(store,body.message,body.mode,router)
        finally:chat_gate.release()
    @app.post('/api/booking-previews')
    def preview(body:Preview,user=Depends(current)):return store.preview(user['id'],body.car_id)
    @app.post('/api/bookings/confirm')
    def confirm(body:Confirm,user=Depends(current)):return store.confirm(user['id'],body.preview_id)
    @app.get('/api/bookings')
    def bookings(user=Depends(current)):return {'bookings':store.bookings(user['id'])}
    @app.post('/api/bookings/{booking_id}/cancel')
    def cancel(booking_id:str,user=Depends(current)):return store.cancel(user['id'],booking_id)
    return app

app=create_app()
