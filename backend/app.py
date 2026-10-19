from __future__ import annotations
import csv, io, json, os, sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token as google_id_token
from . import analytics
from .seed import DB, ROOT, connect, seed

@asynccontextmanager
async def lifespan(application):
 seed()
 yield

app=FastAPI(title="SkillSight Labour Market Intelligence",version="1.0.0",description="Local decision-support prototype; bundled records are synthetic.",lifespan=lifespan)
app.mount("/static",StaticFiles(directory=ROOT/"frontend"),name="static")
BUILT_FRONTEND=ROOT/"frontend"/"dist"
if (BUILT_FRONTEND/"assets").is_dir():
 app.mount("/assets",StaticFiles(directory=BUILT_FRONTEND/"assets"),name="assets")

def load_project_env():
 env_file=ROOT/".env"
 if not env_file.is_file():return
 for line in env_file.read_text(encoding="utf-8-sig").splitlines():
  line=line.strip()
  if not line or line.startswith("#") or "=" not in line:continue
  key,value=line.split("=",1);key=key.strip();value=value.strip().strip("\"'")
  if key and key not in os.environ:os.environ[key]=value

load_project_env()
FIREBASE_PROJECT_ID=os.getenv("FIREBASE_PROJECT_ID","").strip()

def verify_firebase_token(token:str):
 if not FIREBASE_PROJECT_ID:raise ValueError("FIREBASE_PROJECT_ID is not configured")
 claims=google_id_token.verify_firebase_token(token,GoogleAuthRequest(),audience=FIREBASE_PROJECT_ID)
 if claims.get("iss")!=f"https://securetoken.google.com/{FIREBASE_PROJECT_ID}":
  raise ValueError("Firebase token issuer does not match the configured project")
 if not claims.get("sub") or claims.get("uid",claims.get("sub"))!=claims.get("sub"):
  raise ValueError("Firebase token subject is invalid")
 return claims

@app.middleware("http")
async def firebase_authentication(request,call_next):
 path=request.url.path
 if not FIREBASE_PROJECT_ID or not path.startswith("/api/") or path=="/api/health":return await call_next(request)
 auth_header=request.headers.get("authorization","")
 if not auth_header.lower().startswith("bearer "):
  return JSONResponse({"detail":"Firebase sign-in is required."},status_code=401)
 try:claims=verify_firebase_token(auth_header[7:].strip())
 except Exception:
  return JSONResponse({"detail":"Firebase ID token is invalid or expired."},status_code=401)
 request.state.firebase_claims=claims
 if request.method in {"POST","PUT","PATCH","DELETE"} and path in {"/api/import","/api/scenarios"} and claims.get("role") not in {"planner","admin"}:
  return JSONResponse({"detail":"Planner or admin role is required for this operation."},status_code=403)
 return await call_next(request)

@app.get("/")
def home():
 built=BUILT_FRONTEND/"index.html"
 if built.is_file(): return FileResponse(built)
 return {"message":"Frontend build not found. Start Vite with `cd frontend && npm run dev`, or run `npm run build` to serve the production UI from FastAPI."}

def query_rows(state=None,district=None,sector=None,occupation_code=None,period=None):
 c=connect();sql="SELECT o.*,s.name source_name,s.source_type,s.access_method,s.is_synthetic FROM observations o JOIN sources s ON s.id=o.source_id WHERE 1=1";args=[]
 for col,val in [("state",state),("district",district),("sector",sector),("occupation_code",occupation_code),("period",period)]:
  if val is not None:sql+=f" AND o.{col}=?";args.append(val)
 rows=[dict(r) for r in c.execute(sql+" ORDER BY period",args).fetchall()];c.close();return rows

@app.get("/api/health")
def health():return {"status":"ok","database":str(DB),"data_label":"Synthetic demonstration data — not official government statistics","auth_required":bool(FIREBASE_PROJECT_ID)}

@app.get("/api/me")
def current_user(request:Request):
 claims=getattr(request.state,"firebase_claims",None)
 if not claims:return {"authenticated":False,"role":"demo"}
 return {"authenticated":True,"uid":claims.get("uid"),"email":claims.get("email"),"role":claims.get("role","viewer")}

@app.get("/api/filters")
def filters(state:Optional[str]=None):
 rows=query_rows(state=state);return {k:sorted({r[k] for r in rows}) for k in ["state","district","sector","occupation_code","period"]}|{"sources":sorted({r["source_name"] for r in rows})}

