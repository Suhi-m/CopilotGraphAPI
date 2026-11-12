
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from uuid import uuid4

app = FastAPI(title="Copilot Graph API")

# Folder to store generated graphs
OUTPUT_DIR = Path("graphs")
OUTPUT_DIR.mkdir(exist_ok=True)


class GraphRequest(BaseModel):
    title: str
    labels: list[str]
    values: list[float]
    chart_type: str = "bar"


@app.post("/generate-graph")
def generate_graph(request: GraphRequest):

    if not request.labels or len(request.labels) != len(request.values):
        raise HTTPException(
            status_code=400,
            detail="Labels and values must have the same length"
        )

    fig, ax = plt.subplots(figsize=(8, 5))

    if request.chart_type == "line":
        ax.plot(request.labels, request.values, marker="o")
    elif request.chart_type == "bar":
        ax.bar(request.labels, request.values)
    else:
        plt.close(fig)
        raise HTTPException(
            status_code=400,
            detail="Unsupported chart type"
        )

    ax.set_title(request.title)
    ax.set_ylabel("Value")
    fig.tight_layout()

    filename = f"{uuid4().hex}.png"
    filepath = OUTPUT_DIR / filename

    fig.savefig(filepath, format="png", dpi=120)
    plt.close(fig)

    return {
        "status": "success",
        "filename": filename,
        "local_path": str(filepath)
    }


@app.get("/health")
def health():
    return {"status": "healthy"}
