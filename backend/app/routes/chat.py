import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_patient, get_current_user, get_patient_for_clinician
from app.database import get_db
from app.models import ChatMessage, Patient, User
from app.schemas import ChatCapabilities, ChatIn, ChatMessageOut, ChatReply
from app.services.foggy import answer_turn, capabilities

router = APIRouter(prefix="/chat", tags=["chat"])
log = logging.getLogger("cloudcare.chat")


@router.post("", response_model=ChatReply)
def send_message(body: ChatIn, db: Session = Depends(get_db), patient: Patient = Depends(get_current_patient)):
    """One Foggy turn (text or voice share the same routing and state; docs/foggy-policy.md).

    Nothing goes to the care team unless the patient agrees to a specific offer, except the
    red-flag alert for a possible emergency. `escalated` is true only when a real escalation
    row was created during this turn.
    """
    log.info("chat.message source=%s", body.source)  # event name only, never the message
    turn = answer_turn(db, patient, body.message, source=body.source)
    db.commit()
    db.refresh(turn.message)
    return ChatReply(
        message=ChatMessageOut.model_validate(turn.message),
        route=turn.route,
        offer_contact=turn.offer_contact,
        pending_action=turn.pending_action,
        action_result=turn.action_result,
        checkin=turn.checkin,
        escalated=turn.escalated,
    )


@router.get("/capabilities", response_model=ChatCapabilities)
def chat_capabilities(user: User = Depends(get_current_user)):
    """What Foggy can really do here. Clients must not offer anything listed as false."""
    return capabilities()


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
