"""Unified FastAPI entrypoint for all Phase 4 APIs."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from PHASE_4.API1 import app as api1_app
from PHASE_4.API2 import app as api2_app
from PHASE_4.API3 import app as api3_app
from PHASE_4.API4 import app as api4_app
from PHASE_4.API5 import app as api5_app
from PHASE_4.API6 import app as api6_app


app = FastAPI(title="Telecom Network API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for phase_app in (api1_app, api2_app, api3_app, api4_app, api5_app, api6_app):
    app.include_router(phase_app.router)
