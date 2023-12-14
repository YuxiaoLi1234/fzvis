from flask import Flask, request
from flask_cors import CORS
import json
import requests
import numpy as np
import paramiko
import time
import libpressio
from pathlib import Path
from pprint import pprint







# a way to upload the input data is needed
app = Flask(__name__)
# CORS(app, supports_credential=True)
CORS(app)
# ssh.close()
# print(stdout.read().decode())
@app.route('/indexlist',methods=["GET","POST"])
# 
def indexlist():
    def comparing_compressor(arguments):
        
        input_path = eval(arguments['input_data'])
        print(input_path)
        input_data = np.fromfile(input_path, dtype=np.float32)
        # print(input_data)
        # print(eval(arguments["compressor_config"]))
        configs = {
                "compressor_id": arguments["compressor_id"],
                "early_config": arguments["early_config"],
                "compressor_config": arguments["compressor_config"],
                "bound":arguments["compressor_config"]["pressio:abs"]
            }
        
        def run_compressor(args):
            compressor = libpressio.PressioCompressor.from_config({
                # configure which compressor to use
                "compressor_id": args['compressor_id'],
                # configure the set of metrics to be gathered
                "early_config": args['early_config'],
                # {
                #     "pressio:metric": "composite",
                #     "composite:plugins": ["time", "size", "error_stat", "external"],
                #     "external:config_name": f"{args['compressor_id']}-{args['bound']:1.1e}",
                #     # "external:command": str(Path(__file__).absolute().parent.parent / "visualize.py")
                # },
                # configure the compressor
                "compressor_config": args['compressor_config']
                })
            decomp_data = input_data.copy()
            comp_data = compressor.encode(input_data)
            decomp_data = compressor.decode(comp_data, decomp_data)
            metrics = compressor.get_metrics()

            return {"compressor_id": args['compressor_id'],"bound": args['bound'],"metrics": metrics}
        result = run_compressor(configs)
        print('结束')
        return json.dumps(result)
    print('yes')
    if request.method == 'POST':
        # use the data from font-end json.load(request.data)
        
        compressor_id = json.loads(request.data)['compressor_id']
        print(eval(json.loads(request.data)['early_config']))
        early_config = json.loads(eval(json.loads(request.data)['early_config']))
        compressor_config = json.loads(eval(json.loads(request.data)['compressor_config']))
        input_data = json.loads(request.data)['input_data']
        
        # print(json.loads(early_config))
        # print('读入的shihou',type(json.loads(eval(compressor_config))))
        


        # with open(input_data, 'r') as file:
        #     data = json.load(file)
        
        configration = {'compressor_id':compressor_id, 
                        'early_config':early_config,
                        'compressor_config':compressor_config,
                        'input_data':input_data
                        }
        # comparing_compressor(configration)
        # print('输入的',early_config)
        # command = (
        #     f". /home/yli/lyx/spack/share/spack/setup-env.sh && "
        #     f"spack load libpressio && "
        #     f"python3 /home/yli/lyx/libpressio/test1/libpressio_tutorial/exercises/2_comparing_compressors/python/comparing_compressors.py {compressor_id} {early_config} {compressor_config} {input_data}"
        #     # f"python3 /home/yli/lyx/getdata.py {compressor_id} {early_config} {compressor_config} {input_data}"
        # )
        # e,stdout,stderr = ssh.exec_command(command)
        # output = stdout.read().decode('utf-8')
        # error = stderr.read().decode('utf-8')
        
        # # 处理输出
        # print("OUTPUT:")
        # print(output)
        # print(type(output))
        # # print(json.loads(output))
        # print("ERROR:")
        # print(error)
        # if error:return
        output = comparing_compressor(configration)
        # print('输出的事L:',output)
        return output
    else:
        return 'configuration is illegal'



if __name__ == '__main__':
   app.run(debug=True)