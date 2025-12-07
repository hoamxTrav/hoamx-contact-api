import os

from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

from sqlalchemy import create_engine, Column, Integer, Text, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# -----------------------------------------------------------------------------
# Database setup
# -----------------------------------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Fail fast if env var isn't set
    raise RuntimeError("DATABASE_URL environment variable is not set")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


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


# Create table if it doesn't exist (fine to keep even if you already created it)
Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
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
    association: str | None = None
    role: str | None = None
    message: str


# -----------------------------------------------------------------------------
# FastAPI app
# -----------------------------------------------------------------------------

app = FastAPI(
    title="HOAMX Contact API",
    description="Receives contact form submissions and stores them in Postgres.",
    version="1.0.0",
)

# CORS: allow your website to call the API directly
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://www.hoamx.com",
        "https://hoamx.com",
        # add staging domains here if you have them
    ],
    allow_credentials=True,
    allow_methods=["POST", "OPTIONS", "GET"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/contact")
async def create_contact(
    payload: ContactPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
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
    except Exception:
        # In a real app: log the exception
        raise HTTPException(
            status_code=500,
            detail="Unable to submit message at this time."
        )
