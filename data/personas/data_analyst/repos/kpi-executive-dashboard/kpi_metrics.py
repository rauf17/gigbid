# synthetic: true
"""KPI computation functions for net retention and customer acquisition cost."""


def compute_net_dollar_retention(starting_mrr: float, expansion: float, contraction: float, churn: float) -> float:
    if starting_mrr == 0:
        return 0.0
    return ((starting_mrr + expansion - contraction - churn) / starting_mrr) * 100.0
