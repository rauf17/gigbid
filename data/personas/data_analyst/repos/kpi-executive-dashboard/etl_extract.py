# synthetic: true
"""Postgres to data warehouse batch extractor."""
import pandas as pd


def extract_daily_sales(engine, target_date: str) -> pd.DataFrame:
    query = f"""
        SELECT order_id, customer_id, gross_amount, net_margin
        FROM orders
        WHERE order_date = '{target_date}'
    """
    return pd.read_sql(query, engine)
