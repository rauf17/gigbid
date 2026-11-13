-- synthetic: true
SELECT
    subscription_id,
    account_id,
    plan_tier,
    mrr_usd,
    started_at,
    ended_at,
    CASE WHEN ended_at IS NULL THEN TRUE ELSE FALSE END AS is_active
FROM {{ ref('stg_stripe_subscriptions') }};
