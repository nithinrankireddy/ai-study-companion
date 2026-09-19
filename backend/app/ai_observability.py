import time
from sqlalchemy import text


def log_ai_call(
    db,
    project_id,
    user_id,
    feature,
    model,
    started_at,
    response=None,
    status="success",
    error_message=""
):
    try:
        latency_ms = (time.perf_counter() - started_at) * 1000

        prompt_tokens = 0
        output_tokens = 0
        total_tokens = 0

        if response is not None:
            usage = getattr(response, "usage_metadata", None)

            if usage:
                prompt_tokens = int(
                    getattr(usage, "prompt_token_count", 0) or 0
                )

                output_tokens = int(
                    getattr(usage, "candidates_token_count", 0) or 0
                )

                total_tokens = int(
                    getattr(usage, "total_token_count", 0) or 0
                )

        db.execute(
            text("""
                INSERT INTO ai_observability (
                    project_id,
                    user_id,
                    feature,
                    model,
                    status,
                    latency_ms,
                    prompt_tokens,
                    output_tokens,
                    total_tokens,
                    estimated_cost,
                    error_message
                )
                VALUES (
                    :project_id,
                    :user_id,
                    :feature,
                    :model,
                    :status,
                    :latency_ms,
                    :prompt_tokens,
                    :output_tokens,
                    :total_tokens,
                    :estimated_cost,
                    :error_message
                )
            """),
            {
                "project_id": project_id,
                "user_id": str(user_id),
                "feature": feature,
                "model": model,
                "status": status,
                "latency_ms": latency_ms,
                "prompt_tokens": prompt_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "estimated_cost": 0,
                "error_message": error_message[:1000],
            }
        )

        db.commit()

    except Exception as e:
        print("AI observability logging failed:", e)
        db.rollback()