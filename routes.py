from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..discovery.fetcher import SourceNotAllowed, fetch_official, is_official
from ..eligibility.engine import evaluate
from ..models import RuleSet, Scheme, SourceSnapshot, StudentProfile, User
from ..schemas import (Credentials, ProfileIn, RefreshIn, RuleSetCreate, SchemeCreate, SchemeOut, TokenOut)
from ..security import current_user, hash_password, make_token, require_admin, verify_password

router = APIRouter()
STALE_AFTER = timedelta(days=7)


# ---------- auth ----------
@router.post("/auth/register", response_model=TokenOut, status_code=201)
def register(body: Credentials, db: Session = Depends(get_db)):
    user = User(email=body.email.lower(), password_hash=hash_password(body.password), role="student")
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Email already registered")
    db.add(StudentProfile(user_id=user.id, data={}))
    db.commit()
    audit.record(db, "USER_REGISTERED")
    return TokenOut(access_token=make_token(user))


@router.post("/auth/login", response_model=TokenOut)
def login(body: Credentials, db: Session = Depends(get_db)):
    user = db.scalars(select(User).where(User.email == body.email.lower())).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    return TokenOut(access_token=make_token(user))


# ---------- profile ----------
@router.get("/profile")
def get_profile(user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.get(StudentProfile, user.id)
    return p.data if p else {}


@router.put("/profile")
def put_profile(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.get(StudentProfile, user.id) or StudentProfile(user_id=user.id, data={})
    p.data = body.model_dump(exclude_none=True)
    db.add(p)
    db.commit()
    return p.data


# ---------- schemes ----------
def _scheme_out(s: Scheme, db: Session) -> SchemeOut:
    if s.application_deadline is None or not s.deadline_verified:
        status = "UNKNOWN"
    else:
        status = "OPEN" if s.application_deadline >= date.today() else "CLOSED"
    retrieved = s.retrieved_at if s.retrieved_at.tzinfo else s.retrieved_at.replace(tzinfo=timezone.utc)
    approved = db.scalars(select(RuleSet.id).where(RuleSet.scheme_id == s.id, RuleSet.status == "approved")).first()
    return SchemeOut(
        id=s.id, scheme_key=s.scheme_key, name=s.name, provider=s.provider, academic_year=s.academic_year,
        official_url=s.official_url, guideline_url=s.guideline_url, application_deadline=s.application_deadline,
        deadline_verified=s.deadline_verified, application_status=status,
        required_documents=s.required_documents or [], retrieved_at=s.retrieved_at,
        source_snapshot_id=s.source_snapshot_id,
        possibly_outdated=datetime.now(timezone.utc) - retrieved > STALE_AFTER,
        has_approved_rules=approved is not None,
    )


@router.get("/schemes", response_model=list[SchemeOut])
def list_schemes(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return [_scheme_out(s, db) for s in db.scalars(select(Scheme).order_by(Scheme.name))]


@router.post("/admin/sources/refresh")
def refresh_source(body: RefreshIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        r = fetch_official(body.url)
    except SourceNotAllowed as e:
        raise HTTPException(400, str(e))
    snap = SourceSnapshot(url=r["url"], source_type=body.source_type, http_status=r["http_status"],
                          retrieved_at=r["retrieved_at"], sha256=r["sha256"], content_text=r["content_text"])
    db.add(snap)
    db.commit()
    audit.record(db, "SOURCE_SNAPSHOT", verification_result=str(r["http_status"]), evidence_ref=snap.sha256)
    return {"snapshot_id": snap.id, "http_status": snap.http_status, "sha256": snap.sha256,
            "retrieved_at": snap.retrieved_at, "text_preview": snap.content_text[:2000]}


@router.post("/admin/schemes", response_model=SchemeOut, status_code=201)
def create_scheme(body: SchemeCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not is_official(body.official_url) or (body.guideline_url and not is_official(body.guideline_url)):
        raise HTTPException(400, "Scheme and guideline URLs must be official https sources")
    snap = db.get(SourceSnapshot, body.source_snapshot_id)
    if not snap:
        raise HTTPException(400, "source_snapshot_id does not exist; fetch the source first")
    s = Scheme(**body.model_dump(), retrieved_at=snap.retrieved_at)
    db.add(s)
    db.commit()
    audit.record(db, "SCHEME_ADDED", evidence_ref=snap.sha256)
    return _scheme_out(s, db)


@router.post("/admin/rulesets", status_code=201)
def create_ruleset(body: RuleSetCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not db.get(Scheme, body.scheme_id):
        raise HTTPException(404, "Scheme not found")
    for c in body.criteria:
        if not is_official(c.source_reference.split("#")[0].split(" ")[0]):
            raise HTTPException(400, f"Criterion '{c.field}' needs an official https source_reference")
    rs = RuleSet(scheme_id=body.scheme_id, academic_year=body.academic_year,
                 criteria=[{**c.model_dump(), "verified": False} for c in body.criteria], status="draft")
    db.add(rs)
    db.commit()
    return {"id": rs.id, "status": rs.status}


@router.post("/admin/rulesets/{rs_id}/approve")
def approve_ruleset(rs_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """A human admin attests they checked each criterion against its official source."""
    rs = db.get(RuleSet, rs_id)
    if not rs:
        raise HTTPException(404, "Rule set not found")
    rs.criteria = [{**c, "verified": True} for c in rs.criteria]
    rs.status, rs.approved_by, rs.approved_at = "approved", admin.id, datetime.now(timezone.utc)
    db.commit()
    audit.record(db, "RULESET_APPROVED", evidence_ref=rs.id)
    return {"id": rs.id, "status": rs.status}


# ---------- eligibility ----------
@router.post("/eligibility/{scheme_id}")
def check_eligibility(scheme_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    scheme = db.get(Scheme, scheme_id)
    if not scheme:
        raise HTTPException(404, "Scheme not found")
    profile = (db.get(StudentProfile, user.id) or StudentProfile(user_id=user.id, data={})).data
    rs = db.scalars(select(RuleSet).where(RuleSet.scheme_id == scheme_id, RuleSet.status == "approved")
                    .order_by(RuleSet.approved_at.desc())).first()
    result = evaluate(
        scheme_id=scheme_id, rule_academic_year=rs.academic_year if rs else scheme.academic_year,
        criteria=rs.criteria if rs else [], profile=profile, target_academic_year=scheme.academic_year,
        rule_set_approved=rs is not None,
    )
    audit.record(db, "ELIGIBILITY_EVALUATED", application_ref=scheme_id, verification_result=result.overall,
                 evidence_ref=rs.id if rs else None)
    return {
        "scheme": _scheme_out(scheme, db), "overall": result.overall, "summary": result.summary,
        "missing_fields": result.missing_fields,
        "conditions": [c.__dict__ for c in result.conditions],
        "labels": {"conditions": "Official rule (admin-verified)", "values": "Student-provided",
                   "explanations": "System-generated from deterministic rules"},
    }


@router.get("/audit/verify")
def verify_audit(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return audit.verify_chain(db)
