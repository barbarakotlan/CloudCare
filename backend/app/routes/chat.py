import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_patient, get_current_user, get_patient_for_clinician
from app.database import get_db
from app.models import ChatMessage, Escalation, Patient, User
from app.routes.patients import active_care_plan
from app.schemas import ChatIn, ChatMessageOut, ChatReply
from app.services.ai_service import answer_question

router = APIRouter(prefix="/chat", tags=["chat"])

HISTORY_FOR_AI = 10  # recent messages passed to Foggy as context


@router.post("", response_model=ChatReply)
def send_message(body: ChatIn, db: Session = Depends(get_db), patient: Patient = Depends(get_current_patient)):
    """Patient asks Foggy. Red flags and unanswered questions go to the care team."""
    recent = db.scalars(
        select(ChatMessage).where(ChatMessage.patient_id == patient.id)
        .order_by(ChatMessage.created_at.desc()).limit(HISTORY_FOR_AI)
    ).all()
    history = [{"role": m.role, "content": m.content} for m in reversed(recent)]

    plan = active_care_plan(db, patient.id)
    chunks = [{"id": c.id, "section": c.section, "content": c.content} for c in (plan.chunks if plan else [])]

    patient_msg = ChatMessage(patient_id=patient.id, role="patient", content=body.message)
    db.add(patient_msg)
    db.flush()

    answer = answer_question(body.message, chunks, history)
    reply = ChatMessage(
        patient_id=patient.id,
        role="assistant",
        content=answer["content"],
        citations=answer["citations"],
        answered_from_plan=answer["answered_from_plan"],
        red_flag=answer["red_flag"],
    )
    db.add(reply)

    escalated = False
    if answer["red_flag"]:
        db.add(Escalation(
            patient_id=patient.id, trigger_type="red_flag", severity="emergency",
            chat_message_id=patient_msg.id, summary=f'Possible emergency. Patient said: "{body.message}"',
        ))
        escalated = True
    elif not answer["answered_from_plan"]:
        db.add(Escalation(
            patient_id=patient.id, trigger_type="unanswered_question", severity="low",
            chat_message_id=patient_msg.id, summary=f'Not covered by care plan. Patient asked: "{body.message}"',
        ))
        escalated = True

    db.commit()
    db.refresh(reply)
    return ChatReply(message=ChatMessageOut.model_validate(reply), escalated=escalated)


@router.get("/history", response_model=list[ChatMessageOut])
def chat_history(
    patient_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Oldest first. Patients see their own; clinicians pass ?patient_id=."""
    if user.role == "patient":
        patient = db.scalar(select(Patient).where(Patient.user_id == user.id))
        if patient is None:
            raise HTTPException(404, "No patient profile for this account")
    elif patient_id is None:
        raise HTTPException(422, "patient_id is required for clinicians")
    else:
        patient = get_patient_for_clinician(db, user, patient_id)

    return db.scalars(
        select(ChatMessage).where(ChatMessage.patient_id == patient.id).order_by(ChatMessage.created_at)
    ).all()
