import uuid

from fastapi import APIRouter, Depends, HTTPException

from fixmate.api.deps import AuthContext, get_current_user
from fixmate.api.schemas import FeedbackOut, FeedbackRequest
from fixmate.feedback.service import (
    EquipmentRequired,
    MessageNotFound,
    record_feedback,
)

router = APIRouter(prefix="/messages", tags=["feedback"])


@router.post("/{message_id}/feedback", status_code=201, response_model=FeedbackOut)
async def submit_feedback(
    message_id: uuid.UUID,
    body: FeedbackRequest,
    auth: AuthContext = Depends(get_current_user),
) -> FeedbackOut:
    try:
        result = await record_feedback(
            auth.org_id,
            message_id,
            auth.user_id,
            helped=body.helped,
            fix_text=body.fix_text,
            photos=body.photos,
        )
    except MessageNotFound as exc:
        raise HTTPException(status_code=404, detail="message not found") from exc
    except EquipmentRequired as exc:
        raise HTTPException(
            status_code=422, detail="a candidate fix requires the conversation's equipment"
        ) from exc
    return FeedbackOut(
        feedback_id=result.feedback_id, helped=result.helped, fix_id=result.fix_id
    )
