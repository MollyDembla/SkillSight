import csv, io, os
from pathlib import Path
import re
import pytest
from fastapi.testclient import TestClient
from backend import analytics

@pytest.fixture()
def client(monkeypatch):
 db=Path(__file__).resolve().parent/"test-runtime.db"
 if db.exists():db.unlink()
 monkeypatch.setenv("SKILLSIGHT_DB",str(db))
 # seed module captured its path at import time; update it before importing app calls.
 from backend import seed
 monkeypatch.setattr(seed,"DB",db)
 from backend import app as app_module
 monkeypatch.setattr(app_module,"DB",db)
 with TestClient(app_module.app) as c:yield c
 if db.exists():db.unlink()

def test_demo_seed_and_overview_are_reproducible(client):
 a=client.get('/api/overview').json();b=client.get('/api/overview').json()
 assert a==b and a['occupation_count']==5 and a['reporting_period']=='2025-12'
 assert 'Synthetic' in a['data_label'] and 'Unavailable' in a['gap_classification']

def test_forecast_requires_history_and_is_deterministic():
 assert analytics.linear_forecast([{'period':'2025-01','demand_count':4}],3)['status']=='insufficient_history'
 rows=[{'period':f'2025-{m:02}','demand_count':m*10} for m in range(1,5)]
 a=analytics.linear_forecast(rows,2);assert a==analytics.linear_forecast(rows,2)
 assert [x['value'] for x in a['points']]==[65,75]
 with pytest.raises(ValueError):analytics.linear_forecast(rows,13)

def test_optimizer_respects_budget_capacity_and_integer_seats():
 items=[{'occupation_code':'A','occupation_title':'A','demand':10,'max_seats':10,'cost_per_seat':10},{'occupation_code':'B','occupation_title':'B','demand':10,'max_seats':10,'cost_per_seat':10}]
 r=analytics.optimize_allocations(items,70,5)
 assert r['status']=='feasible' and r['total_cost']<=70 and r['total_seats']<=5
 assert all(isinstance(x['seats'],int) for x in r['allocations'])

def test_import_success_validation_rollback_and_provenance(client):
 good='period,state,district,sector,occupation_code,occupation_title,demand_count,training_seats,quality_note\n2026-01,Test,Test district,Health,TEST-1,Test role,7,4,checked\n'
 r=client.post('/api/import?source_name=Unit+fixture',files={'file':('input.csv',good,'text/csv')});assert r.status_code==200 and r.json()['rows_imported']==1
 sources=client.get('/api/sources').json();src=next(x for x in sources if x['name']=='Unit fixture')
 assert src['is_synthetic']==0 and src['source_type']=='imported' and src['access_method']=='user CSV upload' and src['observation_count']==1
 bad=good.replace(',7,4,',',oops,4,')
 r=client.post('/api/import',files={'file':('bad.csv',bad,'text/csv')});assert r.status_code==422
 assert 'no rows were saved' in r.text
 assert next(x for x in client.get('/api/sources').json() if x['name']=='CSV import')['observation_count']==0 if any(x['name']=='CSV import' for x in client.get('/api/sources').json()) else True

def test_scenario_save_reload_and_export(client):
 page=client.get('/');assert page.status_code==200 and 'id="root"' in page.text
 js=re.search(r'src="(/assets/[^\"]+\.js)"',page.text);css=re.search(r'href="(/assets/[^\"]+\.css)"',page.text)
 assert js and css and client.get(js.group(1)).status_code==200 and client.get(css.group(1)).status_code==200
 assert client.get('/static/demo-template.csv').status_code==200
 req={'budget':1000000,'district_capacity':20,'cost_per_seat':1000,'state':'Karnataka','minimum_total_seats':1}
 opt=client.post('/api/allocations/optimize',json=req);assert opt.status_code==200 and opt.json()['result']['status']=='feasible'
 save=client.post('/api/scenarios',json={'name':'Test plan','request':req});assert save.status_code==200
 sid=save.json()['id'];assert client.get(f'/api/scenarios/{sid}').json()['name']=='Test plan'
 assert 'Test plan' in client.get('/api/exports/scenarios.csv').text

def test_infeasible_minimum_and_geography_evidence(client):
 r=client.post('/api/allocations/optimize',json={'budget':0,'district_capacity':0,'minimum_total_seats':1}).json()
 assert r['result']['status']=='infeasible'
 geo=client.get('/api/geography').json();assert geo['map_available'] is False
 assert all(x['gap_status']=='Insufficient evidence' for x in geo['areas'])

def test_firebase_auth_and_planner_role_middleware(client,monkeypatch):
 from backend import app as module
 monkeypatch.setattr(module,'FIREBASE_PROJECT_ID','test-project')
 assert client.get('/api/health').json()['auth_required'] is True
 assert client.get('/api/overview').status_code==401
 monkeypatch.setattr(module,'verify_firebase_token',lambda token:{'uid':'test-user','role':'viewer' if token=='viewer' else 'planner'})
 assert client.get('/api/overview',headers={'Authorization':'Bearer viewer'}).status_code==200
 assert client.get('/api/me',headers={'Authorization':'Bearer viewer'}).json()['role']=='viewer'
 payload={'name':'Unauthorized plan','request':{'budget':100000,'district_capacity':2,'cost_per_seat':1000}}
 assert client.post('/api/scenarios',json=payload,headers={'Authorization':'Bearer viewer'}).status_code==403
 payload['name']='Authorized plan'
 assert client.post('/api/scenarios',json=payload,headers={'Authorization':'Bearer planner'}).status_code==200
