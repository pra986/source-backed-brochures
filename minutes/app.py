import os
import threading
from pathlib import Path
from typing import Annotated
from fastapi import FastAPI,Request,Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse,JSONResponse,Response
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .models import Analyze,Review,AddItem,Delete
from .extract import RuleError,DEMO,parse_transcript,select_offline,build_items
from .storage import Store
from .providers import select_ai,transcribe,MAX_AUDIO
from .exports import export

def create_app(directory=None,selector=None,transcriber=None):
    app=FastAPI(title='Meeting Minutes Studio',version='0.1.0');store=Store(directory or os.getenv('MINUTES_DATA_DIR','.data'));app.state.store=store
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=os.getenv('TRUSTED_HOSTS','127.0.0.1,localhost,testserver').split(','))
    gate=threading.BoundedSemaphore(2)
    @app.middleware('http')
    async def boundaries(request,call_next):
        if request.method in {'POST','PUT','PATCH','DELETE'}:
            if request.headers.get('origin') and request.headers['origin']!=f'{request.url.scheme}://{request.headers.get("host")}':return JSONResponse(status_code=403,content={'detail':'Cross-origin writes are not allowed.'})
            length=request.headers.get('content-length','0')
            maximum=MAX_AUDIO if request.url.path=='/api/transcribe' else 500000
            if not length.isdigit() or int(length)>maximum:return JSONResponse(status_code=413,content={'detail':'Request exceeds the configured size limit.'})
            if request.url.path!='/api/transcribe' and request.headers.get('content-type','').split(';')[0]!='application/json':return JSONResponse(status_code=415,content={'detail':'Send application/json.'})
        response=await call_next(request);response.headers['Cache-Control']='no-store';response.headers['X-Content-Type-Options']='nosniff';return response
    @app.exception_handler(RuleError)
    async def rule(request,exc):return JSONResponse(status_code=exc.status,content={'detail':exc.detail})
    @app.exception_handler(RequestValidationError)
    async def bad(request,exc):return JSONResponse(status_code=422,content={'detail':'Invalid request fields. Check lengths, revision, source IDs and required values.'})
    @app.get('/',response_class=HTMLResponse)
    def index():return (Path(__file__).parent/'static/index.html').read_text()
    @app.get('/api/health')
    def health():return {'status':'ok','ai_configured':bool(os.getenv('OPENAI_API_KEY') and os.getenv('OPENAI_MODEL')),'audio_configured':bool(os.getenv('OPENAI_API_KEY') and os.getenv('OPENAI_TRANSCRIBE_MODEL'))}
    @app.get('/api/demo')
    def demo():return {'title':'Showroom release planning - fictional demo','transcript':DEMO}
    @app.post('/api/analyze')
    def analyze(body:Analyze):
        if not gate.acquire(blocking=False):raise RuleError('Two provider/analysis requests are already running. Try again shortly.',429)
        try:
            segments=parse_transcript(body.transcript);selection=(selector or select_ai)(body.title,segments) if body.mode=='ai' else select_offline(segments)
            return store.create(body.title,body.transcript,segments,build_items(segments,selection,body.mode),body.mode)
        finally:gate.release()
    @app.post('/api/transcribe')
    async def audio(request:Request,filename:Annotated[str,Query(min_length=1,max_length=150)]):
        chunks=[];size=0
        async for chunk in request.stream():
            size+=len(chunk)
            if size>MAX_AUDIO:raise RuleError('Audio must be no larger than 20 MiB.',413)
            chunks.append(chunk)
        data=b''.join(chunks);content_type=request.headers.get('content-type','').split(';')[0]
        if not gate.acquire(blocking=False):raise RuleError('Two provider/analysis requests are already running. Try again shortly.',429)
        try:
            from starlette.concurrency import run_in_threadpool
            return await run_in_threadpool(transcriber or transcribe,data,filename,content_type)
        finally:gate.release()
    @app.get('/api/meetings')
    def recent():return {'meetings':store.recent()}
    @app.get('/api/meetings/{identifier}')
    def meeting(identifier:str):return store.get(identifier)
    @app.put('/api/meetings/{identifier}/review')
    def review(identifier:str,body:Review):return store.review(identifier,body)
    @app.post('/api/meetings/{identifier}/items')
    def add(identifier:str,body:AddItem):return store.add(identifier,body)
    @app.get('/api/meetings/{identifier}/revisions')
    def revisions(identifier:str):return {'revisions':store.revisions(identifier)}
    @app.delete('/api/meetings/{identifier}')
    def delete(identifier:str,body:Delete):return store.delete(identifier,body.revision)
    @app.get('/api/meetings/{identifier}/export')
    def download(identifier:str,format:str='markdown'):
        data,mime,extension=export(store.get(identifier),format)
        return Response(data,media_type=mime,headers={'Content-Disposition':f'attachment; filename="meeting-{identifier}.{extension}"'})
    return app
app=create_app()
