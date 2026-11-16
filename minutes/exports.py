import csv
import html
import io
import json
import re
from .extract import RuleError

def md(value):
    return re.sub(r'([\\`*_{}\[\]()#+!|>])',r'\\\1',html.escape(str(value),quote=False))

def csv_safe(value):
    text='' if value is None else str(value)
    return "'"+text if text.lstrip().startswith(('=','+','-','@')) or text.startswith(('\t','\r','\n')) else text

def export(record,format):
    if format not in {'markdown','csv','json'}:raise RuleError('Choose markdown, csv or json.')
    if not record['reviewed']:raise RuleError('Review and approve the minutes before exporting.',409)
    sources={s['id']:s for s in record['segments']}
    included=[i for i in record['items'] if i['included']]
    if format=='json':return json.dumps(record,indent=2,ensure_ascii=False),'application/json','json'
    if format=='csv':
        stream=io.StringIO(newline='');writer=csv.writer(stream);writer.writerow(['item_id','task','owner','due_text','source_id','timestamp','source_quote','user_edited'])
        for i in included:
            if i['kind']=='action':writer.writerow([csv_safe(x) for x in [i['id'],i['text'],i['owner'] or 'Not stated',i['due_text'] or 'Not stated',i['source_id'],sources[i['source_id']]['timestamp'] or 'Not provided',i['quote'],i['edited']]])
        return stream.getvalue(),'text/csv','csv'
    lines=['# '+md(record['title']),'','Status: reviewed by the local user. Review is not independent factual verification.','Source SHA-256: '+record['source_sha256'],'Revision: '+str(record['revision']),'']
    for kind,title in [('summary','Discussion excerpts'),('decision','Decisions'),('action','Action items')]:
        lines+=['## '+title,'']
        items=[i for i in included if i['kind']==kind]
        if not items:lines+=['No included items.','']
        for i in items:
            note=' (user edited)' if i['edited'] else ''
            lines+=['- '+md(i['text'])+f" [{i['source_id']}](#{i['source_id'].lower()})"+note]
            if kind=='action':lines+=['  - Owner: '+md(i['owner'] or 'Not stated')+'; due text: '+md(i['due_text'] or 'Not stated')]
            lines+=['']
    lines+=['## Source transcript','']
    for s in record['segments']:
        lines+=['### '+s['id'],'',md((('['+s['timestamp']+'] ') if s['timestamp'] else '')+((s['speaker']+': ') if s['speaker'] else '')+s['text']),'']
    return '\n'.join(lines),'text/markdown','md'
