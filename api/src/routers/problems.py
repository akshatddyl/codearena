"""
/api/problems — list and view problems.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from .. import db
from ..deps import CurrentUser, get_current_user
from ..models import ProblemDetail, ProblemSummary

router = APIRouter(prefix="/api/problems", tags=["problems"])


@router.get("", response_model=list[ProblemSummary])
async def list_problems(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(get_current_user),
) -> list[ProblemSummary]:
    """List active problems, newest first."""
    rows = await db.fetch_all(
        """
        SELECT id, title, difficulty, time_limit_ms, memory_limit_mb,
               created_at, tags
        FROM problems
        WHERE is_active = TRUE
        ORDER BY id ASC
        LIMIT $1 OFFSET $2
        """,
        limit, offset,
    )
    return [ProblemSummary(**dict(r)) for r in rows]


@router.get("/random")
async def get_random_problem(
    user: CurrentUser = Depends(get_current_user),
):
    """
    Return a random problem ID that the user has not yet solved.
    If they have solved everything, return a completely random one.
    """
    # Find unsolved problems
    row = await db.fetch_one(
        """
        SELECT p.id
        FROM problems p
        WHERE p.is_active = TRUE
          AND NOT EXISTS (
              SELECT 1
              FROM submissions s
              JOIN results r ON r.submission_id = s.id
              WHERE s.user_id = $1
                AND s.problem_id = p.id
                AND r.verdict = 'AC'
          )
        ORDER BY RANDOM()
        LIMIT 1
        """,
        user.id,
    )

    # Fallback: If all problems are solved, pick any random problem
    if not row:
        row = await db.fetch_one(
            "SELECT id FROM problems WHERE is_active = TRUE ORDER BY RANDOM() LIMIT 1"
        )

    if not row:
        raise HTTPException(status_code=404, detail="No problems available")

    return {"id": row["id"]}


@router.get("/{problem_id}", response_model=ProblemDetail)
async def get_problem(
    problem_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> ProblemDetail:
    """Fetch a problem by ID."""
    row = await db.fetch_one(
        """
        SELECT id, title, description, input_format, output_format,
               constraints, difficulty, time_limit_ms, memory_limit_mb,
               created_at, tags
        FROM problems
        WHERE id = $1 AND is_active = TRUE
        """,
        problem_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="problem not found")
    return ProblemDetail(**dict(row))


class HintResponse(BaseModel):
    ordinal: int
    content: str


@router.get("/{problem_id}/hints", response_model=list[HintResponse])
async def get_problem_hints(
    problem_id: int,
    user: CurrentUser = Depends(get_current_user),
):
    """Fetch the hints for a problem, ordered by ordinal."""
    rows = await db.fetch_all(
        """
        SELECT ordinal, content
        FROM problem_hints
        WHERE problem_id = $1
        ORDER BY ordinal ASC
        """,
        problem_id,
    )
    return [dict(r) for r in rows]