@app.get("/api/overview")
def overview(state:Optional[str]=None,district:Optional[str]=None,sector:Optional[str]=None,period:Optional[str]=None):
 rows=query_rows(state,district,sector,period=period)
 by_period={};by_occ={};by_area={}
 for r in rows:
  by_period[r["period"]]=by_period.get(r["period"],0)+r["demand_count"]
  o=by_occ.setdefault(r["occupation_code"],{"occupation_code":r["occupation_code"],"occupation_title":r["occupation_title"],"sector":r["sector"],"demand":0,"training_seats":0});o["demand"]+=r["demand_count"];o["training_seats"]+=r["training_seats"]
  key=(r["state"],r["district"]);a=by_area.setdefault(key,{"state":key[0],"district":key[1],"demand":0,"training_seats":0});a["demand"]+=r["demand_count"];a["training_seats"]+=r["training_seats"]
 latest=max((r["period"] for r in rows),default=None);snapshot=[r for r in rows if r["period"]==latest]
 return {"data_label":"Synthetic demonstration data — not official government statistics","filters":{"state":state,"district":district,"sector":sector,"period":period},"reporting_period":latest,"observed_demand_count":sum(r["demand_count"] for r in (rows if period else snapshot)),"occupation_count":len(by_occ),"training_seats":sum(r["training_seats"] for r in snapshot),"workforce_supply":"Unavailable: no comparable workforce measure in available data.","gap_classification":"Unavailable: demand and supply measures are not comparable.","demand_trend":[{"period":k,"value":v} for k,v in sorted(by_period.items())],"occupations":sorted(by_occ.values(),key=lambda x:-x["demand"]),"areas":sorted(by_area.values(),key=lambda x:-x["demand"]),"source_count":len({r["source_id"] for r in rows}),"quality_issues":sum(bool(r["quality_note"]) for r in rows)}

@app.get("/api/occupations")
def occupations(state:Optional[str]=None,sector:Optional[str]=None,period:Optional[str]=None,q:Optional[str]=None):
 rows=query_rows(state=state,sector=sector,period=period);keys=sorted({(r["occupation_code"],r["occupation_title"],r["sector"]) for r in rows})
 return [{"code":c,"title":t,"sector":s,"observations":sum(1 for r in rows if r["occupation_code"]==c),"demand_count":sum(r["demand_count"] for r in rows if r["occupation_code"]==c),"training_seats":sum(r["training_seats"] for r in rows if r["occupation_code"]==c),"skills":"Not provided in available data","classification_note":"Demo code; not an asserted NCO classification."} for c,t,s in keys if not q or q.lower() in (c+t+s).lower()]

@app.get("/api/occupations/{code}")
def occupation(code:str,state:Optional[str]=None,district:Optional[str]=None,period:Optional[str]=None):
 rows=query_rows(state,district,occupation_code=code,period=period)
 if not rows:raise HTTPException(404,"Occupation not found for selected filters")
 periods=sorted({r["period"] for r in rows})
 return {"code":code,"title":rows[0]["occupation_title"],"sector":rows[0]["sector"],"demand_trend":[{"period":p,"demand":sum(r["demand_count"] for r in rows if r["period"]==p)} for p in periods],"training_seats_latest":sum(r["training_seats"] for r in rows if r["period"]==periods[-1]),"sources":sorted({r["source_name"] for r in rows}),"classification_note":"Demo occupation code; no NCO mapping was supplied."}

@app.get("/api/geography")
def geography(state:Optional[str]=None,period:Optional[str]=None):
 rows=query_rows(state=state,period=period);latest=period or max((r["period"] for r in rows),default=None);rows=[r for r in rows if r["period"]==latest];d={}
 for r in rows:
  key=(r["state"],r["district"]);a=d.setdefault(key,{"state":key[0],"district":key[1],"observed_demand":0,"training_seats":0,"gap_status":"Insufficient evidence","gap_reason":"No comparable workforce supply measure."});a["observed_demand"]+=r["demand_count"];a["training_seats"]+=r["training_seats"]
 return {"reporting_period":latest,"areas":sorted(d.values(),key=lambda x:(x["state"],x["district"])),"map_available":False,"note":"No boundary data was provided; showing a geographic comparison table."}

@app.get("/api/forecasts")
def forecasts(state:Optional[str]=None,sector:Optional[str]=None,occupation_code:Optional[str]=None,period:Optional[str]=None,horizon:int=Query(3,ge=1,le=12)):
 return {"forecast":analytics.linear_forecast(query_rows(state=state,sector=sector,occupation_code=occupation_code,period=period),horizon),"scope":{"state":state,"sector":sector,"occupation_code":occupation_code,"period":period},"data_label":"Synthetic demonstration data — not official government statistics"}

