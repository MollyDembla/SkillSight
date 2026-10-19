from __future__ import annotations
import hashlib, os, threading, time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token as google_id_token
from .db import ROOT, connect, db_path
from .pipeline import run as pipeline
from .synth.generate import seed
from .api import v1


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
REFRESH_HOURS=float(os.getenv("SKILLSIGHT_REFRESH_HOURS","24"))
MUTATING={"/api/v1/import","/api/v1/scenarios","/api/v1/pipeline/run","/api/v1/api-keys","/api/v1/webhooks"}


def _scheduler():
 """Periodic refresh so forecasts are updated continuously rather than annually."""
 while True:
  time.sleep(REFRESH_HOURS*3600)
  try:pipeline.run("scheduled")
  except Exception:pass


@asynccontextmanager
async def lifespan(application):
 seed()
 c=connect();has_run=pipeline.last_run(c) is not None;c.close()
 if has_run:threading.Thread(target=pipeline.ensure_ready,daemon=True).start()  # serve stored results while the model warms up
 else:pipeline.run("startup")
 if REFRESH_HOURS>0:threading.Thread(target=_scheduler,daemon=True).start()
 yield

app=FastAPI(title="SkillSight - Labour Market Intelligence System",version="2.0.0",lifespan=lifespan,
 description="AI-enabled labour market intelligence and skill demand-supply forecasting for MSDE (SIH 2026, PS 26246). Bundled records are synthetic demonstration data. "
 "Machine clients authenticate with an `X-API-Key` header when authentication is enabled.")
app.include_router(v1.router)
BUILT_FRONTEND=ROOT/"frontend"/"dist"
if (BUILT_FRONTEND/"assets").is_dir():
 app.mount("/assets",StaticFiles(directory=BUILT_FRONTEND/"assets"),name="assets")
if (BUILT_FRONTEND/"geo").is_dir():
 app.mount("/geo",StaticFiles(directory=BUILT_FRONTEND/"geo"),name="geo")

def verify_firebase_token(token:str):
 if not FIREBASE_PROJECT_ID:raise ValueError("FIREBASE_PROJECT_ID is not configured")
 claims=google_id_token.verify_firebase_token(token,GoogleAuthRequest(),audience=FIREBASE_PROJECT_ID)
 if claims.get("iss")!=f"https://securetoken.google.com/{FIREBASE_PROJECT_ID}":
  raise ValueError("Firebase token issuer does not match the configured project")
 if not claims.get("sub") or claims.get("uid",claims.get("sub"))!=claims.get("sub"):
  raise ValueError("Firebase token subject is invalid")
 return claims

def verify_api_key(key:str):
 c=connect()
 try:
  r=c.execute("SELECT id,name FROM api_keys WHERE key_hash=? AND revoked=0",(hashlib.sha256(key.encode()).hexdigest(),)).fetchone()
  return {"uid":f"api-key:{r['id']}","name":r["name"],"role":"machine"} if r else None
 finally:c.close()

@app.middleware("http")
async def authentication(request,call_next):
 path=request.url.path
 if not FIREBASE_PROJECT_ID or not path.startswith("/api/") or path=="/api/health":return await call_next(request)
 api_key=request.headers.get("x-api-key","").strip()
 if api_key:
  claims=verify_api_key(api_key)
  if not claims:return JSONResponse({"detail":"API key is invalid or revoked."},status_code=401)
  if request.method!="GET":return JSONResponse({"detail":"API keys are read-only."},status_code=403)
  request.state.firebase_claims=claims
  return await call_next(request)
 auth_header=request.headers.get("authorization","")
 if not auth_header.lower().startswith("bearer "):
  return JSONResponse({"detail":"Firebase sign-in or an X-API-Key header is required."},status_code=401)
 try:claims=verify_firebase_token(auth_header[7:].strip())
 except Exception:
  return JSONResponse({"detail":"Firebase ID token is invalid or expired."},status_code=401)
 request.state.firebase_claims=claims
 if request.method in {"POST","PUT","PATCH","DELETE"} and (path in MUTATING or path.startswith("/api/v1/alerts/") or path.startswith("/api/v1/api-keys/")) and claims.get("role") not in {"planner","admin"}:
  return JSONResponse({"detail":"Planner or admin role is required for this operation."},status_code=403)
 return await call_next(request)

@app.get("/")
def home():
 built=BUILT_FRONTEND/"index.html"
 if built.is_file(): return FileResponse(built)
 return {"message":"Frontend build not found. Start Vite with `cd frontend && npm run dev`, or run `npm run build` to serve the production UI from FastAPI."}

@app.get("/api/health")
def health():return {"status":"ok","database":str(db_path()),"data_label":"Synthetic demonstration data - not official government statistics","auth_required":bool(FIREBASE_PROJECT_ID),"model_ready":pipeline.STATE.get("frame") is not None}

@app.get("/api/me")
def current_user(request:Request):
 claims=getattr(request.state,"firebase_claims",None)
 if not claims:return {"authenticated":False,"role":"demo"}
 return {"authenticated":True,"uid":claims.get("uid"),"email":claims.get("email"),"role":claims.get("role","viewer")}
