import os
import requests

from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional

from sqlalchemy import create_engine, Column, Integer, Text, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.sql import text

DATABASE_URL = os.getenv("DATABASE_URL")

Base = declarative_base()
_engine = None
_SessionLocal = None


def init_engine():
    global _engine, _SessionLocal
    if _engine is not None and _SessionLocal is not None:
        return
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable is not set")

    _engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    Base.metadata.create_all(bind=_engine)


def get_db():
    try:
        init_engine()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"DB init failed: {exc}")

    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ContactPayload(BaseModel):
    name: str
    email: EmailStr
    association: Optional[str] = None
    role: Optional[str] = None
    message: str


class ContactMessage(Base):
    __tablename__ = "contact_messages"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    name = Column(Text, nullable=False)
    email = Column(Text, nullable=False)
    association = Column(Text)
    role = Column(Text)
    message = Column(Text)
    source_page = Column(Text, nullable=False, default="contact.html")
    ip_address = Column(Text)
    user_agent = Column(Text)


app = FastAPI(title="HOAMX Contact API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://www.hoamx.com", "https://hoamx.com"],
    allow_credentials=True,
    allow_methods=["POST", "OPTIONS", "GET"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    db_host = DATABASE_URL.split("@")[1].split(":")[0] if DATABASE_URL and "@" in DATABASE_URL else "unknown"
    try:
        public_ip = requests.get("https://api.ipify.org", timeout=5).text
    except Exception:
        public_ip = "unknown"
    return {"status": "ok", "to_ip": db_host, "from_ip": public_ip}


@app.post("/api/contact")
async def create_contact(payload: ContactPayload, request: Request, db: Session = Depends(get_db)):
    client_host = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    cm = ContactMessage(
        name=payload.name.strip(),
        email=payload.email.strip(),
        association=(payload.association or "").strip() or None,
        role=(payload.role or "").strip() or None,
        message=payload.message.strip(),
        source_page="contact.html",
        ip_address=client_host,
        user_agent=user_agent,
    )

    db.add(cm)
    db.commit()
    db.refresh(cm)
    return {"ok": True, "id": cm.id}
