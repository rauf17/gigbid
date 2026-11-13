-- synthetic: true
WITH monthly_activity AS (
    SELECT
        user_id,
        DATE_TRUNC('month', activity_date) AS activity_month
    FROM {{ ref('stg_user_events') }}
    GROUP BY 1, 2
),
cohort_base AS (
    SELECT
        user_id,
        MIN(activity_month) AS cohort_month
    FROM monthly_activity
    GROUP BY 1
)
SELECT
    cb.cohort_month,
    ma.activity_month,
    COUNT(DISTINCT ma.user_id) AS active_users
FROM cohort_base cb
JOIN monthly_activity ma ON cb.user_id = ma.user_id
GROUP BY 1, 2;
