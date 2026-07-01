#!/usr/bin/env python

from argparse import ArgumentParser
from flask import Flask, request, jsonify, send_file, send_from_directory, Response, stream_with_context
from flask_cors import CORS
import json
import jwt
from datetime import datetime, timedelta
from functools import wraps
import hashlib
import libpressio as lp
import math
import numpy as np
import netCDF4 as nc
import os
from pathlib import Path
from pprint import pprint
import threading 
import time
from openai import OpenAI
from dotenv import load_dotenv
from collections import deque
from analysis_metrics import METRIC_HANDLERS
import logging
import traceback
import sys

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('server.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# CONSTANTS
DEFAULT_SYSTEM_CONFIG_PROMPT = "You are an expert in lossy compression with deep knowledge of scientific data. Please provide clear and concise answers to all questions. If you are not sure about the answer, please say so. Don't make up answers. Please always reply within 200 words if possible."
LLM_MODEL_NAME = "meta/llama3-70b-instruct"

# Useful paths and create necessary folders for the backend
project_root = Path(__file__).parent.parent.parent
dist_dir = project_root / "dist"
root_dir = Path.home() / ".fzvis"
upload_dir = root_dir / "uploads"
case_study_dir = Path(os.getenv("FZVIS_CASE_STUDY_ROOT", str(root_dir / "case_studies"))).expanduser().resolve()
work_dir = root_dir / "data"
work_dir.mkdir(parents=True, exist_ok=True)
upload_dir.mkdir(parents=True, exist_ok=True)
case_study_dir.mkdir(parents=True, exist_ok=True)
metadata_file = upload_dir / "metadata.json"
case_study_metadata_file = case_study_dir / "metadata.json"
saved_datasets = {}
saved_case_studies = {}
decompressed_data_cache = {}  # Cache for decompressed data
input_data_cache = {}     # Cache for analysis datasets indexed by client-provided keys


def _slugify_name(name):
    safe = ''.join(ch if ch.isalnum() or ch in ('-', '_') else '-' for ch in str(name or '').strip())
    safe = '-'.join(filter(None, safe.split('-')))
    return safe or f"case-study-{int(time.time())}"


def _sanitize_relative_path(relative_path):
    rel = Path(relative_path)
    parts = []
    for part in rel.parts:
        if part in ('', '.'):
            continue
        if part == '..':
            raise ValueError("Invalid relative path")
        parts.append(part)
    if not parts:
        raise ValueError("Empty relative path")
    return Path(*parts)


def _read_json_file(file_path):
    with open(file_path, 'r') as handle:
        return json.load(handle)


def _persist_case_studies():
    with open(case_study_metadata_file, 'w') as handle:
        json.dump(saved_case_studies, handle, indent=4)


def _get_case_study_entry(study_id):
    study = saved_case_studies.get(study_id)
    if not study:
        raise FileNotFoundError(f"Case study '{study_id}' not found")
    return study


def _get_case_study_root(study_id):
    study = _get_case_study_entry(study_id)
    root_name = study.get("root") or study_id
    root_path = Path(root_name).expanduser()
    if not root_path.is_absolute():
        root_path = case_study_dir / root_path
    return root_path.resolve()


def _resolve_case_study_path(study_id, relative_path):
    study_root = _get_case_study_root(study_id)
    safe_rel = _sanitize_relative_path(relative_path)
    target = (study_root / safe_rel).resolve()
    if target != study_root and study_root not in target.parents:
        raise ValueError("Invalid case study path")
    return target


def _load_case_study_manifest(study_id):
    study = _get_case_study_entry(study_id)
    manifest_path = _resolve_case_study_path(study_id, study.get("manifest", "manifest.json"))
    return _read_json_file(manifest_path)


def _get_case_study_run(manifest, run_id):
    for run in manifest.get("runs", []):
        if run.get("id") == run_id:
            return run
    raise FileNotFoundError(f"Run '{run_id}' not found")


def _build_case_study_summary(study_id, manifest, display_name=None):
    run_ids = [run.get("id") for run in manifest.get("runs", []) if run.get("id")]
    return {
        "id": study_id,
        "name": display_name or study_id,
        "root": study_id,
        "manifest": "manifest.json",
        "dataset": manifest.get("dataset"),
        "data_type": manifest.get("data_type"),
        "dims": manifest.get("dims", []),
        "run_ids": run_ids,
        "run_count": len(run_ids),
        "registered_at": datetime.utcnow().isoformat() + 'Z',
    }

def _resolve_case_study_local_path(local_path):
    requested = Path(local_path).expanduser()
    if not requested.is_absolute():
        requested = case_study_dir / requested
    resolved = requested.resolve()
    if resolved != case_study_dir and case_study_dir not in resolved.parents:
        raise ValueError(f"Case study path must be inside {case_study_dir}")
    return resolved


def _register_case_study_path(local_path, display_name=None, persist=True):
    study_root = _resolve_case_study_local_path(local_path)
    if not study_root.exists() or not study_root.is_dir():
        raise FileNotFoundError(f"Case study folder not found: {study_root}")

    manifest_path = (study_root / "manifest.json").resolve()
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.json not found in {study_root}")
    if manifest_path.parent != study_root:
        raise ValueError("manifest.json must be directly inside the case study folder")

    manifest = _read_json_file(manifest_path)
    study_id = _slugify_name(display_name or study_root.name)
    summary = _build_case_study_summary(study_id, manifest, display_name or study_root.name)
    summary["root"] = str(study_root)
    summary["manifest"] = "manifest.json"
    summary["source"] = "server_path"

    saved_case_studies[study_id] = summary
    if persist:
        _persist_case_studies()
    return summary, manifest

def _parse_run_ids_param():
    run_ids = request.args.getlist("runId") or request.args.getlist("runIds")
    if not run_ids:
        raw = (request.args.get("runIds") or '').strip()
        if raw:
            run_ids = [part.strip() for part in raw.split(',') if part.strip()]
    # If getlist returned a single element with commas, split it
    elif len(run_ids) == 1 and ',' in run_ids[0]:
        run_ids = [part.strip() for part in run_ids[0].split(',') if part.strip()]
    return run_ids


def _get_case_study_artifact_dtype(manifest, artifact_name):
    if artifact_name in ("predictions", "residuals", "reconstructed"):
        data_type = str(manifest.get("data_type", "float")).lower()
        if data_type == "double":
            return np.dtype(np.float64)
        return np.dtype(np.float32)
    if artifact_name == "quant_indices":
        return np.dtype(np.int32)
    if artifact_name == "fallback_mask":
        return np.dtype(np.uint8)
    raise ValueError(f"Unsupported artifact '{artifact_name}'")


def _load_case_study_artifact_array(study_id, run_id, artifact_name, manifest=None):
    manifest = manifest or _load_case_study_manifest(study_id)
    run = _get_case_study_run(manifest, run_id)
    artifact_rel = (run.get("artifacts") or {}).get(artifact_name)
    if not artifact_rel:
        raise FileNotFoundError(f"Artifact '{artifact_name}' not found for run '{run_id}'")
    artifact_path = _resolve_case_study_path(study_id, artifact_rel)
    dtype = _get_case_study_artifact_dtype(manifest, artifact_name)
    return np.fromfile(artifact_path, dtype=dtype)


def _sample_array(arr, max_points=120000):
    if arr is None:
        return np.array([], dtype=np.float64)
    arr = np.asarray(arr)
    if arr.size <= max_points:
        return arr
    step = max(1, int(math.ceil(arr.size / max_points)))
    return arr[::step]


def _safe_quantile(values, q):
    values = np.asarray(values)
    if values.size == 0:
        return None
    return float(np.quantile(values, q))


def _build_histogram_series(values, bins=80, hist_range=None, density=True):
    values = np.asarray(values)
    if values.size == 0:
        return {"x": [], "y": []}
    counts, edges = np.histogram(values, bins=bins, range=hist_range, density=density)
    centers = (edges[:-1] + edges[1:]) / 2.0
    return {"x": centers.tolist(), "y": counts.tolist()}


def _build_cdf_series(values, max_points=2000):
    values = np.asarray(values)
    if values.size == 0:
        return {"x": [], "y": []}
    sorted_vals = np.sort(values)
    if sorted_vals.size > max_points:
        step = max(1, int(math.ceil(sorted_vals.size / max_points)))
        sorted_vals = sorted_vals[::step]
    y = np.arange(1, sorted_vals.size + 1, dtype=np.float64) / float(sorted_vals.size)
    return {"x": sorted_vals.tolist(), "y": y.tolist()}


def _compute_quant_category_shares(quant_indices, quantbin_count):
    quant_indices = np.asarray(quant_indices)
    total = int(quant_indices.size) or 1
    radius = int(quantbin_count) // 2
    unpred_mask = quant_indices == 0
    mags = np.abs(quant_indices[~unpred_mask].astype(np.int64) - radius)
    return {
        "unpred": float(np.count_nonzero(unpred_mask) / total),
        "small": float(np.count_nonzero((mags >= 1) & (mags <= 2)) / total),
        "medium": float(np.count_nonzero((mags >= 3) & (mags <= 16)) / total),
        "large": float(np.count_nonzero(mags > 16) / total),
    }


def _compute_quant_magnitudes(quant_indices, quantbin_count, exclude_zero=True, max_points=120000):
    sampled = _sample_array(quant_indices, max_points=max_points).astype(np.int64, copy=False)
    radius = int(quantbin_count) // 2
    if exclude_zero:
        sampled = sampled[sampled != 0]
    if sampled.size == 0:
        return np.array([], dtype=np.float64)
    return np.abs(sampled - radius).astype(np.float64, copy=False)


def _reshape_case_study_slice(values, dims, slice_index):
    dims = [int(d) for d in dims]
    if not dims:
        return []
    if len(dims) == 1:
        return np.asarray(values).tolist()
    rows = dims[-2]
    cols = dims[-1]
    values = np.asarray(values)
    if len(dims) == 2:
        trimmed = values[:rows * cols]
        return trimmed.reshape(rows, cols).tolist()
    slice_size = rows * cols
    total_slices = max(1, values.size // slice_size)
    idx = min(max(0, int(slice_index)), total_slices - 1)
    start = idx * slice_size
    trimmed = values[start:start + slice_size]
    if trimmed.size < slice_size:
        padded = np.zeros(slice_size, dtype=trimmed.dtype)
        padded[:trimmed.size] = trimmed
        trimmed = padded
    return trimmed.reshape(rows, cols).tolist()


def _compute_pairwise_delta_summary(study_id, manifest, run_a, run_b):
    metrics_a = _read_json_file(_resolve_case_study_path(study_id, _get_case_study_run(manifest, run_a).get("metrics")))
    metrics_b = _read_json_file(_resolve_case_study_path(study_id, _get_case_study_run(manifest, run_b).get("metrics")))
    residual_a = np.abs(_sample_array(_load_case_study_artifact_array(study_id, run_a, "residuals", manifest), 100000))
    residual_b = np.abs(_sample_array(_load_case_study_artifact_array(study_id, run_b, "residuals", manifest), 100000))
    quant_a = _load_case_study_artifact_array(study_id, run_a, "quant_indices", manifest)
    quant_b = _load_case_study_artifact_array(study_id, run_b, "quant_indices", manifest)
    shares_a = _compute_quant_category_shares(quant_a, manifest.get("fixed_modules", {}).get("quantbin_count", 0))
    shares_b = _compute_quant_category_shares(quant_b, manifest.get("fixed_modules", {}).get("quantbin_count", 0))
    return {
        "run_a": run_a,
        "run_b": run_b,
        "delta_compression_ratio": float(metrics_b.get("compression_ratio", 0) - metrics_a.get("compression_ratio", 0)),
        "delta_p95_abs_residual": (_safe_quantile(residual_b, 0.95) or 0.0) - (_safe_quantile(residual_a, 0.95) or 0.0),
        "delta_p99_abs_residual": (_safe_quantile(residual_b, 0.99) or 0.0) - (_safe_quantile(residual_a, 0.99) or 0.0),
        "delta_medium_share": float(shares_b["medium"] - shares_a["medium"]),
        "delta_large_share": float(shares_b["large"] - shares_a["large"]),
        "delta_prediction_time": float(metrics_b.get("stage_time_seconds", {}).get("prediction", 0) - metrics_a.get("stage_time_seconds", {}).get("prediction", 0)),
    }


def _clean_data_array(data_array, operation_name="data processing"):
    """
    Clean a numpy array by replacing NaN/inf with finite values.
    
    Args:
        data_array: The numpy array to clean
        operation_name: Description of the operation for logging purposes
        
    Returns:
        Cleaned numpy array (copy of original with NaN/inf replaced by 0.0)
    """
    arr_data = data_array.copy()
    
    if not np.isfinite(arr_data).all():
        num_invalid = (~np.isfinite(arr_data)).sum()
        logger.warning(f"Found {num_invalid} NaN/inf values in {operation_name}, replacing with 0.0")
        arr_data = np.nan_to_num(arr_data, nan=0.0, posinf=0.0, neginf=0.0)
    
    return arr_data

def _get_data_from_any_cache(data_key):
    if not data_key:
        return None
    data = input_data_cache.get(data_key)
    if data is None:
        data = decompressed_data_cache.get(data_key)
    return data

def _precision_to_dtype(precision, endianness='little'):
    prec = (precision or '').lower()
    if prec in ('d', 'double', 'float64', 'f64'):
        dtype = np.dtype(np.float64)
    elif prec in ('f', 'float32', 'f32', ''):
        dtype = np.dtype(np.float32)
    elif prec in ('i8', 'int8'):
        dtype = np.dtype(np.int8)
    elif prec in ('u8', 'uint8'):
        dtype = np.dtype(np.uint8)
    elif prec in ('i16', 'int16'):
        dtype = np.dtype(np.int16)
    elif prec in ('u16', 'uint16'):
        dtype = np.dtype(np.uint16)
    elif prec in ('i32', 'int32'):
        dtype = np.dtype(np.int32)
    elif prec in ('u32', 'uint32'):
        dtype = np.dtype(np.uint32)
    else:
        raise ValueError(f"Unsupported precision '{precision}'")

    if dtype.itemsize > 1:
        end = (endianness or 'little').lower()
        if end in ('big', 'be', '>'):
            dtype = dtype.newbyteorder('>')
        elif end in ('little', 'le', '<', 'native', ''):
            dtype = dtype.newbyteorder('<')
    return dtype

# Get the file size in a human readable format
def _get_human_readable_size(filepath): 
    if os.path.isfile(filepath):
        fileSize = os.path.getsize(filepath)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
            if fileSize < 1024.0:
                return f"{fileSize:.2f} {unit}"
            fileSize /= 1024.0

# Read NetCDF file
def _read_netcdf_file(filename, variable, sliceParams=None):
    filePath = upload_dir / filename
    with nc.Dataset(filePath) as dataSet:
        if variable == "metadata":
            return {
                varName: {
                    "shape": dataSet.variables[varName].shape,
                    "dimensions": dataSet.variables[varName].dimensions,
                    "dtype": str(dataSet.variables[varName].dtype),
                }
                for varName in dataSet.variables
            }
        elif variable == "all":
            varData = {}
            for varName in dataSet.variables:
                netCdfVar = dataSet.variables[varName]
                data = np.nan_to_num(netCdfVar[:], nan=0)
                varData[varName] = data.flatten().tolist()
            return varData
        else:
            varObj = dataSet.variables[variable]
            varData = varObj[:]
            dimNames = varObj.dimensions
            print(variable, "dimensions:", dimNames)
            if sliceParams:
                slices = []
                for dimSlice in sliceParams:
                    sl = slice(
                        dimSlice.get("start", 0),
                        dimSlice.get("end", None),
                        dimSlice.get("step", 1)
                    )
                    slices.append(sl)
                varData = varData[tuple(slices)]
            # Normalize to time-first ordering if a time dimension exists
            try:
                timeIdx = next((i for i, d in enumerate(dimNames) if str(d).lower() == "time"), -1)
                if timeIdx > 0 and varData.ndim >= 3:
                    varData = np.moveaxis(varData, timeIdx, 0)
            except Exception as _e:
                pass
            print("nan locations:", np.where(np.isnan(varData)))
            return varData


# Create Large Language Model (LLM) client
# You can request a free API key from NVIDIA at
# https://build.nvidia.com/models
client = OpenAI(
    base_url = "https://integrate.api.nvidia.com/v1",
    api_key = os.environ.get("NVIDIA_API_KEY", ""),
)
conversation_history = [{"role": "system", "content": DEFAULT_SYSTEM_CONFIG_PROMPT}]

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')
CORS(app)


def is_passcode_auth_enabled():
    return bool((os.getenv('FLASK_PASSCODE') or '').strip())


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_passcode_auth_enabled():
            return f(*args, **kwargs)

        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]
        
        if not token:
            print(f"Auth failed: Token missing for {request.path}")
            return jsonify({'error': 'Token is missing!'}), 401
        
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        except Exception as e:
            print(f"Auth failed: Token invalid for {request.path}: {e}")
            return jsonify({'error': 'Token is invalid!'}), 401
        
        return f(*args, **kwargs)
    return decorated


# Global error handlers to prevent server crashes
@app.errorhandler(404)
def not_found_error(error):
    logger.warning(f"404 error: {request.url}")
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 error: {error}")
    logger.error(traceback.format_exc())
    return jsonify({"error": "Internal server error", "message": str(error)}), 500

@app.errorhandler(Exception)
def handle_unexpected_error(error):
    logger.error(f"Unexpected error: {error}")
    logger.error(traceback.format_exc())
    return jsonify({"error": "An unexpected error occurred", "message": str(error)}), 500

@app.route("/api/auth-status", methods=["GET"])
def auth_status():
    return jsonify({"passcodeRequired": is_passcode_auth_enabled()}), 200

@app.route("/api/login", methods=["POST"])
def login():
    if not is_passcode_auth_enabled():
        token = jwt.encode({
            'exp': datetime.utcnow() + timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm="HS256")
        return jsonify({'token': token})

    data = request.get_json(silent=True) or {}
    passcode = data.get('passcode')
    if passcode == os.getenv('FLASK_PASSCODE'):
        token = jwt.encode({
            'exp': datetime.utcnow() + timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm="HS256")
        return jsonify({'token': token})
    return jsonify({'error': 'Invalid passcode'}), 401


@app.route("/api/verify", methods=["GET"])
@token_required
def verify_token():
    return jsonify({'message': 'Token is valid'}), 200


# Route to get the list of uploaded datasets
@app.route("/api/listDatasets", methods=["GET", "POST"])
@token_required
def get_uploaded_datasets():
    return jsonify({"datasets" : saved_datasets}), 200


# Route to send the file back to the front end
@app.route("/api/download", methods=["GET", "POST"])
@token_required
def send_data_file(): 
    fileName = request.args.get("filename")
    fileType = request.args.get("filetype")

    # Check if the file exists first
    filePath = upload_dir / fileName
    if not filePath.exists():
        return jsonify({"error": "File not found"}), 404
    
    # Handle different file types
    if fileType == "raw":
        return send_file(filePath, as_attachment=False)
    elif fileType == "netcdf":
        variable = request.args.get("variable")
        slices = request.args.get("slices")
        sliceParams = json.loads(slices) if slices else None
        varData = _read_netcdf_file(fileName, variable, sliceParams)
        # Send the array as bytes
        return Response(varData.tobytes(), mimetype="application/octet-stream")


# Route to handle file upload
@app.route("/api/upload", methods=["POST"])
@token_required
def upload_file():
    try:
        result = {}
        datasetMetadata = {}
        readDataFile = False
        filePath = ""
        # Uploading a new dataset 
        if "file" in request.files: 
            uploadedFile = request.files["file"]
            if uploadedFile.filename == "":
                return jsonify({"error" : "No file selected"}), 400

            # Save file
            fileName = uploadedFile.filename
            filePath = upload_dir / fileName
            uploadedFile.save(filePath)

            # Use the filename as the key for now as we don't allow two duplicate files
            datasetMetadata["name"] = fileName
            datasetMetadata["size"] = _get_human_readable_size(filePath)
            readDataFile = True
            
        # Updating an existing dataset
        elif request.form.get("filename"):
            fileName = request.form.get("filename")
            datasetMetadata = saved_datasets[fileName]

        # Handle different file types
        fileType = request.form.get("type")
        datasetMetadata["type"] = fileType

        if fileType == "netcdf":
            if readDataFile:
                dataSet = nc.Dataset(filePath)
                variableKeys = dataSet.variables.keys()
                datasetMetadata["vars"] = _read_netcdf_file(datasetMetadata["name"], "metadata")
        
        elif fileType == "raw":
            datasetMetadata["width"] = request.form.get("width")
            datasetMetadata["height"] = request.form.get("height")
            datasetMetadata["depth"] = request.form.get("depth")
            datasetMetadata["precision"] = request.form.get("precision")
            datasetMetadata["endianness"] = request.form.get("endianness", "little")

        # Save metadata to a json file
        saved_datasets[fileName] = datasetMetadata
        result["dataset"] = datasetMetadata
        with open(metadata_file, 'w') as f:
            json.dump(saved_datasets, f, indent=4)
        return jsonify(result), 200
        
    except Exception as e:
        print("Error in upload_file():", e)
        return jsonify({"error" : str(e)}), 500


# Route to handle datasets update
@app.route("/api/updateDatasets", methods=["POST"])
@token_required
def update_datasets():
    try:
        # Update the currently working dataset
        if request.form.get("currentDataset"):
            currentDataset = json.loads(request.form["currentDataset"])
            # print("currentDataset:", currentDataset)

        # Remove the files if deleted datasets are provided
        if request.form.get("deletedDatasets"):
            deletedDatasets = json.loads(request.form["deletedDatasets"])
            print("deletedDatasets: ", deletedDatasets)
            for d in deletedDatasets:
                filePath = upload_dir / saved_datasets[d].get("name")
                if os.path.isfile(filePath):
                    os.remove(filePath)
                saved_datasets.pop(d)
            # Update the metadata file
            with open(metadata_file, 'w') as f:
                json.dump(saved_datasets, f, indent=4)
        return jsonify({"datasets" : saved_datasets}), 200

    except Exception as e:
        print(e)
        return jsonify({"error" : str(e)}), 500


@app.route("/api/caseStudies", methods=["GET"])
@token_required
def list_case_studies():
    return jsonify({"case_studies": saved_case_studies, "base_dir": str(case_study_dir)}), 200


@app.route("/api/caseStudy/availablePaths", methods=["GET"])
@token_required
def list_available_case_study_paths():
    """List all valid case study directories in the base directory"""
    try:
        available = []
        if case_study_dir.exists() and case_study_dir.is_dir():
            for item in sorted(case_study_dir.iterdir()):
                if item.is_dir():
                    manifest_path = item / "manifest.json"
                    if manifest_path.exists():
                        rel_path = item.relative_to(case_study_dir)
                        available.append(str(rel_path))
        return jsonify({"available_paths": available, "base_dir": str(case_study_dir)}), 200
    except Exception as e:
        logger.error(f"Error listing available case studies: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/caseStudy/upload", methods=["POST"])
@token_required
def upload_case_study():
    try:
        uploaded_files = request.files.getlist("files")
        relative_paths = request.form.getlist("relative_paths")
        requested_name = (request.form.get("study_name") or '').strip()

        if not uploaded_files:
            return jsonify({"error": "No case-study files uploaded"}), 400
        if relative_paths and len(relative_paths) != len(uploaded_files):
            return jsonify({"error": "Relative path count does not match uploaded files"}), 400

        inferred_root = None
        if relative_paths:
            first_rel = Path(relative_paths[0])
            if len(first_rel.parts) > 1:
                inferred_root = first_rel.parts[0]

        study_id = _slugify_name(requested_name or inferred_root or Path(uploaded_files[0].filename).stem)
        study_root = (case_study_dir / study_id).resolve()
        study_root.mkdir(parents=True, exist_ok=True)

        saved_manifest_rel = None
        file_count = 0
        for index, uploaded_file in enumerate(uploaded_files):
            rel_path = relative_paths[index] if index < len(relative_paths) else uploaded_file.filename
            safe_rel = _sanitize_relative_path(rel_path)
            parts = list(safe_rel.parts)
            if inferred_root and parts and parts[0] == inferred_root:
                parts = parts[1:]
            if not parts:
                continue
            target_rel = Path(*parts)
            target_path = (study_root / target_rel).resolve()
            if target_path != study_root and study_root not in target_path.parents:
                raise ValueError("Invalid upload path")
            target_path.parent.mkdir(parents=True, exist_ok=True)
            uploaded_file.save(target_path)
            file_count += 1
            if target_rel.name == "manifest.json":
                saved_manifest_rel = str(target_rel)

        if not saved_manifest_rel:
            manifest_candidate = study_root / "manifest.json"
            if manifest_candidate.exists():
                saved_manifest_rel = "manifest.json"
        if not saved_manifest_rel:
            raise FileNotFoundError("manifest.json not found in uploaded case-study folder")

        manifest = _read_json_file(study_root / saved_manifest_rel)
        summary = _build_case_study_summary(study_id, manifest, requested_name or inferred_root or study_id)
        summary["root"] = study_id
        summary["manifest"] = saved_manifest_rel
        summary["file_count"] = file_count
        summary["source"] = "upload"
        saved_case_studies[study_id] = summary
        _persist_case_studies()
        return jsonify({"case_study": summary, "manifest": manifest}), 200
    except Exception as e:
        logger.error(f"Error in upload_case_study(): {e}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route("/api/caseStudy/register", methods=["POST"])
@token_required
def register_case_study():
    try:
        payload = request.get_json(silent=True) or {}
        local_path = (payload.get("path") or '').strip()
        display_name = (payload.get("study_name") or '').strip()
        if not local_path:
            return jsonify({"error": "path is required"}), 400

        summary, manifest = _register_case_study_path(local_path, display_name or None, persist=True)
        return jsonify({
            "case_study": summary,
            "manifest": manifest,
            "base_dir": str(case_study_dir),
        }), 200
    except Exception as e:
        logger.error(f"Error in register_case_study(): {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/caseStudy/manifest", methods=["GET"])
@token_required
def get_case_study_manifest():
    try:
        study_id = request.args.get("studyId")
        if not study_id:
            return jsonify({"error": "studyId is required"}), 400
        manifest = _load_case_study_manifest(study_id)
        summary = _get_case_study_entry(study_id)
        return jsonify({"case_study": summary, "manifest": manifest}), 200
    except Exception as e:
        logger.error(f"Error in get_case_study_manifest(): {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/caseStudy/metrics", methods=["GET"])
@token_required
def get_case_study_metrics():
    try:
        study_id = request.args.get("studyId")
        run_id = request.args.get("runId")
        if not study_id or not run_id:
            return jsonify({"error": "studyId and runId are required"}), 400
        manifest = _load_case_study_manifest(study_id)
        run = _get_case_study_run(manifest, run_id)
        metrics_rel = run.get("metrics")
        if not metrics_rel:
            return jsonify({"error": f"Metrics path missing for run '{run_id}'"}), 404
        metrics = _read_json_file(_resolve_case_study_path(study_id, metrics_rel))
        return jsonify({"run": run, "metrics": metrics}), 200
    except Exception as e:
        logger.error(f"Error in get_case_study_metrics(): {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/caseStudy/residualSummary", methods=["GET"])
@token_required
def get_case_study_residual_summary():
    try:
        study_id = request.args.get("studyId")
        run_ids = _parse_run_ids_param()
        if not study_id or not run_ids:
            return jsonify({"error": "studyId and runIds are required"}), 400
        manifest = _load_case_study_manifest(study_id)
        abs_error_bound = float(manifest.get("fixed_modules", {}).get("abs_error_bound", 0) or 0)
        clip_multiplier = float(request.args.get("clipMultiplier", 20) or 20)
        mode = (request.args.get("mode") or "signed").strip().lower()
        bins = int(request.args.get("bins", 80) or 80)
        density = (request.args.get("histnorm") or "probability density").strip().lower() == "probability density"
        hist_range = None
        if abs_error_bound > 0:
            clip_value = abs_error_bound * max(1.0, clip_multiplier)
            hist_range = (0.0, clip_value) if mode == "absolute" else (-clip_value, clip_value)
        summaries = {}
        for run_id in run_ids:
            residuals = _sample_array(_load_case_study_artifact_array(study_id, run_id, "residuals", manifest), 120000).astype(np.float64, copy=False)
            hist_values = np.abs(residuals) if mode == "absolute" else residuals
            if hist_range is not None:
                hist_values = hist_values[(hist_values >= hist_range[0]) & (hist_values <= hist_range[1])]
            cdf_values = np.abs(residuals)
            summaries[run_id] = {
                "histogram": _build_histogram_series(hist_values, bins=bins, hist_range=hist_range, density=density),
                "cdf": _build_cdf_series(cdf_values, max_points=2000),
            }
        return jsonify({"runs": summaries, "mode": mode, "clip_range": list(hist_range) if hist_range else None}), 200
    except Exception as e:
        logger.error(f"Error in get_case_study_residual_summary(): {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/caseStudy/quantSummary", methods=["GET"])
@token_required
def get_case_study_quant_summary():
    try:
        study_id = request.args.get("studyId")
        run_ids = _parse_run_ids_param()
        if not study_id or not run_ids:
            return jsonify({"error": "studyId and runIds are required"}), 400
        manifest = _load_case_study_manifest(study_id)
        quantbin_count = int(manifest.get("fixed_modules", {}).get("quantbin_count", 0) or 0)
        clip_mode = (request.args.get("clip") or "p99").strip().lower()
        bins = int(request.args.get("bins", 70) or 70)
        sampled = {}
        all_magnitudes = []
        category_shares = {}
        for run_id in run_ids:
            quant_indices = _load_case_study_artifact_array(study_id, run_id, "quant_indices", manifest)
            magnitudes = _compute_quant_magnitudes(quant_indices, quantbin_count, exclude_zero=True, max_points=120000)
            sampled[run_id] = magnitudes
            if magnitudes.size:
                all_magnitudes.append(magnitudes)
            category_shares[run_id] = _compute_quant_category_shares(quant_indices, quantbin_count)
        clip_max = None
        if all_magnitudes and clip_mode == "p99":
            clip_max = float(np.quantile(np.concatenate(all_magnitudes), 0.99))
        summaries = {}
        hist_range = (0.0, clip_max) if clip_max and clip_max > 0 else None
        for run_id, magnitudes in sampled.items():
            hist_values = magnitudes
            if hist_range is not None:
                hist_values = hist_values[hist_values <= hist_range[1]]
            summaries[run_id] = {
                "histogram": _build_histogram_series(hist_values, bins=bins, hist_range=hist_range, density=True),
                "shares": category_shares[run_id],
            }
        return jsonify({"runs": summaries, "clip_mode": clip_mode, "clip_max": clip_max}), 200
    except Exception as e:
        logger.error(f"Error in get_case_study_quant_summary(): {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/caseStudy/spatialSlice", methods=["GET"])
@token_required
def get_case_study_spatial_slice():
    try:
        study_id = request.args.get("studyId")
        run_id = request.args.get("runId")
        compare_run_id = request.args.get("compareRunId")
        mode = (request.args.get("mode") or "absolute").strip().lower()
        slice_index = int(request.args.get("sliceIndex", 0) or 0)
        if not study_id or not run_id:
            return jsonify({"error": "studyId and runId are required"}), 400
        manifest = _load_case_study_manifest(study_id)
        dims = manifest.get("dims", [])
        if mode == "fallback":
            primary = _load_case_study_artifact_array(study_id, run_id, "fallback_mask", manifest).astype(np.float64, copy=False)
            values = primary
        else:
            primary = _load_case_study_artifact_array(study_id, run_id, "residuals", manifest).astype(np.float64, copy=False)
            if mode == "signed":
                values = primary
            elif mode == "delta" and compare_run_id:
                compare = _load_case_study_artifact_array(study_id, compare_run_id, "residuals", manifest).astype(np.float64, copy=False)
                common = min(primary.size, compare.size)
                values = np.abs(compare[:common]) - np.abs(primary[:common])
            else:
                values = np.abs(primary)
        slice_data = _reshape_case_study_slice(values, dims, slice_index)
        return jsonify({"dims": dims, "slice_index": slice_index, "mode": mode, "data": slice_data}), 200
    except Exception as e:
        logger.error(f"Error in get_case_study_spatial_slice(): {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/caseStudy/pairwiseDelta", methods=["GET"])
@token_required
def get_case_study_pairwise_delta():
    try:
        study_id = request.args.get("studyId")
        run_a = request.args.get("runA")
        run_b = request.args.get("runB")
        if not study_id or not run_a or not run_b:
            return jsonify({"error": "studyId, runA, and runB are required"}), 400
        manifest = _load_case_study_manifest(study_id)
        return jsonify(_compute_pairwise_delta_summary(study_id, manifest, run_a, run_b)), 200
    except Exception as e:
        logger.error(f"Error in get_case_study_pairwise_delta(): {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/caseStudy/artifact", methods=["GET"])
@token_required
def get_case_study_artifact():
    try:
        study_id = request.args.get("studyId")
        run_id = request.args.get("runId")
        artifact = request.args.get("artifact")
        if not study_id or not run_id or not artifact:
            return jsonify({"error": "studyId, runId, and artifact are required"}), 400

        manifest = _load_case_study_manifest(study_id)
        run = _get_case_study_run(manifest, run_id)
        artifacts = run.get("artifacts", {})
        artifact_rel = artifacts.get(artifact)
        if not artifact_rel:
            return jsonify({"error": f"Artifact '{artifact}' not found for run '{run_id}'"}), 404

        artifact_path = _resolve_case_study_path(study_id, artifact_rel)
        if not artifact_path.exists():
            return jsonify({"error": f"Artifact file missing: {artifact}"}), 404

        return send_file(artifact_path, mimetype="application/octet-stream", as_attachment=False)
    except Exception as e:
        logger.error(f"Error in get_case_study_artifact(): {e}")
        return jsonify({"error": str(e)}), 500

# Route to get the list of uploaded datasets
@app.route("/api/allCompressors", methods=["GET"])
@token_required
def get_available_compressors():
    try: 
        c = lp.PressioCompressor("pressio", name="pressio")
        compressors = c.get_configuration()["pressio"]["pressio:compressor"]
        compressors.remove("pressio")
        return jsonify({"compressors" : compressors}), 200
    except Exception as e:
        print("Error in get_available_compressors():", e)
        return jsonify({"error": str(e)}), 500

@app.route("/api/decompressed/<data_key>", methods=["GET"])
@token_required
def get_decompressed_data(data_key):
    """Serve decompressed data as binary blob"""
    try:
        data = _get_data_from_any_cache(data_key)
        if data is None:
            return jsonify({"error": "DATA_KEY_NOT_FOUND", "missing_keys": [data_key]}), 404
        
        data_bytes = data.tobytes()
        return Response(data_bytes, mimetype="application/octet-stream")
    except Exception as e:
        print(f"Error in get_decompressed_data(): {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/cache/upload", methods=["POST"])
@token_required
def upload_to_cache():
    """General endpoint to upload binary data to server-side cache"""
    try:
        data_key = request.form.get('data_key')
        metadata = json.loads(request.form.get('metadata', '{}'))
        
        data_file = request.files.get('data')
        if not data_file or not data_key:
            return jsonify({"error": "Missing data file or data_key"}), 400

        # Decode binary into numpy array
        precision = metadata.get('precision', 'f')
        endianness = metadata.get('endianness', 'little')
        dtype = _precision_to_dtype(precision, endianness)
        logger.info(f"upload_to_cache: precision={precision}, dtype={dtype}, metadata={metadata}")
        data_array = np.frombuffer(data_file.read(), dtype=dtype)

        # Reshape according to provided dimensions
        dimensions = metadata.get('dimensions', [])
        if len(dimensions) == 3:
            width, height, depth = map(int, dimensions)
            data_array = data_array.reshape(depth, height, width)
        elif len(dimensions) == 2:
            width, height = map(int, dimensions)
            data_array = data_array.reshape(height, width)

        # Proactively clean data before storing in cache
        data_array = _clean_data_array(data_array, "uploaded data to cache")

        # Store into input_data_cache (general purpose)
        input_data_cache[data_key] = data_array
        
        print(f"Stored uploaded data into cache under key: {data_key}")
        return jsonify({"status": "success", "data_key": data_key}), 200
    except Exception as e:
        print(f"Error in upload_to_cache(): {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/indexlist", methods=["POST"])
@token_required
def indexlist():
    try:
        def describe_compression_error(exc, context=None):
            message = str(exc).strip()
            if not message:
                message = "Compression failed with an empty backend exception. See server console for traceback."
            if context:
                return f"{context}: {message}"
            return message

        option = int(request.form.get("get_options"))
        # Run all submitted compressors and compare the results
        if(option == 0):
            def replace_unsupported_values(obj):
                if isinstance(obj, dict):
                    return {k: replace_unsupported_values(v) for k, v in obj.items()}
                elif obj == math.inf:
                    return "Infinity"
                elif obj == -math.inf:
                    return "-Infinity"
                elif obj is None:
                    return 'null'
                elif isinstance(obj, float) and math.isnan(obj):
                    return 'null'
                else:
                    return obj
            def comparing_compressor(arguments):
                # Expect a dataset cache key and metadata
                dataset_key = arguments.get("data_key")
                meta = arguments.get("dataset_meta") or {}
                
                # Fallback to name if data_key is missing
                if not dataset_key:
                    dataset_key = meta.get("name")
                
                if not dataset_key:
                    raise ValueError("Missing data_key or dataset name for compression request")
                cached = input_data_cache.get(dataset_key)
                if cached is None:
                    return {"error": "DATA_KEY_NOT_FOUND"}
                input_array = cached
                dimensions = meta.get("dimensions")
                precision = meta.get("precision", 'f')
                endianness = meta.get("endianness", 'little')
                if input_array is None and meta.get("name"):
                    filePath = upload_dir / meta["name"]
                    dtype = _precision_to_dtype(precision, endianness)
                    logger.info(f"indexlist: Loading file with precision={precision}, dtype={dtype}, meta={meta}")
                    buffer = np.fromfile(filePath, dtype=dtype)
                    if dimensions and len(dimensions) == 3:
                        width, height, depth = map(int, dimensions)
                        expected = width * height * depth
                        if len(buffer) > expected:
                            buffer = buffer[len(buffer) - expected:]
                        buffer = buffer.reshape(depth, height, width)
                    input_array = _clean_data_array(buffer, "dataset loaded from file")
                    input_data_cache[dataset_key] = input_array
                if input_array is None:
                    return {"error": "Dataset unavailable for compression"}

                # No need to manually construct the configs dictionary, as we expect the full config from the front end
                # configs = {
                #     "compressor_id": arguments["compressor_id"],
                # }
                # if "early_config" in arguments:
                #     configs["early_config"] = {
                #         "pressio:metric": "composite",
                #         "composite:plugins": arguments["early_config"].get("composite:plugins", []),
                #     }
                # configs["compressor_config"] = arguments["compressor_config"]
                # pprint(configs)

                def run_compressor(args, dataset):
                    # Check if the configuration is valid
                    # compressor_config_dict = {
                    #     "compressor_id": args["compressor_id"],
                    #     "compressor_config": args["compressor_config"],
                    # }
                    # if "early_config" in args:
                    #     compressor_config_dict["early_config"] = args["early_config"]
                    # If selected compressor is roibin, ensure roi_size matches dataset shape
                    patched_args = args.copy()
                    try:
                        selectedCompressor = patched_args.get("compressor_id")
                        if selectedCompressor == "pressio":
                            selectedCompressor = (
                                patched_args.get("early_config", {})
                                .get("pressio", {})
                                .get("pressio:compressor")
                            )
                        if selectedCompressor == "roibin" and dataset is not None:
                            # Inject roibin:roi_size under pressio early_config
                            ec = patched_args.setdefault("early_config", {})
                            ec_pressio = ec.setdefault("pressio", {})
                            # Only set if not already provided
                            if "roibin:roi_size" not in ec_pressio:
                                ec_pressio["roibin:roi_size"] = np.asarray(dataset.shape, dtype=np.int32)
                    except Exception as _e:
                        # Fallback to original args if any issue arises
                        patched_args = args
                    
                    logger.info("Compressor config from frontend: %s", json.dumps({
                        "compressor_id": args.get("compressor_id"),
                        "compressor_config": args.get("compressor_config", {}),
                        "early_config": args.get("early_config", {})
                    }, indent=2, sort_keys=True))
                    try:
                        compressor = lp.PressioCompressor.from_config(patched_args)
                        decompData = dataset.copy()
                        compData = compressor.encode(dataset)
                        decompData = compressor.decode(compData, decompData)
                        metrics = compressor.get_metrics()
                    except Exception as exc:
                        compressor_name = args.get("compressor_id") or "unknown compressor"
                        logger.error(
                            "Compression failed for %s with config %s",
                            compressor_name,
                            json.dumps({
                                "compressor_config": args.get("compressor_config", {}),
                                "early_config": args.get("early_config", {})
                            }, indent=2, sort_keys=True)
                        )
                        logger.error(traceback.format_exc())
                        raise RuntimeError(describe_compression_error(exc, f"{compressor_name} compression failed")) from exc
                    metrics1 = replace_unsupported_values(metrics)

                    # Extract error bound and filter out config parameters from metrics
                    compressor_id = args["compressor_id"]
                    compressor_config = args.get("compressor_config", {})

                    # Filter out config parameters (keys ending with _str, _mode, _algo, etc.)
                    # These are configuration values that libpressio includes in metrics but aren't actual metrics
                    config_param_suffixes = ['_str', '_mode', '_algo', '_type', '_method', '_level', '_version', '_bound']
                    config_param_keywords = ['error_bound', 'abs_error', 'rel_error', 'psnr_error', 'accuracy', 'rate', 'precision']

                    filtered_metrics = {}
                    for key, value in metrics1.items():
                        # Keep metric if it doesn't look like a config parameter
                        is_config_suffix = any(key.endswith(suffix) for suffix in config_param_suffixes)
                        is_config_keyword = any(keyword in key for keyword in config_param_keywords)

                        # Check if this key exists in compressor_config (exact match or without prefix)
                        is_in_config = key in compressor_config
                        if not is_in_config and ':' in key:
                            # Check without prefix (e.g., "sz3:abs_error_bound" -> "abs_error_bound")
                            key_without_prefix = key.split(':', 1)[-1]
                            is_in_config = any(key_without_prefix in str(config_key) for config_key in compressor_config.keys())

                        # Filter out if it's a config parameter
                        if not (is_config_suffix or (is_config_keyword and is_in_config)):
                            filtered_metrics[key] = value

                    # Extract and add error bound as a metric
                    error_bound = None
                    if compressor_id == 'sz3':
                        # For SZ3, check error bound mode to determine which bound to use
                        mode = compressor_config.get('sz3:error_bound_mode_str') or compressor_config.get('error_bound_mode_str')
                        if mode == 'ABS' and 'sz3:abs_error_bound' in compressor_config:
                            error_bound = compressor_config.get('sz3:abs_error_bound')
                        elif mode == 'REL' and 'sz3:rel_error_bound' in compressor_config:
                            error_bound = compressor_config.get('sz3:rel_error_bound')
                        elif mode == 'PSNR' and 'sz3:psnr_error_bound' in compressor_config:
                            error_bound = compressor_config.get('sz3:psnr_error_bound')
                        # Fallback: use any available error bound
                        if error_bound is None:
                            error_bound = (compressor_config.get('sz3:abs_error_bound') or
                                         compressor_config.get('sz3:rel_error_bound') or
                                         compressor_config.get('sz3:psnr_error_bound'))
                    elif compressor_id == 'zfp':
                        # For ZFP, use accuracy field
                        error_bound = compressor_config.get('zfp:accuracy')

                    # Add error bound to metrics if found
                    if error_bound is not None:
                        filtered_metrics['error_bound'] = float(error_bound)

                    return {
                        "compressor_id": args["compressor_id"],
                        "compressor_config": args.get("compressor_config", {}),
                        "early_config": args.get("early_config", {}),
                        "metrics": filtered_metrics,
                        "decompressed_data": decompData,  # Return the numpy array
                    }
                result = run_compressor(arguments, input_array)
                # Extract decompressed data and store it in cache
                decompData = result.pop("decompressed_data")
                decompData = _clean_data_array(decompData, "decompressed data from compressor")
                # Generate a unique key for this result
                key = hashlib.md5(f"{arguments.get('compressor_id')}_{time.time()}".encode()).hexdigest()
                result["data_key"] = key
                decompressed_data_cache[key] = decompData
                return result
            
            configurations = json.loads(request.form.get("configurations"))
            # pprint(configurations)
            result = {}
            for name, config in configurations.items():
                if(config["compressor_id"] != ''):
                    output = comparing_compressor(config)
                    if "error" in output:
                        # If it's a cache miss, return 404 so frontend can retry
                        status_code = 404 if output["error"] == "DATA_KEY_NOT_FOUND" else 500
                        return jsonify(output), status_code
                    result[name] = output
                    # print("original data non-zero values:", np.count_nonzero(input_array))
                    # print("decompressed data non-zero values:", np.count_nonzero(output["decp_data"]))
            return jsonify(result), 200
        
        elif option == 1:
            # pprint(lp.PressioCompressor("roibin", {"roibin:roi": "sz3"}).get_configuration())
            compressorId = request.form["compressor_id"]
            compressor = lp.PressioCompressor(compressorId)
            options = compressor.get_configuration()
            doc = compressor.get_documentation()
            highlevel = []
            if "pressio:highlevel" in options:
                highlevel = options["pressio:highlevel"]
            # print("options:", json.dumps(options, indent=4, sort_keys=True))
            moduleSlots = {k: options[k] for k in options if k.startswith(compressorId)}
            # print("highlevel:", highlevel)
            # print("options:", moduleSlots)
            
            return jsonify({"doc": doc, "highlevel" : highlevel, "options" : moduleSlots}), 200 
    
    except Exception as e:
        logger.error("Error in indexlist()")
        logger.error(traceback.format_exc())
        return jsonify({"error": describe_compression_error(e)}), 500

# Route to get progressive configuration options for a compressor
@app.route("/api/progressiveOptions", methods=["POST"])
@token_required
def get_progressive_config():
    try:
        configs = request.get_json() or {}
        
        if not configs:
            return jsonify({"error": "configuration is empty"}), 400
        
        def traverse_config(data, keyFilter=None, stripKey=False, detailed=False, filterNoop=False):
            """
            Function to traverse and extract info from configuration data.
            
            Args:
                data: Configuration dictionary to traverse
                keyFilter: Optional function to filter keys (e.g., lambda x: x == "pressio:highlevel")
                stripKey: If True, strip the matched key from the path
                detailed: If True, return detailed info with slot, options, type for list values
                filterNoop: If True, filter out any keys/paths containing 'noop'
            
            Returns:
                Dictionary mapping paths to values (or detailed info if detailed=True)
            """
            results = {}
            q = deque([(data, "")])
            
            while q:
                node, path = q.popleft()
                if isinstance(node, dict):
                    for k, v in node.items():
                        currPath = f"{path}/{k}" if path else k
                        
                        # Skip if filtering noop and path contains noop
                        if filterNoop and ('noop' in currPath or k == 'noop'):
                            continue
                        
                        # Check if this key matches the filter
                        if keyFilter is None or keyFilter(k):
                            if stripKey:
                                # Strip the trailing key from the path
                                resultKey = currPath.rsplit(f'/{k}', 1)[0] if currPath.endswith(f'/{k}') else currPath
                            else:
                                resultKey = currPath
                            
                            if detailed and isinstance(v, list):
                                filteredList = [item for item in v if not (filterNoop and ('noop' in str(item) or item == 'noop'))] if filterNoop else v
                                if not filteredList and filterNoop:
                                    continue  # Skip empty lists
                                
                                # Return detailed info
                                ptype = 'metric' if 'metric' in k else 'compressor'
                                results[resultKey] = {
                                    'slot': k,
                                    'options': list(dict.fromkeys(filteredList)) if stripKey else filteredList,  # Deduplicate if stripKey
                                    'type': ptype
                                }
                            elif isinstance(v, list):
                                filteredList = [item for item in v if not (filterNoop and ('noop' in str(item) or item == 'noop'))] if filterNoop else v
                                if not filteredList and filterNoop:
                                    continue  # Skip empty lists
                                
                                # Deduplicate if stripKey is True
                                results[resultKey] = list(dict.fromkeys(filteredList)) if stripKey else filteredList
                            elif not detailed:
                                # For non-list values, only include if not in detailed mode
                                results[resultKey] = v
                        
                        # Continue traversal for dict values
                        if isinstance(v, dict):
                            q.append((v, currPath))
            
            return results

        compressor = lp.PressioCompressor.from_config(configs)
        configurationData = compressor.get_configuration()
        # print("Configuration data:")
        # pprint(configurationData)

        doc = compressor.get_documentation()
        
        # Get options with type information
        optionsData = compressor.get_options()
        
        # Extract type information for each option
        def get_option_types(options):
            """Extract type information from pressio options dictionary by inferring from values"""
            type_info = {}
            
            def infer_type(value):
                """Infer the type string from a Python value"""
                if value is None:
                    return 'unset'
                elif isinstance(value, bool):
                    return 'bool'
                elif isinstance(value, int):
                    return 'int'
                elif isinstance(value, float):
                    return 'double'
                elif isinstance(value, str):
                    return 'string'
                elif isinstance(value, (list, tuple)):
                    return 'string_array' if all(isinstance(x, str) for x in value) else 'data'
                elif hasattr(value, 'dtype'):
                    # numpy array
                    dtype_str = str(value.dtype)
                    if 'int8' in dtype_str:
                        return 'int8'
                    elif 'int16' in dtype_str:
                        return 'int16'
                    elif 'int32' in dtype_str:
                        return 'int32'
                    elif 'int64' in dtype_str:
                        return 'int64'
                    elif 'uint8' in dtype_str:
                        return 'uint8'
                    elif 'uint16' in dtype_str:
                        return 'uint16'
                    elif 'uint32' in dtype_str:
                        return 'uint32'
                    elif 'uint64' in dtype_str:
                        return 'uint64'
                    elif 'float32' in dtype_str:
                        return 'float'
                    elif 'float64' in dtype_str:
                        return 'double'
                    else:
                        return 'data'
                else:
                    return 'unknown'
            
            def traverse(obj, path=''):
                """Recursively traverse the options dictionary"""
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        current_path = f"{path}/{key}" if path else key
                        if isinstance(value, dict):
                            # Recurse into nested dictionaries
                            traverse(value, current_path)
                        else:
                            # This is a leaf value, infer its type
                            type_info[key] = infer_type(value)
            
            traverse(options)
            return type_info
        
        optionTypes = get_option_types(optionsData)
        # print("Extracted option types:")
        # pprint(optionTypes)

        allHighlevels = traverse_config(configurationData, keyFilter=lambda x: x=="pressio:highlevel", stripKey=True, filterNoop=True)
        children = traverse_config(configurationData, keyFilter=lambda x: x=="pressio:children", stripKey=True, filterNoop=True)

        # Only keep high-level entries that are exactly one level below pressio (e.g., pressio/roibin)
        def is_top_level(entryPath: str) -> bool:
            return entryPath.startswith("pressio/") and entryPath.count('/') == 1 and not entryPath.endswith('/noop')

        highlevel = {
            path: options
            for path, options in allHighlevels.items()
            if is_top_level(path)
        }

        # Get all option lists with detailed info
        optionLists = traverse_config(configurationData, detailed=True)

        filteredOptionLists = {}
        for k, v in optionLists.items():
            if v['type'] == 'metric':
                # Only keep top-level pressio:metric
                if k.count('/') == 1 and v['slot'] == 'pressio:metric':
                    # Remove 'composite' from the options
                    filtered_options = [opt for opt in v['options'] if opt != 'composite']
                    if filtered_options:
                        filteredOptionLists[k] = {
                            'slot': v['slot'],
                            'options': filtered_options,
                            'type': v['type']
                        }
            else:
                # Keep all non-metric options as-is
                filteredOptionLists[k] = v
        
        optionLists = filteredOptionLists

        # print("highlevel options:")
        # pprint(highlevel)
        # print("children options:")
        # pprint(children)
        # print("Option lists with paths:")
        # pprint(optionLists)

        return jsonify({
            "doc": doc,
            "highlevel": highlevel,
            "children": children,
            "optionLists": optionLists,
            "optionTypes": optionTypes,
        }), 200
    
    except Exception as e:
        print("Error in get_progressive_config():", e)
        return jsonify({"error": str(e)}), 500

# Route to get AI response
@app.route("/api/chat", methods=["POST"])
@token_required
def get_ai_response(): 
    try:
        message = request.form.get("message")
        if not message:
            return jsonify({"error": "No input provided"}), 400
        
        # Create and return streaming completion using conversation history
        conversation_history.append({"role": "user", "content": message})
        response = client.chat.completions.create(
            model=LLM_MODEL_NAME,
            messages=conversation_history,
            temperature=0.6,
            top_p=0.7,
            max_tokens=4096,
            stream=True,
        )

        # Stream the response back to the client
        def generate():
            fullResponse = ""
            for chunk in response:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    reasoning = delta.reasoning_content or ""
                    content = delta.content or ""

                    if content:
                        fullResponse += content
                    
                    payload = {
                        "reasoning_content": reasoning,
                        "content": content
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
            conversation_history.append({"role": "assistant", "content": fullResponse})
            yield "data: [DONE]\n\n"
        
        return Response(
            stream_with_context(generate()), 
            mimetype="text/event-stream")

    except Exception as e:
        print("Error in get_ai_response():", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/analysis/compute", methods=["POST"])
@token_required
def compute_analysis_metric():
    """
    Compute various Quantities of Interest (QoI) metrics on the dataset.
    Accepts binary data, metric type, and parameters.
    """
    try:
        # Get the metric type and parameters
        metric_type = request.form.get('metric_type')
        parameters = json.loads(request.form.get('parameters', '{}'))

        # Fast path: use cached dataset via client-provided key
        data_key = request.form.get('data_key')
        data_array = None
        if data_key:
            data_array = _get_data_from_any_cache(data_key)
            if data_array is None:
                return jsonify({"error": "DATA_KEY_NOT_FOUND", "missing_keys": [data_key]}), 404
            logger.info(f"Using cached data for metric '{metric_type}': shape={data_array.shape}, size={data_array.size}, dtype={data_array.dtype}")
        else:
            # Fallback: read uploaded data file directly
            data_file = request.files.get('data')
            if not data_file:
                return jsonify({"error": "No data file or data_key provided"}), 400

            # Read binary data based on precision
            precision = parameters.get('precision', 'f')
            endianness = parameters.get('endianness', 'little')
            dtype = _precision_to_dtype(precision, endianness)
            data_array = np.frombuffer(data_file.read(), dtype=dtype)

            # Get dimensions and reshape
            dimensions = parameters.get('dimensions', [])
            if len(dimensions) == 3:
                width, height, depth = dimensions
                expected_size = width * height * depth
                if data_array.size != expected_size:
                    logger.error(f"Size mismatch: expected {expected_size} but got {data_array.size}")
                    return jsonify({"error": f"Data size mismatch: expected {expected_size} but got {data_array.size}"}), 400
                data_array = data_array.reshape(depth, height, width)  # (D, H, W)
            elif len(dimensions) == 2:
                width, height = dimensions
                expected_size = width * height
                if data_array.size != expected_size:
                    logger.error(f"Size mismatch: expected {expected_size} but got {data_array.size}")
                    return jsonify({"error": f"Data size mismatch: expected {expected_size} but got {data_array.size}"}), 400
                data_array = data_array.reshape(height, width)
            
            # If a data_key was provided but not found, store the uploaded data now
            if data_key:
                data_array = _clean_data_array(data_array, "uploaded data in analysis compute")
                input_data_cache[data_key] = data_array
                print(f"Stored uploaded data into cache under key: {data_key}")

        # If a comparison key is provided, fetch original data from cache
        comparison_key = parameters.get('comparison_key')
        if comparison_key:
            print(f"Comparison key provided: {comparison_key}")
            original_data = input_data_cache.get(comparison_key)
            if original_data is None:
                original_data = decompressed_data_cache.get(comparison_key)
            
            parameters['original_data'] = original_data
            if original_data is not None:
                print(f"Original data retrieved from cache for comparison.")
            else:
                print(f"Original data NOT found in cache for key: {comparison_key}")

        # Find and run metric handler
        handler = METRIC_HANDLERS.get(metric_type)
        if not handler:
            return jsonify({"error": f"Unknown metric type: {metric_type}"}), 400

        result = handler(data_array, parameters)
        return jsonify({"result": result}), 200
    
    except Exception as e:
        print(f"Error in compute_analysis_metric(): {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# Upload-and-compute fallback: store dataset under client-provided key, then compute
@app.route("/api/analysis/compute/upload", methods=["POST"])
@token_required
def upload_and_compute_metric():
    try:
        metric_type = request.form.get('metric_type')
        parameters = json.loads(request.form.get('parameters', '{}'))
        data_key = request.form.get('data_key')
        if not data_key:
            return jsonify({"error": "Missing data_key"}), 400

        data_file = request.files.get('data')
        if not data_file:
            return jsonify({"error": "No data file provided"}), 400

        # Decode binary into numpy array
        precision = parameters.get('precision', 'f')
        endianness = parameters.get('endianness', 'little')
        dtype = _precision_to_dtype(precision, endianness)
        data_array = np.frombuffer(data_file.read(), dtype=dtype)

        # Reshape according to provided dimensions
        dimensions = parameters.get('dimensions', [])
        if len(dimensions) == 3:
            width, height, depth = dimensions
            data_array = data_array.reshape(depth, height, width)
        elif len(dimensions) == 2:
            width, height = dimensions
            data_array = data_array.reshape(height, width)
        # 1D stays flat

        data_array = _clean_data_array(data_array, "uploaded data in upload_and_compute")

        # Store into cache under key (overwrite allowed)
        input_data_cache[data_key] = data_array

        # Handle comparison key if present
        comparison_key = parameters.get('comparison_key')
        if comparison_key:
            print(f"Comparison key provided in upload: {comparison_key}")
            original_data = input_data_cache.get(comparison_key)
            if original_data is None:
                original_data = decompressed_data_cache.get(comparison_key)
            
            parameters['original_data'] = original_data
            if original_data is not None:
                print(f"Original data retrieved from cache for comparison (upload path).")
            else:
                print(f"Original data NOT found in cache for key (upload path): {comparison_key}")

        handler = METRIC_HANDLERS.get(metric_type)
        if not handler:
            return jsonify({"error": f"Unknown metric type: {metric_type}"}), 400

        result = handler(data_array, parameters)
        return jsonify({"result": result, "data_key": data_key, "stored": True}), 200

    except Exception as e:
        print(f"Error in upload_and_compute_metric(): {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/correction/critical_points", methods=["POST"])
@token_required
def apply_correction():
    try:
        original_key = request.form.get('original_key')
        compressed_key = request.form.get('compressed_key')
        config = json.loads(request.form.get('config', '{}'))
        metadata = json.loads(request.form.get('metadata', '{}'))

        print(f"Correction request received: original_key={original_key}, compressed_key={compressed_key}")
        print(f"Config: {config}")

        if not original_key or not compressed_key:
            print("Error: Missing original_key or compressed_key")
            return jsonify({"error": "Missing original_key or compressed_key"}), 400

        # Retrieve data from cache
        original_data = _get_data_from_any_cache(original_key)
        decompressed_data = _get_data_from_any_cache(compressed_key)

        missing = []
        if original_data is None:
            missing.append(original_key)
        
        if decompressed_data is None:
            missing.append(compressed_key)
        
        if missing:
            return jsonify({"error": "DATA_KEY_NOT_FOUND", "missing_keys": missing}), 404

        # Run correction
        handler = METRIC_HANDLERS.get('critical_points_correction')
        parameters = {
            'config': config,
            'metadata': metadata
        }
        
        result = handler(original_data, decompressed_data, parameters)

        if 'error' in result:
            return jsonify(result), 500

        # Store corrected data in cache
        corrected_data = result.pop('corrected_data')
        corrected_data = _clean_data_array(corrected_data, "corrected data")
        new_key = hashlib.md5(f"corrected_{compressed_key}_{time.time()}".encode()).hexdigest()
        decompressed_data_cache[new_key] = corrected_data
        
        result['data_key'] = new_key
        return jsonify(result), 200

    except Exception as e:
        print(f"Error in apply_correction(): {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/correction/ffcz", methods=["POST"])
@token_required
def apply_ffcz_correction():
    try:
        original_key = request.form.get('original_key')
        compressed_key = request.form.get('compressed_key')
        config = json.loads(request.form.get('config', '{}'))
        metadata = json.loads(request.form.get('metadata', '{}'))

        logger.info(f"FFCz correction request: original_key={original_key}, compressed_key={compressed_key}")
        logger.info(f"FFCz config: {config}")

        if not original_key or not compressed_key:
            return jsonify({"error": "Missing original_key or compressed_key"}), 400

        # Retrieve data from cache
        original_data = _get_data_from_any_cache(original_key)
        decompressed_data = _get_data_from_any_cache(compressed_key)

        missing = []
        if original_data is None:
            missing.append(original_key)
        if decompressed_data is None:
            missing.append(compressed_key)

        if missing:
            return jsonify({"error": "DATA_KEY_NOT_FOUND", "missing_keys": missing}), 404

        # Run FFCz correction sweep
        handler = METRIC_HANDLERS.get('ffcz_correction')
        parameters = {
            'config': config,
            'metadata': metadata
        }

        result = handler(original_data, decompressed_data, parameters)

        if 'error' in result:
            return jsonify(result), 500

        # Cache corrected data for each frequency bound if available
        if result.get('results'):
            logger.info(f"Processing {len(result['results'])} FFCz results")
            for idx, freq_result in enumerate(result['results']):
                freq_bound = freq_result.get('freq_bound', 'unknown')
                if 'corrected_data' in freq_result:
                    corrected_data = freq_result.pop('corrected_data')
                    corrected_changed = freq_result.get('corrected_data_changed')
                    if corrected_changed is False:
                        logger.info(f"[{idx+1}/{len(result['results'])}] Skipping cache for unchanged FFCz corrected data at freq_bound {freq_bound}")
                    else:
                        corrected_data = _clean_data_array(corrected_data, "FFCz corrected data")

                        # Generate unique key for this frequency bound's corrected data
                        new_key = hashlib.md5(f"ffcz_{compressed_key}_{freq_bound}_{time.time()}".encode()).hexdigest()
                        decompressed_data_cache[new_key] = corrected_data

                        freq_result['data_key'] = new_key
                        logger.info(f"[{idx+1}/{len(result['results'])}] Cached FFCz corrected data for freq_bound {freq_bound}: shape={corrected_data.shape}, key={new_key}")
                else:
                    logger.info(f"[{idx+1}/{len(result['results'])}] No corrected data for freq_bound {freq_bound}")

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error in apply_ffcz_correction(): {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# Catch-all route to serve the Vue frontend's index.html
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    fullPath = os.path.join(dist_dir, path)
    if os.path.isfile(fullPath):
        return send_from_directory(dist_dir, path)
    else:
        return send_from_directory(dist_dir, 'index.html')


# Main entry of the server program
if __name__ == '__main__':

    # Parsing command line arguments
    parser = ArgumentParser(description="enter your HOST/POST.", usage="path/to/main.py [OPTIONAL ARGUMENTS] <HOST> <PORT> <configfile>")
    parser.add_argument('--HOST', nargs='?', help='HOST_address', default="0.0.0.0")
    parser.add_argument('--PORT', nargs='?', help='PORT_address', default="10080")
    parser.add_argument('--configfile', nargs='?', help='your_config_file', default=None)
    cmdInput = parser.parse_args()

    if not any(vars(cmdInput).values()):
        parser.print_help()
    apiHost = cmdInput.HOST
    apiPort = cmdInput.PORT
    
    # Read uploaded datasets from the metadata file
    if metadata_file.exists():
        with open(metadata_file, 'r') as f:
            saved_datasets = json.load(f)
    if case_study_metadata_file.exists():
        with open(case_study_metadata_file, 'r') as f:
            saved_case_studies = json.load(f)

    # Run the server with error handling
    try:
        logger.info(f"Starting server on {apiHost}:{apiPort}")
        app.run(host=apiHost, port=apiPort, debug=True, threaded=True)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.critical(f"Critical error starting server: {e}")
        logger.critical(traceback.format_exc())
        sys.exit(1)
