from flask import Flask, request
from flask_cors import CORS
import json
import requests

import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname='164.107.120.231', username='yli', password='30d5f21a21fca0cb18b8626f')

# ssh.exec_command('python3 /home/yli/lyx/getdata.py')
stdout = ssh.exec_command('python3 /home/yli/lyx/getdata.py')[1]
print('22')
output = stdout.read().decode('utf-8')
print(output)
# a way to upload the input data is needed
app = Flask(__name__)
CORS(app, supports_credential=True)

ssh.close()
# print(stdout.read().decode())
@app.route('/indexlist',methods=["GET","POST"])
def indexlist():
    if request.method == 'POST':
        # use the data from font-end json.load(request.data)
        compressor_id = json.loads(request.data)['compressor_id']
        early_config = json.loads(request.data)['early_config']
        compressor_config = json.loads(request.data)['compressor_config']
        
        
        configration = {'compressor_id':json.dumps(compressor_id), 
                        'early_config':json.dumps(early_config),
                        'compressor_config':json.dumps(compressor_config)
                        }
        

        return configration
    else:
        return 'configuration is illegal'
if __name__ == '__main__':
   app.run(debug=True)