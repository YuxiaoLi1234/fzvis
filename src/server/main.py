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

load_dotenv()

# CONSTANTS
DEFAULT_SYSTEM_CONFIG_PROMPT = "You are an expert in lossy compression with deep knowledge of scientific data. Please provide clear and concise answers to all questions. If you are not sure about the answer, please say so. Don't make up answers. Please always reply within 200 words if possible."
LLM_MODEL_NAME = "deepseek-ai/deepseek-r1-0528"

# Useful paths and create necessary folders for the backend
project_root = Path(__file__).parent.parent.parent
dist_dir = project_root / "dist"
root_dir = Path.home() / ".fzvis"
upload_dir = root_dir / "uploads"
work_dir = root_dir / "data"
work_dir.mkdir(parents=True, exist_ok=True)
upload_dir.mkdir(parents=True, exist_ok=True)
metadata_file = upload_dir / "metadata.json"
saved_datasets = {}
decompressed_data_cache = {}  # Cache for decompressed data
input_data_cache = {}     # Cache for analysis datasets indexed by client-provided keys

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

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]
        if not token:
            return jsonify({'error': 'Token is missing!'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        except:
            return jsonify({'error': 'Token is invalid!'}), 401
        return f(*args, **kwargs)
    return decorated

# Get the file size in a human readable format
def get_human_readable_size(filepath): 
    if os.path.isfile(filepath):
        fileSize = os.path.getsize(filepath)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
            if fileSize < 1024.0:
                return f"{fileSize:.2f} {unit}"
            fileSize /= 1024.0


# Read NetCDF file
def read_netcdf_file(filename, variable, sliceParams=None):
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
            varData = dataSet.variables[variable][:]
            print(variable,"dimensions:", dataSet.variables[variable].dimensions)
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
            print("nan locations:", np.where(np.isnan(varData)))
            return varData


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    passcode = data.get('passcode')
    if passcode == os.getenv('FLASK_PASSCODE', 'default_passcode'):
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
        varData = read_netcdf_file(fileName, variable, sliceParams)
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
            datasetMetadata["size"] = get_human_readable_size(filePath)
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
                datasetMetadata["vars"] = read_netcdf_file(datasetMetadata["name"], "metadata")
        
        elif fileType == "raw":
            datasetMetadata["width"] = request.form.get("width")
            datasetMetadata["height"] = request.form.get("height")
            datasetMetadata["depth"] = request.form.get("depth")
            datasetMetadata["precision"] = request.form.get("precision")

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
        if data_key not in decompressed_data_cache:
            return jsonify({"error": "Data not found or expired"}), 404
        
        data = decompressed_data_cache[data_key]
        data_bytes = data.tobytes()
        return Response(data_bytes, mimetype="application/octet-stream")
    except Exception as e:
        print(f"Error in get_decompressed_data(): {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/indexlist", methods=["POST"])
@token_required
def indexlist():
    try:
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
                if input_array is None and meta.get("name"):
                    filePath = upload_dir / meta["name"]
                    dtype = np.float64 if precision == 'd' else np.float32
                    buffer = np.fromfile(filePath, dtype=dtype)
                    if dimensions and len(dimensions) == 3:
                        width, height, depth = map(int, dimensions)
                        expected = width * height * depth
                        if len(buffer) > expected:
                            buffer = buffer[len(buffer) - expected:]
                        buffer = buffer.reshape(depth, height, width)
                    input_array = buffer
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
                    
                    compressor = lp.PressioCompressor.from_config(patched_args)
                    decompData = dataset.copy()
                    compData = compressor.encode(dataset)
                    decompData = compressor.decode(compData, decompData)
                    metrics = compressor.get_metrics()
                    metrics1 = replace_unsupported_values(metrics)
                    
                    return {
                        "compressor_id": args["compressor_id"],
                        "metrics": metrics1,
                        "decompressed_data": decompData,  # Return the numpy array
                    }
                result = run_compressor(arguments, input_array)
                # Extract decompressed data and store it in cache
                decompData = result.pop("decompressed_data")
                # Generate a unique key for this result
                key = hashlib.md5(f"{arguments.get('compressor_id')}_{time.time()}".encode()).hexdigest()
                result["data_key"] = key
                decompressed_data_cache[key] = decompData
                return result
            
            configurations = json.loads(request.form.get("configurations"))
            # pprint(configurations)
            result = {}
            for name, config in configurations.items():
                print("Running compressor: ", name)
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
        print("Error in indexlist():", e)
        return jsonify({"error": str(e)}), 500

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
            data_array = input_data_cache.get(data_key)
            if data_array is None:
                return jsonify({"error": "DATA_KEY_NOT_FOUND"}), 404
        else:
            # Fallback: read uploaded data file directly
            data_file = request.files.get('data')
            if not data_file:
                return jsonify({"error": "No data file or data_key provided"}), 400

            # Read binary data based on precision
            precision = parameters.get('precision', 'f')
            dtype = np.float64 if precision == 'd' else np.float32
            data_array = np.frombuffer(data_file.read(), dtype=dtype)

            # Get dimensions and reshape
            dimensions = parameters.get('dimensions', [])
            if len(dimensions) == 3:
                width, height, depth = dimensions
                data_array = data_array.reshape(depth, height, width)  # (D, H, W)
            elif len(dimensions) == 2:
                width, height = dimensions
                data_array = data_array.reshape(height, width)
            # 1D data stays flat

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
        dtype = np.float64 if precision == 'd' else np.float32
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

        # Store into cache under key (overwrite allowed)
        input_data_cache[data_key] = data_array

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

    app.run(host=apiHost, port=apiPort, debug=True, threaded=True)
