#!/usr/bin/env python

import numpy as np
import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pathlib import Path
import json
import libpressio
from argparse import ArgumentParser
import math

dist_dir = Path(__file__).parent.parent / "usr/libexec/fzvis/ui"

app = Flask(__name__)
CORS(app)
@app.route('/indexlist', methods=["GET", "POST"])



def indexlist():
    global input_data, depth, height, depth
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
        global  input_data, width, depth, height
        print("arguments: ", arguments)
        def get_metrics_configuration(metrics):
            if 'composite' in metrics:
                # If composite is selected, use all metrics
                return {
                    "pressio:metric": "composite",
                    "composite:plugins": ["time", "size", "error_stat"]
                }
            else:
                # Otherwise, only use the selected metrics
                return {
                    "pressio:metric": "composite",
                    "composite:plugins": metrics
                }

        configs = {
            "compressor_name": arguments['compressor_name'],
            "compressor_id": arguments["compressor_id"],
            "early_config": get_metrics_configuration(arguments['early_config'].get("composite:plugins", [])),
            "compressor_config": arguments["compressor_config"],
        }
        def run_compressor(args):
            global input_data, width, height, depth
            compressor = libpressio.PressioCompressor.from_config({
                "compressor_id": args['compressor_id'],
                "early_config": args['early_config'],
                "compressor_config": args['compressor_config']
            })
            decomp_data = input_data.copy()
            comp_data = compressor.encode(input_data)
            decomp_data = compressor.decode(comp_data, decomp_data)
            metrics = compressor.get_metrics()
            metrics1 = replace_unsupported_values(metrics)
            
            return {
                "compressor_name": args['compressor_name'],
                "compressor_id": args['compressor_id'],
                "metrics": metrics1,
                "decp_data": decomp_data.tolist()
            }
        result = run_compressor(configs)
        
        return result
    
    if request.method == 'POST':
        print(request.form['get_options'])
        if(int(request.form['get_options']) == 0):
            file = request.files['file']
            width = int(request.form['width'])
            height = int(request.form['height'])
            depth = int(request.form['depth'])
            precision = request.form.get('precision')
            print(precision)
            if precision=='d': 
                input_data = np.fromfile(file, dtype=np.float64)
            elif precision=='f': 
                input_data = np.fromfile(file, dtype=np.float32)

            if len(input_data)>width*height*depth: input_data = input_data[len(input_data)- width*height*depth:]
            
            input_data = input_data.reshape(width, height, depth)
            input_data = np.nan_to_num(input_data, nan=0)
            configurations = json.loads(request.form.get('configurations'))
            print(configurations)
            result = {}
            decp_data = []
            for key in configurations:
                print(key)
                if(key['compressor_id']!=''):
                
                    print(key)
                    output = comparing_compressor(key)
                    result[output['compressor_name']] = {"compressor_id": output['compressor_id'],
                                                    "metrics": output['metrics'],
                                                }
                    decp_data.append(output['decp_data'])
            print(result)
            result['input_data'] = input_data.tolist()
            result['decp_data'] = decp_data
            #return json.loads(json.dumps(output,indent=2))
            return jsonify(result)
        
            # print(slice_number,sliced_id,slice_width,slice_height,type(input_data),len(input_data))
        else:
            compressor_id = request.form["compressor_id"]
            c = libpressio.PressioCompressor("pressio", {"pressio:compressor": compressor_id}, name="pressio")
            top_level = c. get_configuration()["pressio"]
            children = top_level["pressio:children"] # you'll see pressio/noop and pressio/sz3
            options = top_level[compressor_id] #we determined that "sz3" is the right string here by stripping out "pressio/" from the entries in children
            module_slots = {k: options[k] for k in options if k.startswith(compressor_id)}
            
            return module_slots
    else:
        return jsonify({"error": "configuration is illegal"}), 400
    

# Catch-all route to serve the Vue frontend's index.html
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    print(f"Requested path: {path}")
    print(f"dist_dir: {dist_dir}")
    full_path = os.path.join(dist_dir, path)
    print(f"Full path: {full_path}")
    if os.path.isfile(full_path):
        return send_from_directory(dist_dir, path)
    else:
        return send_from_directory(dist_dir, 'index.html')


parser = ArgumentParser(description="enter your HOST/POST.", usage="path/to/main.py [OPTIONAL ARGUMENTS] <HOST> <PORT> <configfile>")
parser.add_argument('--HOST', nargs='?', help='HOST_address', default="0.0.0.0")
parser.add_argument('--PORT', nargs='?', help='PORT_address', default="5003")
parser.add_argument('--configfile', nargs='?', help='your_config_file', default=None)   

if __name__ == '__main__':
    input_data = None
    width = -1
    height = -1
    depth = -1
    input = parser.parse_args()
    if not any(vars(input).values()):
        parser.print_help()
    api_host = input.HOST
    api_port = input.PORT
    config = {
        "API_HOST": api_host,
        "API_PORT": api_port
    }
    with open('./config.json', 'w') as json_file:
        json.dump(config, json_file, indent=4)
    app.run(host=api_host, port = api_port, debug=True)
