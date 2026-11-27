"""Helpers for strict validation of URL query parameters."""

from fastapi import HTTPException, Request


def reject_unknown_query_parameters(
    request: Request,
    allowed_parameters: set[str] | frozenset[str] = frozenset(),
) -> None:
    """Reject query parameters that an endpoint does not explicitly support."""
    unknown_parameters = sorted(
        set(request.query_params.keys()) - set(allowed_parameters)
    )
    if unknown_parameters:
        names = ", ".join(unknown_parameters)
        raise HTTPException(
            status_code=422,
            detail=f"Unknown query parameter(s): {names}.",
        )
