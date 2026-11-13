-- synthetic: true
-- High-level executive gross margin and revenue run rate
SELECT
    DATE_TRUNC('quarter', recorded_at) AS fiscal_quarter,
    SUM(gross_revenue_usd) AS total_revenue,
    SUM(gross_margin_usd) / NULLIF(SUM(gross_revenue_usd), 0) * 100 AS margin_percentage
FROM analytics.fct_daily_revenue
GROUP BY 1
ORDER BY 1 DESC;
