"""Human-review endpoints for exception approval (Task 8).

GET  /api/v1/exceptions[?status=pending]
GET  /api/v1/exceptions/{exception_id}
POST /api/v1/exceptions/{exception_id}/approve   -> posts the journal
POST /api/v1/exceptions/{exception_id}/reject
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status

from invoice_agent.hitl.models import ApproveRequest, ExceptionItem, ExceptionStatus, RejectRequest
from invoice_agent.hitl.service import AlreadyResolvedError, HumanReviewService, NotFoundError

router = APIRouter(tags=["human-review"])


def get_review_service(request: Request) -> HumanReviewService:
    return request.app.state.review_service


@router.get("/exceptions", response_model=list[ExceptionItem], summary="List queued exceptions")
def list_exceptions(
    status_filter: ExceptionStatus | None = Query(default=None, alias="status"),
    service: HumanReviewService = Depends(get_review_service),
) -> list[ExceptionItem]:
    return service.list(status_filter)


@router.get(
    "/exceptions/{exception_id}", response_model=ExceptionItem, summary="Fetch one exception"
)
def get_exception(
    exception_id: str, service: HumanReviewService = Depends(get_review_service)
) -> ExceptionItem:
    try:
        return service.get(exception_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/exceptions/{exception_id}/approve",
    response_model=ExceptionItem,
    summary="Approve an exception (posts the Payment Journal)",
)
def approve_exception(
    exception_id: str,
    body: ApproveRequest = Body(default_factory=ApproveRequest),
    service: HumanReviewService = Depends(get_review_service),
) -> ExceptionItem:
    try:
        return service.approve(exception_id, actor=body.actor, note=body.note)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AlreadyResolvedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/exceptions/{exception_id}/reject",
    response_model=ExceptionItem,
    summary="Reject an exception",
)
def reject_exception(
    exception_id: str,
    body: RejectRequest = Body(default_factory=RejectRequest),
    service: HumanReviewService = Depends(get_review_service),
) -> ExceptionItem:
    try:
        return service.reject(exception_id, actor=body.actor, note=body.note)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AlreadyResolvedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
