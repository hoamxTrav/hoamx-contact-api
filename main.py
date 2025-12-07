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

Base = declarative_base()
_engine = None
_SessionLocal = None


def init_engine():
    """
    Lazily initialize the engine & sessionmaker.
    This avoids crashing the container at import/startup time.
    """
    global _engine, _SessionLocal

    if _engine is not None and _SessionLocal is not None:
        return

    if not DATABASE_URL:
        # Don't crash the whole service – surface a clear error on request instead.
        raise RuntimeError("DATABASE_URL environment variable is not set")

    try:
        _engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

        # Create tables if they don't exist
        Base.metadata.create_all(bind=_engine)
    except Exception as exc:
        # Bubble up a useful error; FastAPI will turn this into a 500 on request.
        raise RuntimeError(f"Failed to initialize database engine: {exc}") from exc


def get_db():
    try:
        init_engine()
    except RuntimeError as exc:
        # Convert engine/init errors into HTTP 500s, not container crashes
        raise HTTPException(status_code=500, detail=str(exc))

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
    association: str | None = None
    role: str | None = None
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
    # Keep health simple; don't force a DB check here
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
    except HTTPException:
        # Re-raise cleanly for init errors
        raise
    except Exception as exc:
        # In a real app: log the exception
        raise HTTPException(
            status_code=500,
            detail=f"Unable to submit message at this time: {exc}",
        )
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )
