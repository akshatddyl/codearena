from fastapi import APIRouter, Depends

from .. import db
from ..deps import CurrentUser, get_current_user

router = APIRouter(prefix="/api/activity", tags=["activity"])


@router.get("/")
async def get_global_activity(
    limit: int = 15,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Fetch the most recent public events:
    - Recent Accepted submissions
    - New user registrations
    """
    # 1. Recent ACs
    acs = await db.fetch_all(
        """
        SELECT
            'ac' AS type,
            s.id AS submission_id,
            u.username,
            p.title AS problem_title,
            p.difficulty,
            r.runtime_ms,
            r.graded_at AS created_at
        FROM results r
        JOIN submissions s ON s.id = r.submission_id
        JOIN users u ON u.id = s.user_id
        JOIN problems p ON p.id = s.problem_id
        WHERE r.verdict = 'AC'
        ORDER BY r.graded_at DESC
        LIMIT $1
        """,
        limit,
    )

    # 2. Recent Registrations
    regs = await db.fetch_all(
        """
        SELECT
            'registration' AS type,
            u.username,
            u.created_at
        FROM users u
        ORDER BY u.created_at DESC
        LIMIT $1
        """,
        limit,
    )

    # Combine and sort chronologically
    events = []
    for r in acs:
        events.append(dict(r))
    for r in regs:
        events.append(dict(r))

    events.sort(key=lambda x: x["created_at"], reverse=True)

    # Return top N
    return events[:limit]
