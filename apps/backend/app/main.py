# apps/backend/app/main.py

from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def read_root():
    return {"message": "🎉 Your FastAPI app is live on Render!"}
