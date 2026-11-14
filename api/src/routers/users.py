"""
/api/users — public user profiles.
"""

import math
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException

from .. import db
from ..deps import CurrentUser, get_current_user
from ..models import UpdateProfileRequest

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/{username}")
async def get_public_profile(
    username: str,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Return a user's public profile: username, join date, global rank,
    number of solved problems, and total submissions.

    This endpoint is available to any authenticated user (so profiles
    can be viewed by anyone logged in), but returns nothing sensitive
    (no email, no password hash, no source code).
    """
    target = await db.fetch_one(
        """
        SELECT id, username, role, created_at, bio, avatar_url, xp
        FROM users
        WHERE username = $1
        """,
        username,
    )
    if target is None:
        raise HTTPException(status_code=404, detail="user not found")

    # Get follower / following counts
    counts = await db.fetch_one(
        """
        SELECT
            (SELECT COUNT(*) FROM follows WHERE following_id = $1) AS follower_count,
            (SELECT COUNT(*) FROM follows WHERE follower_id = $1) AS following_count
        """,
        target["id"],
    )

    # Check if current user is following this user
    is_following = await db.fetch_val(
        "SELECT EXISTS(SELECT 1 FROM follows WHERE follower_id = $1 AND following_id = $2)",
        user.id,
        target["id"],
    )

    # Aggregate stats from the leaderboard materialized view
    stats = await db.fetch_one(
        """
        SELECT
            COALESCE(SUM(best_score), 0)                       AS total_score,
            COUNT(*) FILTER (WHERE accepted_count > 0)         AS total_solved,
            COALESCE(SUM(total_submissions), 0)                AS total_submissions
        FROM leaderboard
        WHERE user_id = $1
        """,
        target["id"],
    )

    # Compute global rank by counting users with higher scores
    rank_row = await db.fetch_one(
        """
        WITH scores AS (
            SELECT user_id, SUM(best_score) AS total
            FROM leaderboard
            GROUP BY user_id
        )
        SELECT
            COUNT(*) + 1 AS rank
        FROM scores
        WHERE total > COALESCE(
            (SELECT SUM(best_score) FROM leaderboard WHERE user_id = $1),
            0
        )
        """,
        target["id"],
    )

    # Calculate level from XP
    xp = target["xp"]
    level = int(math.isqrt(xp // 100)) + 1

    return {
        "id": target["id"],
        "username": target["username"],
        "role": target["role"],
        "joined_at": target["created_at"],
        "bio": target["bio"],
        "avatar_url": target["avatar_url"],
        "xp": xp,
        "level": level,
        "rank": rank_row["rank"] if rank_row else None,
        "total_score": stats["total_score"],
        "total_solved": stats["total_solved"],
        "total_submissions": stats["total_submissions"],
        "follower_count": counts["follower_count"],
        "following_count": counts["following_count"],
        "is_following": is_following,
    }


@router.put("/me/profile")
async def update_profile(
    req: UpdateProfileRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Update the authenticated user's public bio and avatar URL."""
    provided = req.model_fields_set
    if not provided:
        return {"status": "ok"}

    await db.execute(
        """
        UPDATE users
        SET bio = CASE WHEN $1 THEN $2 ELSE bio END,
            avatar_url = CASE WHEN $3 THEN $4 ELSE avatar_url END
        WHERE id = $5
        """,
        "bio" in provided,
        req.bio,
        "avatar_url" in provided,
        req.avatar_url,
        user.id,
    )
    return {"status": "ok"}


@router.get("/me/topics")
async def get_user_topics(
    user: CurrentUser = Depends(get_current_user),
):
    """
    Calculate how many problems the user has solved per topic tag.
    """
    rows = await db.fetch_all(
        """
        WITH solved_problems AS (
            SELECT DISTINCT s.problem_id
            FROM submissions s
            JOIN results r ON r.submission_id = s.id
            WHERE s.user_id = $1 AND r.verdict = 'AC'
        )
        SELECT
            unnest(p.tags) AS tag,
            COUNT(*) AS solved_count
        FROM problems p
        JOIN solved_problems sp ON sp.problem_id = p.id
        GROUP BY tag
        ORDER BY solved_count DESC
        """,
        user.id,
    )

    # Also get total available problems per tag
    totals = await db.fetch_all(
        """
        SELECT unnest(tags) AS tag, COUNT(*) AS total_count
        FROM problems WHERE is_active = TRUE
        GROUP BY tag
        """
    )
    total_map = {row["tag"]: row["total_count"] for row in totals}

    result = []
    for row in rows:
        tag = row["tag"]
        solved = row["solved_count"]
        total = total_map.get(tag, solved)
        pct = round((solved / total) * 100) if total > 0 else 0
        result.append({
            "tag": tag,
            "solved": solved,
            "total": total,
            "percentage": pct,
        })

    return result


@router.get("/me/recommendations")
async def get_recommendations(
    user: CurrentUser = Depends(get_current_user),
):
    """
    Suggest the next problem based on the user's weakest topic.
    Also returns stats for the current week.
    """
    # 1. Find the user's weakest topic
    weakest_topic_row = await db.fetch_one(
        """
        WITH user_topics AS (
            SELECT unnest(p.tags) AS tag,
                   COUNT(*) FILTER (WHERE r.verdict = 'AC') AS solved
            FROM problems p
            LEFT JOIN submissions s ON s.problem_id = p.id AND s.user_id = $1
            LEFT JOIN results r ON r.submission_id = s.id
            WHERE p.is_active = TRUE
            GROUP BY tag
            HAVING COUNT(*) FILTER (WHERE r.verdict = 'AC') < COUNT(*)
            ORDER BY (COUNT(*) FILTER (WHERE r.verdict = 'AC')::float / COUNT(*)) ASC
            LIMIT 1
        )
        SELECT tag FROM user_topics
        """,
        user.id,
    )

    recommendation = None
    if weakest_topic_row:
        weakest_tag = weakest_topic_row["tag"]
        # Find an unsolved problem in this topic
        recommended_problem = await db.fetch_one(
            """
            SELECT p.id, p.title, p.difficulty
            FROM problems p
            WHERE p.is_active = TRUE
              AND $1 = ANY(p.tags)
              AND p.id NOT IN (
                  SELECT s.problem_id FROM submissions s
                  JOIN results r ON r.submission_id = s.id
                  WHERE s.user_id = $2 AND r.verdict = 'AC'
              )
            ORDER BY RANDOM()
            LIMIT 1
            """,
            weakest_tag, user.id,
        )
        if recommended_problem:
            recommendation = {
                "problem": dict(recommended_problem),
                "reason": f"Improve your {weakest_tag.replace('-', ' ')} skills",
            }

    # 2. Weekly Stats
    week_start = datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())
    weekly_stats = await db.fetch_one(
        """
        SELECT
            COUNT(DISTINCT s.problem_id) FILTER (WHERE r.verdict = 'AC') AS weekly_solved,
            COUNT(s.id) AS weekly_submissions
        FROM submissions s
        LEFT JOIN results r ON r.submission_id = s.id
        WHERE s.user_id = $1 AND s.submitted_at >= $2
        """,
        user.id, week_start,
    )

    return {
        "recommendation": recommendation,
        "weekly_stats": dict(weekly_stats) if weekly_stats else {"weekly_solved": 0, "weekly_submissions": 0},
    }