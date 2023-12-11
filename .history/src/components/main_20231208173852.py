from flask import Flask, request
from flask_cors import CORS
import json
import requests

import paramiko
import time
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(hostname='164.107.120.231', username='yli', password='30d5f21a21fca0cb18b8626f')

# ssh.exec_command('python3 /home/yli/lyx/getdata.py')
ssh.exec_command('exec bash')
ssh.exec_command('cd /home/yli/lyx')
ssh.exec_command('. /home/yli/lyx/spack/share/spack/setup-env.sh')

# ssh.exec_command('/home/yli/lyx/spack/bin/spack load libpressio')
e,stdout,stderr = ssh.exec_command('sudo /home/yli/lyx/spack load libpressio')
channel = stdout.channel

# 检查命令是否完成
while not channel.exit_status_ready():
    # 这里可以加入时间等待来避免过于频繁的检查
    time.sleep(1)

# 读取输出
output = stdout.read().decode('utf-8')
error = stderr.read().decode('utf-8')

# 处理输出
print("OUTPUT:")
print(output)
print("ERROR:")
print(error)

# 检查退出状态
exit_status = channel.recv_exit_status()
if exit_status == 0:
    print("Command executed successfully")
else:
    print("Command failed with exit status", exit_status)
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