from fastapi import FastAPI
from app.routers.auth import auth_router


app = FastAPI()
app.include_router(auth_router)

@app.get("/")
def read_root():
    return {"status": "ok"}