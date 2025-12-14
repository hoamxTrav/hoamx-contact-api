import os
import uvicorn

from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional

from sqlalchemy import create_engine, Column, Integer, Text, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.sql import text

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL")
HEALTH_TOKEN = os.getenv("HEALTH_TOKEN")

# -----------------------------------------------------------------------------
# Database setup
# -----------------------------------------------------------------------------

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
    _SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=_engine,
    )

    Base.metadata.create_all(bind=_engine)


def get_db():
    try:
        init_engine()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail="Database not configured")

    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -----------------------------------------------------------------------------
# Pydantic schema
# -----------------------------------------------------------------------------

class ContactPayload(BaseModel):
    name: str
    email: EmailStr
    association: Optional[str] = None
    role: Optional[str] = None
    message: str


# -----------------------------------------------------------------------------
# ORM model
# -----------------------------------------------------------------------------

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


# -----------------------------------------------------------------------------
# FastAPI app
# -----------------------------------------------------------------------------

app = FastAPI(
    title="HOAMX Contact API",
    description="Receives contact form submissions and stores them in Postgres.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://www.hoamx.com",
        "https://hoamx.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# Health endpoints
# -----------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/db")
def health_db(
    request: Request,
    db: Session = Depends(get_db),
):
    token = request.headers.get("x-health-token")
    if not HEALTH_TOKEN or token != HEALTH_TOKEN:
        # Hide existence
        raise HTTPException(status_code=404, detail="not found")

    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        print(f"health_db error: {exc!r}")
        raise HTTPException(status_code=500, detail="db error")


# -----------------------------------------------------------------------------
# Contact endpoint
# -----------------------------------------------------------------------------

@app.post("/api/contact")
def create_contact(
    payload: ContactPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        client_ip = (
            request.headers.get("x-forwarded-for", "").split(",")[0]
            or request.client.host
            if request.client
            else None
        )

        cm = ContactMessage(
            name=payload.name.strip(),
            email=payload.email.strip(),
            association=(payload.association or "").strip() or None,
            role=(payload.role or "").strip() or None,
            message=payload.message.strip(),
            source_page="contact.html",
            ip_address=client_ip,
            user_agent=request.headers.get("user-agent"),
        )

        db.add(cm)
        db.commit()
        db.refresh(cm)

        return {"ok": True, "id": cm.id}

    except Exception as exc:
        print(f"contact insert error: {exc!r}")
        raise HTTPException(
            status_code=500,
            detail="Unable to submit message at this time.",
        )


# -----------------------------------------------------------------------------
# Local entrypoint (Cloud Run ignores this, but it’s fine to keep)
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
    )
