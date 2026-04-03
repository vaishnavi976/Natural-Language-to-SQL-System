from __future__ import annotations
from typing import Any


def _is_numeric(val: Any) -> bool:
    try:
        float(val)
        return True
    except (TypeError, ValueError):
        return False


def generate_chart(
    columns: list[str],
    rows: list[list[Any]],
    question: str = "",
) -> tuple[dict | None, str]:
    """
    Returns (chart_dict, chart_type) or (None, "").
    chart_dict is a Plotly JSON-serialisable {data, layout}.
    """
    if not rows or len(columns) < 2:
        return None, ""

    idx_of = {c: i for i, c in enumerate(columns)}
    numeric_cols = [c for c in columns
                    if all(_is_numeric(r[idx_of[c]]) for r in rows)]
    text_cols    = [c for c in columns if c not in numeric_cols]

    if not numeric_cols:
        return None, ""

    x_col = text_cols[0] if text_cols else columns[0]
    y_col = numeric_cols[0]
    x_idx = idx_of[x_col]
    y_idx = idx_of[y_col]

    x_vals = [str(r[x_idx]) for r in rows]
    y_vals = [float(r[y_idx]) for r in rows]

    q = question.lower()

    # Choose chart type
    if any(w in q for w in ("trend", "monthly", "over time", "by month",
                             "by week", "registration", "time series")):
        chart_type = "line"
        trace = {
            "type": "scatter", "mode": "lines+markers",
            "x": x_vals, "y": y_vals, "name": y_col,
            "line": {"color": "#3B82F6", "width": 2},
        }
    elif len(rows) <= 6 and any(w in q for w in
                                ("breakdown", "distribution", "percentage",
                                 "percent", "share", "proportion", "status")):
        chart_type = "pie"
        trace = {
            "type": "pie", "labels": x_vals, "values": y_vals,
            "hole": 0.35, "textinfo": "label+percent",
        }
    else:
        chart_type = "bar"
        trace = {
            "type": "bar", "x": x_vals, "y": y_vals, "name": y_col,
            "marker": {"color": "#6366F1"},
        }

    layout = {
        "title":         {"text": question[:80] or y_col, "font": {"size": 14}},
        "xaxis":         {"title": x_col, "tickangle": -30},
        "yaxis":         {"title": y_col},
        "margin":        {"l": 60, "r": 20, "t": 60, "b": 80},
        "plot_bgcolor":  "#ffffff",
        "paper_bgcolor": "#ffffff",
    }

    return {"data": [trace], "layout": layout}, chart_type
