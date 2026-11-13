
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.responses import Response
from azure.core.exceptions import ResourceNotFoundError, AzureError
from pydantic import BaseModel
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from uuid import uuid4
from io import BytesIO
import os
from datetime import datetime, timezone

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings

STORAGE_ACCOUNT_NAME = os.environ["AZURE_STORAGE_ACCOUNT_NAME"]
BLOB_CONTAINER_NAME = "copilot-graphs"

blob_service_client = BlobServiceClient(
    account_url=f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net",
    credential=DefaultAzureCredential()
)

container_client = blob_service_client.get_container_client(
    BLOB_CONTAINER_NAME
)


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

    chart_type = request.chart_type

    # Generate a unique filename
    current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    unique_id = uuid4().hex[:8]

    filename = f"{current_date}_{chart_type}_{unique_id}.png"

    # Validate input
    if not request.labels or len(request.labels) != len(request.values):
        raise HTTPException(
            status_code=400,
            detail="Labels and values must have the same length"
        )

    # Generate chart
    fig, ax = plt.subplots(figsize=(8, 5))

    try:
        if chart_type == "line":
            ax.plot(request.labels, request.values, marker="o")

        elif chart_type == "bar":
            ax.bar(request.labels, request.values)

        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported chart type"
            )

        ax.set_title(request.title)
        ax.set_ylabel("Value")
        fig.tight_layout()

        # Save PNG in memory
        image_buffer = BytesIO()
        fig.savefig(image_buffer, format="png", dpi=120)
        image_buffer.seek(0)

        # Upload to Azure Blob Storage
        blob_client = container_client.get_blob_client(filename)

        blob_client.upload_blob(
            image_buffer,
            overwrite=False,
            content_settings=ContentSettings(
                content_type="image/png"
            )
        )

    finally:
        plt.close(fig)

    return {
        "status": "success",
        "filename": filename
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/graphs/{filename}")
def get_graph(filename: str):

    # Only allow valid PNG filenames
    if (
        Path(filename).name != filename
        or not filename.endswith(".png")
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid filename"
        )

    try:
        # Access the PNG stored in Azure Blob Storage
        blob_client = container_client.get_blob_client(filename)

        # Download the image from Blob Storage
        image_data = blob_client.download_blob().readall()

        # Return the PNG directly to the browser/Copilot
        return Response(
            content=image_data,
            media_type="image/png",
            headers={
                "Content-Disposition": f'inline; filename="{filename}"'
            }
        )

    except ResourceNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Graph not found"
        )

    except AzureError:
        raise HTTPException(
            status_code=502,
            detail="Unable to retrieve graph from storage"
        )



# @app.get("/graphs/{filename}")
# def get_graph(filename: str):
#     # Only allow PNG filenames
#     if Path(filename).name != filename or not filename.endswith(".png"):
#         raise HTTPException(status_code=400, detail="Invalid filename")

#     file_path = Path("graphs") / filename

#     if not file_path.is_file():
#         raise HTTPException(status_code=404, detail="Graph not found")

#     return FileResponse(
#         path=file_path,
#         media_type="image/png",
#         filename=filename,
#         content_disposition_type="inline"
#     )
