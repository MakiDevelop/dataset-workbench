from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Any
import uuid
import os

from src.pipelines.reducer import (
    save_upload_file,
    get_preview,
    get_distinct_values,
    export_filtered_data,
    preview_filtered_query,
)

router = APIRouter(prefix="/api/reduce", tags=["reduce"])

DATA_INPUT_DIR = "data/input"
DATA_OUTPUT_DIR = "data/output"

os.makedirs(DATA_INPUT_DIR, exist_ok=True)
os.makedirs(DATA_OUTPUT_DIR, exist_ok=True)


class FilterRule(BaseModel):
    column: str
    op: str
    value: Any


class ExportRequest(BaseModel):
    format: str  # csv | xlsx
    logic: str = "AND"
    filters: List[FilterRule]


# PreviewQueryRequest for previewing filtered queries
class PreviewQueryRequest(BaseModel):
    logic: str = "AND"
    filters: List[FilterRule]


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    dataset_id = str(uuid.uuid4())
    try:
        saved_path = save_upload_file(file, dataset_id, DATA_INPUT_DIR)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "dataset_id": dataset_id,
        "filename": file.filename,
        "path": saved_path,
    }


@router.get("/{dataset_id}/preview")
def preview_dataset(
    dataset_id: str,
    limit: int = Query(200, ge=10, le=1000),
):
    try:
        result = get_preview(dataset_id, DATA_INPUT_DIR, limit)
        return result
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{dataset_id}/distinct")
def distinct_values(
    dataset_id: str,
    column: str,
    limit: int = Query(200, ge=1, le=1000),
):
    try:
        values = get_distinct_values(dataset_id, DATA_INPUT_DIR, column, limit)
        return {"column": column, "values": values}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Endpoint for previewing filtered query results
@router.post("/{dataset_id}/preview_query")
def preview_query(
    dataset_id: str,
    payload: PreviewQueryRequest,
):
    try:
        result = preview_filtered_query(
            dataset_id=dataset_id,
            input_dir=DATA_INPUT_DIR,
            filters=payload.filters,
            logic=payload.logic,
        )
        return result
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{dataset_id}/export")
def export_dataset(
    dataset_id: str,
    payload: ExportRequest,
):
    try:
        output_path, filename = export_filtered_data(
            dataset_id=dataset_id,
            input_dir=DATA_INPUT_DIR,
            output_dir=DATA_OUTPUT_DIR,
            export_format=payload.format,
            filters=payload.filters,
            logic=payload.logic,
        )

        def file_iterator():
            with open(output_path, "rb") as f:
                yield from f

        media_type = (
            "text/csv"
            if payload.format == "csv"
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        return StreamingResponse(
            file_iterator(),
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            },
        )

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))