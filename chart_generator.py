from __future__ import annotations
from typing import Any

def generate_chart(columns, rows, question=""):
    if not rows or len(columns) < 2:
        return None, ""

    idx = {c: i for i, c in enumerate(columns)}

    def is_numeric(v):
        try:
            float(v)
            return True
        except:
            return False

    numeric_cols = [c for c in columns if all(is_numeric(r[idx[c]]) for r in rows)]
    text_cols = [c for c in columns if c not in numeric_cols]

    if not numeric_cols:
        return None, ""

    # 🔥 smarter column selection
    x_col = text_cols[0] if text_cols else columns[0]

    # choose best numeric column (max total impact)
    y_col = max(numeric_cols, key=lambda c: sum(float(r[idx[c]]) for r in rows))

    x_vals = [str(r[idx[x_col]]) for r in rows]
    y_vals = [float(r[idx[y_col]]) for r in rows]

    # 🔥 SORT values (important for good charts)
    combined = sorted(zip(x_vals, y_vals), key=lambda x: x[1], reverse=True)
    x_vals, y_vals = zip(*combined)

    q = question.lower()

    base_color = "#6366F1"

    gradient_colors = [
        "#6366F1", "#7C83FD", "#A5B4FC",
        "#C7D2FE", "#E0E7FF"
    ]

    # 📊 Decide chart type
    if any(w in q for w in ("trend", "monthly", "over time")):
        chart_type = "line"

        trace = {
            "type": "scatter",
            "mode": "lines+markers",
            "x": x_vals,
            "y": y_vals,
            "line": {
                "width": 3,
                "shape": "spline",  # smooth curve
                "color": base_color
            },
            "marker": {"size": 7},
        }

    elif len(rows) <= 6:
        chart_type = "pie"

        trace = {
            "type": "pie",
            "labels": x_vals,
            "values": y_vals,
            "hole": 0.45,
            "marker": {"colors": gradient_colors},
            "textinfo": "percent+label",
        }

    else:
        chart_type = "bar"

        trace = {
            "type": "bar",
            "x": x_vals,
            "y": y_vals,
            "marker": {
                "color": y_vals,  # 🔥 dynamic color
                "colorscale": "Blues",
            },
        }

    # 🎨 Modern layout
    layout = {
        "title": {
            "text": question.title(),
            "x": 0.02,
            "font": {"size": 20}
        },
        "xaxis": {
            "title": x_col,
            "tickangle": -30,
            "showgrid": False,
        },
        "yaxis": {
            "title": y_col,
            "gridcolor": "#E5E7EB",
            "zeroline": False,
        },
        "margin": {"l": 50, "r": 20, "t": 60, "b": 80},
        "plot_bgcolor": "#FFFFFF",
        "paper_bgcolor": "#FFFFFF",
        "font": {"family": "Segoe UI", "size": 12},
        "hovermode": "x unified",
    }

    return {"data": [trace], "layout": layout}, chart_type