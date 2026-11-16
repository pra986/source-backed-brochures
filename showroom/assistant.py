"""Read-only tool router: models select typed operations, never write bookings."""
import json
import os
import re
import httpx
from pydantic import ValidationError
from .db import RuleError
from .models import Plan, Search

HELP='Search by budget (for example, under 12 lakh), brand, fuel, transmission or body type. Compare two or three IDs, such as CAR-001 and CAR-002. To request a demo booking, select a car, sign in, review its preview and explicitly confirm. Chat cannot create bookings. Mileage, safety ratings, discounts and finance information are not in this synthetic catalog.'

def offline_plan(message):
    text=message.strip().lower()
    if not text: raise RuleError('Enter a question.')
    ids=list(dict.fromkeys(f'CAR-{int(n):03d}' for n in re.findall(r'\bcar[- ]?0*(\d{1,3})\b',text)))
    if any(re.search(r'\b'+x+r'\b',text) for x in ['book','booking','reserve','pay','mileage','safety','loan','discount','emi','not','except','exclude','without']):
        return Plan(action='help')
    if 'compare' in text:
        if not 2<=len(ids)<=3:return Plan(action='help')
        return Plan(action='compare',ids=ids)
    if ids:
        return Plan(action='details',ids=ids[:1])
    filters={}
    # One shared unit at the end of a simple range: between 8 and 12 lakh.
    match=re.search(r'\bbetween\s+(\d+(?:\.\d+)?)\s+and\s+(\d+(?:\.\d+)?)\s*(lakh|lakhs|lac|lacs|crore|crores)?\b',text)
    def amount(number,unit):return round(float(number)*({'lakh':100000,'lakhs':100000,'lac':100000,'lacs':100000,'crore':10000000,'crores':10000000}.get(unit,1)))
    if match:
        filters['min_price']=amount(match[1],match[3]);filters['max_price']=amount(match[2],match[3])
    else:
        match=re.search(r'\b(under|below|upto|up to|budget|above|over)\s*(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)\s*(lakh|lakhs|lac|lacs|crore|crores)?\b',text)
        if match:
            filters['min_price' if match[1] in ['above','over'] else 'max_price']=amount(match[2].replace(',',''),match[3])
    if not match and re.search(r'\b(under|below|upto|up to|budget|above|over|between)\b',text):
        return Plan(action='help')
    for field,choices in [('brand',['aster','sahyadri','nexaura']),('fuel',['petrol','diesel','electric','hybrid']),('transmission',['manual','automatic']),('body_type',['hatchback','sedan','suv'])]:
        found=[c for c in choices if re.search(r'\b'+c+r'\b',text)]
        if len(found)>1:return Plan(action='help')
        if found:filters[field]=found[0]
    if not filters and not re.search(r'\b(cars?|inventory|show|list|available|browse)\b',text):return Plan(action='help')
    try:return Plan(action='search',filters=Search(**filters))
    except ValidationError as exc:raise RuleError('The budget range is invalid. Please use a non-negative minimum below the maximum.') from exc

def provider_plan(message):
    key,model=os.getenv('OPENAI_API_KEY'),os.getenv('OPENAI_MODEL')
    if not key or not model:raise RuleError('AI mode requires server-side OPENAI_API_KEY and OPENAI_MODEL. Use offline mode for the no-key demo.',503)
    prompt='''Translate the user message into a READ-ONLY JSON tool plan. Never invent answers or booking writes.
Return {"action":"search|compare|details|help","filters":{},"ids":[]}.
Search filters: min_price/max_price (integer INR), brand, fuel (petrol/diesel/electric/hybrid), transmission (manual/automatic), body_type (hatchback/sedan/suv), available_only (boolean).
1 lakh = 100000 INR. Brands: Aster, Sahyadri, Nexaura. IDs use CAR-001 format.
Choose help for booking actions or unsupported facts such as mileage, safety, loans or discounts.
Compare needs 2-3 distinct IDs. Details needs one ID. No SQL and no extra fields.'''
    try:
        with httpx.Client(timeout=25,follow_redirects=False) as client:
            r=client.post(os.getenv('OPENAI_BASE_URL','https://api.openai.com/v1').rstrip('/')+'/chat/completions',headers={'Authorization':f'Bearer {key}'},json={'model':model,'messages':[{'role':'system','content':prompt},{'role':'user','content':message}],'response_format':{'type':'json_object'}})
            r.raise_for_status()
            return Plan.model_validate_json(r.json()['choices'][0]['message']['content'])
    except (httpx.HTTPError,ValueError,KeyError,IndexError,TypeError) as exc:
        raise RuleError('AI routing failed or returned an invalid plan. Retry or select offline mode.',502) from exc

def answer(store,message,mode='offline',router=None):
    plan=(router or provider_plan)(message) if mode=='ai' else offline_plan(message)
    if not isinstance(plan,Plan):raise RuleError('The router returned an invalid tool plan.',502)
    for identifier in plan.ids:
        if not re.fullmatch(r'CAR-\d{3}',identifier):raise RuleError('Invalid car identifier in tool plan.',400)
    trace={'tool':plan.action,'arguments':plan.model_dump(exclude={'action'}),'mode':mode,'readonly':True}
    if plan.action=='help':return {'message':HELP,'cars':[],'trace':trace,'synthetic':True}
    if plan.action=='compare':
        if not 2<=len(plan.ids)<=3 or len(set(plan.ids))!=len(plan.ids):raise RuleError('Compare requires two or three distinct car IDs.')
        result=store.compare(plan.ids)
        text='Side-by-side comparison from the current synthetic inventory. Lowest listed price: '+', '.join(result['lowest_price_ids'])+'. No real-world performance is inferred.'
    elif plan.action=='details':
        if len(plan.ids)!=1:raise RuleError('Details requires exactly one car ID.')
        result={'cars':[store.car(plan.ids[0])]};text='Current details from the synthetic inventory.'
    else:
        result={'cars':store.search(plan.filters)}
        text=(f"Found {len(result['cars'])} matching demo cars. Prices are integer INR, exclude fees, and are not real quotations." if result['cars'] else 'No current demo cars match those filters. Try a larger budget or fewer filters.')
    return {'message':text,**result,'trace':trace,'synthetic':True}
