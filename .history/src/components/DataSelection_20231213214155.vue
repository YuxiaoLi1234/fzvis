<template>
    <t-space>
    <t-loading :loading="loading" text="loading compressor..." fullscreen />
      <!-- <t-switch v-model="loading"></t-switch> -->

  </t-space>
    <div id="data_selection">
        <p>Enter your Configuration here</p>

        <t-input id = 'input1' v-model="compressor_id" placeholder='null' label="compressor_id:"  @enter="update"/>
        <t-input id = 'input5' v-model="compressor_name" placeholder='null' label="compressor_name:"  @enter="update"/>

        <t-input id = 'input2' v-model="early_config" placeholder='null' label="early_config:"  @enter="update"/>
        <t-input id = 'input3' v-model="compressor_config" placeholder='null' label="compressor_config:"  @enter="update"/>
        <t-input id = 'input4' v-model="input_data" placeholder='null' label="path_to_input_data:"  @enter="update"/>
        <!-- <t-alert theme="error" :message="infoMessage">  </t-alert> -->
        <!-- <t-button id = 'submit' @click="submit">submit</t-button> -->
        <p id="temp1" ></p>

    </div>

    <!-- need a place to upload the inputdata -->
</template>

<script>
import axios from 'axios'
import emitter from './eventBus.js';
// import { json } from 'd3';
export default {
  name:'DataSelection',
  data(){
      return{
        infoMessage:'',
        loading:false,
        compressor_id:'sz',
        early_config:`'{"pressio:metric":"composite","composite:plugins": ["time","size","error_stat","external"]}'`,
        compressor_config:`'{"pressio:abs": 0.001}'`,
        input_data:'./data/inputdata.json',
        compressor_name:'sz1',
        msg:'',
        compare_data:{'compressor_id':[],'bound':[],'metrics':[],'input_data':''},
      };
  },
  methods:{
    update:function(){
        console.log('changed')
        if(this.compressor_id.length == 0 || this.early_config.length == 0 || this.compressor_config.length == 0){
            this.msg = this.$message.info({
                    content: 'input is illegal',
                    theme:"warning",
                    duration: 1000,
                    // 层级控制：非当前场景自由控制开关的关键代码，仅用于测试 API 是否运行正常
                    zIndex: 1001,
                    // 挂载元素控制：非当前场景自由控制开关的关键代码，仅用于测试 API 是否运行正常
                    attach: document.body,
                });
        }
        else{
            // const that = this
            this.loading = true

            axios.post('http://localhost:5000/indexlist',{
                
            'compressor_id':this.compressor_id,
            'early_config':this.early_config,
            'compressor_config':this.compressor_config,
            'input_data':this.input_data
            }).then(response=>{
                
                let need1 = response.data
                console.log('接受数据',typeof(need1))
                this.compare_data['compressor_id'].push(this.compressor_name)
                this.compare_data['bound'].push(need1['bound'])
                this.compare_data['metrics'].push(need1['metrics'])
                this.compare_data['input_data']=this.input_data
                document.getElementById('temp1').innerHTML=JSON.stringify(this.compare_data)
                emitter.emit('myEvent', this.compare_data);
                this.loading = false
            })
            .catch((error)=>{
                this.loading = false
                // this.infoMessage = 'illegal input'
                alert('illegal input');
                console.log(error)
            })
        }
        
    },
    submit:function(){
        
        
    }
  }
}
</script>

<style scoped>
#data_selection{
    border:2px solid #a7b2ac;
    border-radius: 4px;
    position:absolute;
    top:1%;
    left:.7%;
    width: 28%;
    height: 26%;
}
#input1{
    position:absolute;
    width:70%;
    top:5%;
    left:10%
}
#input2{
    position:absolute;
    width:70%;
    top:25%;
    left:10%
}
#input3{
    position:absolute;
    width:70%;
    top:45%;
    left:10%
}
#submit{
    position:absolute;
    z-index:101;
    top:85%;
    right:10%
}
#input4{
    position:absolute;
    width:70%;
    top:65%;
    left:10%
}
#input5{
    position:absolute;
    width:70%;
    top:85%;
    left:10%
}
p{
    position:absolute;
    left:10%
}
#temp1{
    display: none;
}
</style>