@app.get("/api/alerts")
def alerts(state:Optional[str]=None,district:Optional[str]=None,sector:Optional[str]=None,period:Optional[str]=None):
 rows=query_rows(state,district,sector);periods=sorted(p for p in {r["period"] for r in rows} if not period or p<=period)
 if len(periods)<2:return {"period":periods[-1] if periods else None,"alerts":[],"rule_note":"At least two observed periods are required; planner review required."}
 latest=periods[-1];prev=periods[-2];groups={}
 for r in rows:
  if r["period"] in (latest,prev):
   k=(r["occupation_code"],r["occupation_title"],r["state"],r["district"]);groups.setdefault(k,{latest:0,prev:0})[r["period"]]+=r["demand_count"]
 out=[]
 for (code,title,state,district),g in groups.items():
  if g[prev]>0 and (g[latest]-g[prev])/g[prev]>=.25:out.append({"rule":"Demand proxy increased at least 25% from prior observed month","severity":"review","occupation_code":code,"occupation_title":title,"state":state,"district":district,"previous_period":prev,"previous_demand":g[prev],"current_period":latest,"current_demand":g[latest],"change_percent":round((g[latest]/g[prev]-1)*100,1),"interpretation":"Synthetic demand signal only; not a shortage classification."})
 return {"period":latest,"alerts":sorted(out,key=lambda x:-x["change_percent"]),"rule_note":"Deterministic threshold rule; planner review required."}

class AllocationRequest(BaseModel):
 budget:int=Field(ge=0,le=100000000);district_capacity:int=Field(ge=0,le=1000000);cost_per_seat:int=Field(default=10000,ge=1,le=100000000);state:Optional[str]=None;district:Optional[str]=None;sector:Optional[str]=None;period:Optional[str]=None;minimum_total_seats:int=Field(default=0,ge=0,le=1000000)

def make_allocation(req):
 rows=query_rows(req.state,req.district,req.sector,period=req.period);latest=req.period or max((r["period"] for r in rows),default=None);agg={}
 for r in rows:
  if r["period"]==latest:
   o=agg.setdefault(r["occupation_code"],{"occupation_code":r["occupation_code"],"occupation_title":r["occupation_title"],"demand":0,"cost_per_seat":req.cost_per_seat,"max_seats":0});o["demand"]+=r["demand_count"];o["max_seats"]+=r["training_seats"]
 result=analytics.optimize_allocations(list(agg.values()),req.budget,req.district_capacity)
 if result["status"]=="feasible" and result["total_seats"]<req.minimum_total_seats:result={"status":"infeasible","reason":f"Constraints allow at most {result['total_seats']} seats, below requested minimum of {req.minimum_total_seats}.","budget":req.budget,"capacity":req.district_capacity}
 return {"result":result,"assumptions":{"demand":"latest-period observed demand proxy","unit_cost":req.cost_per_seat,"human_review_required":True}}

@app.post("/api/allocations/optimize")
def optimize(req:AllocationRequest):
 try:return make_allocation(req)
 except ValueError as e:raise HTTPException(422,str(e))

class SaveScenario(BaseModel):name:str=Field(min_length=1,max_length=100);request:AllocationRequest

@app.post("/api/scenarios")
def save_scenario(s:SaveScenario):
 data=make_allocation(s.request)
 if data["result"]["status"]!="feasible":raise HTTPException(422,data["result"]["reason"])
 c=connect();cur=c.execute("INSERT INTO scenarios(name,inputs_json,result_json) VALUES(?,?,?)",(s.name,json.dumps(s.request.model_dump()),json.dumps(data)));c.commit();sid=cur.lastrowid;c.close();return {"id":sid,"name":s.name,"created":True,"data":data}

@app.get("/api/scenarios")
def list_scenarios():
 c=connect();rows=[dict(r) for r in c.execute("SELECT id,name,created_at FROM scenarios ORDER BY id DESC")];c.close();return rows

@app.get("/api/scenarios/{sid}")
def get_scenario(sid:int):
 c=connect();r=c.execute("SELECT * FROM scenarios WHERE id=?",(sid,)).fetchone();c.close()
 if not r:raise HTTPException(404,"Scenario not found")
 return {"id":r["id"],"name":r["name"],"created_at":r["created_at"],"request":json.loads(r["inputs_json"]),"data":json.loads(r["result_json"])}

