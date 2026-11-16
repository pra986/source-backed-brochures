"""Immutable source segments and conservative extractive selection."""
import re
from .models import Selection

class RuleError(Exception):
    def __init__(self,message,status=400):super().__init__(message);self.status=status;self.detail=message

DEMO='''[00:00] Maya: This fictional meeting reviews the showroom demo and its next release.
[00:12] Ravi: The inventory search now returns database prices and stock correctly.
[00:25] Maya: We agreed to keep the next release focused on booking-request reliability.
[00:42] Ravi: I will add a duplicate-confirmation test by Friday.
[00:58] Maya: I will review the setup guide by 2026-11-20.
[01:14] Ravi: We should consider a MySQL adapter in a later release.
[01:32] Maya: Decision: no real customer data will be used in the demo.
[01:48] Ravi: I will record the browser walkthrough.
[02:03] Maya: The meeting is complete; all names and project details here are synthetic.'''

def parse_timestamp(value):
    parts=value.split(':')
    if len(parts) not in {2,3} or any(not p.isdigit() for p in parts):raise RuleError('Use timestamps like [00:42] or [01:02:03].')
    nums=list(map(int,parts))
    if nums[-1]>=60 or (len(nums)==3 and nums[-2]>=60):raise RuleError('Timestamp seconds and hour-format minutes must be below 60.')
    return sum(n*60**i for i,n in enumerate(reversed(nums)))

def parse_transcript(text):
    segments=[];last=-1
    for raw in text.splitlines():
        raw=raw.strip()
        if not raw:continue
        if len(raw)>2000:raise RuleError('A transcript line exceeds 2000 characters. Split it into shorter source segments.')
        timestamp=None;seconds=None
        if raw.startswith('['):
            m=re.match(r'^\[([^\]]+)\]\s*(.*)$',raw)
            if not m:raise RuleError('Unclosed timestamp bracket.')
            timestamp=m[1];seconds=parse_timestamp(timestamp);raw=m[2].strip()
            if seconds<last:raise RuleError('Transcript timestamps must be nondecreasing.')
            last=seconds
        speaker=None
        m=re.match(r"^([^:]{1,60}):\s*(.+)$",raw)
        if m and m[1].strip().lower() not in {'decision','action','note','summary'} and not any(c.isdigit() for c in m[1]):
            speaker=m[1].strip();raw=m[2].strip()
        if not raw:raise RuleError('Each transcript segment needs spoken text.')
        segments.append({'id':f'S{len(segments)+1:03d}','timestamp':timestamp,'seconds':seconds,'speaker':speaker,'text':raw})
        if len(segments)>300:raise RuleError('Use at most 300 nonempty transcript lines per meeting.')
    if not segments:raise RuleError('Provide at least one nonempty transcript line.')
    return segments

def is_decision(segment):
    return bool(re.search(r'\b(we agreed|we decided|decided to|decision:)\b',segment['text'],re.I) or segment['text'].lower().startswith('decision:'))

def commitment(segment):
    text=segment['text']
    first=re.match(r"^(?:I will|I'll)\s+",text,re.I)
    named=re.match(r"^([A-Z][\w'-]*(?:\s+[A-Z][\w'-]*)?) will\s+",text)
    owner=None
    if first:owner=segment['speaker']
    elif named and named[1].lower() not in {'we','they','he','she','it','the team','you','maybe','perhaps','maybe i','perhaps i'}:owner=named[1]
    else:return False,None,None
    due=re.search(r'\bby\s+((?:next\s+)?(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)|today|tomorrow|\d{4}-\d{2}-\d{2})\b',text,re.I)
    return True,owner,due[1] if due else None

def select_offline(segments):
    return Selection(summary=[s['id'] for s in segments[:4]],decision=[s['id'] for s in segments if is_decision(s)][:20],action=[s['id'] for s in segments if commitment(s)[0]][:40])

def build_items(segments,selection,mode):
    known={s['id']:s for s in segments};items=[]
    if not isinstance(selection,Selection):raise RuleError('The selector returned an invalid result.',502)
    for kind in ['summary','decision','action']:
        ids=getattr(selection,kind)
        if len(ids)!=len(set(ids)):raise RuleError('The selector returned duplicate source IDs.',502)
        for source_id in ids:
            if source_id not in known:raise RuleError('The selector returned an unsupported source ID.',502)
            source=known[source_id]
            if kind=='decision' and not is_decision(source):raise RuleError('The selected decision lacks an explicit decision marker. Review the transcript.',502)
            action,owner,due=commitment(source)
            if kind=='action' and not action:raise RuleError('The selected action lacks an explicit commitment. Add it manually if appropriate.',502)
            items.append({'id':f'I{len(items)+1:03d}','kind':kind,'text':source['text'],'source_id':source_id,'quote':source['text'],'owner':owner if kind=='action' else None,'due_text':due if kind=='action' else None,'included':True,'edited':False,'provenance':'ai-selected' if mode=='ai' else 'extractive'})
    if not items:raise RuleError('No items were selected. Use offline mode or add a more complete transcript.',502)
    return items