@app.get("/api/sources")
def sources():
 c=connect();out=[dict(r) for r in c.execute("SELECT s.*,COUNT(o.id) observation_count,MIN(o.period) first_period,MAX(o.period) last_period FROM sources s LEFT JOIN observations o ON o.source_id=s.id GROUP BY s.id ORDER BY s.id")];c.close();return out

@app.post("/api/import")
async def import_csv(file:UploadFile=File(...),source_name:str=Query("CSV import",min_length=1,max_length=120),source_type:str=Query("imported",min_length=1,max_length=80),access_method:str=Query("user CSV upload",min_length=1,max_length=120)):
 if not file.filename.lower().endswith(".csv"):raise HTTPException(415,"Only CSV uploads are supported.")
 raw=await file.read(5*1024*1024+1)
 if len(raw)>5*1024*1024:raise HTTPException(413,"CSV exceeds 5 MiB limit.")
 try:text=raw.decode("utf-8-sig");reader=csv.DictReader(io.StringIO(text))
 except UnicodeDecodeError:raise HTTPException(422,"CSV must be UTF-8 encoded.")
 required={"period","state","district","sector","occupation_code","occupation_title","demand_count","training_seats"}
 if not reader.fieldnames or not required.issubset(reader.fieldnames):raise HTTPException(422,{"message":"Missing required columns","required":sorted(required)})
 parsed=[];errors=[]
 for line,row in enumerate(reader,start=2):
  try:
   p=row["period"].strip()
   if len(p)!=7 or p[4]!="-" or not(1<=int(p[5:])<=12):raise ValueError("period must be YYYY-MM")
   vals=[row[k].strip() for k in ["state","district","sector","occupation_code","occupation_title"]]
   if not all(vals):raise ValueError("text fields cannot be blank")
   nums=[]
   for k in ["demand_count","training_seats"]:
    v=int(row[k]);
    if v<0:raise ValueError(f"{k} must be nonnegative")
    nums.append(v)
   parsed.append((p,*vals,*nums,row.get("quality_note","").strip()))
  except (ValueError,TypeError,KeyError) as e:errors.append({"line":line,"error":str(e)})
 if errors:raise HTTPException(422,{"message":"Import rejected; no rows were saved.","errors":errors[:50],"invalid_row_count":len(errors)})
 if not parsed:raise HTTPException(422,"CSV contains no data rows.")
 seen=set()
 for r in parsed:
  key=(r[0],r[1],r[2],r[5])
  if key in seen:raise HTTPException(422,"Duplicate period/state/district/occupation records found; no rows were saved.")
  seen.add(key)
 c=connect()
 try:
  c.execute("BEGIN IMMEDIATE");sid=c.execute("INSERT INTO sources(name,source_type,access_method,is_synthetic,reporting_note) VALUES(?,?,?,?,?)",(source_name,source_type,access_method,0,"Imported; provenance supplied by uploader.")).lastrowid
  c.executemany("INSERT INTO observations(source_id,period,state,district,sector,occupation_code,occupation_title,demand_count,training_seats,quality_note) VALUES(?,?,?,?,?,?,?,?,?,?)",[(sid,*r) for r in parsed]);c.commit()
 except sqlite3.Error as e:c.rollback();raise HTTPException(422,f"Import transaction rolled back: {e}")
 finally:c.close()
 return {"source_id":sid,"rows_imported":len(parsed),"source_name":source_name,"status":"committed"}

def csv_response(rows,fields,filename):
 s=io.StringIO();w=csv.DictWriter(s,fieldnames=fields);w.writeheader();w.writerows(rows)
 return StreamingResponse(iter([s.getvalue()]),media_type="text/csv",headers={"Content-Disposition":f"attachment; filename={filename}"})

@app.get("/api/exports/observations.csv")
def export_observations(state:Optional[str]=None,sector:Optional[str]=None):
 fields=["period","state","district","sector","occupation_code","occupation_title","demand_count","training_seats","source_name","source_type","access_method","quality_note"];rows=query_rows(state=state,sector=sector)
 return csv_response([{k:r[k] for k in fields} for r in rows],fields,"skillsight-observations.csv")

@app.get("/api/exports/scenarios.csv")
def export_scenarios():
 c=connect();rows=[dict(r) for r in c.execute("SELECT * FROM scenarios ORDER BY id")];c.close();fields=["id","name","created_at","inputs_json","result_json"]
 return csv_response(rows,fields,"skillsight-scenarios.csv")
