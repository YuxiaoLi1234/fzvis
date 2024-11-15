<template>
  <t-space>
    <t-loading :loading="loading" text="loading compressor..." fullscreen />
  </t-space>

  <div id="data_selection">
      <!--Enter your Configuration here-->
      
      <div class="saved-configs">
        <div class="saved-configs-container">
        <h3>Saved Configuration</h3>
        <div class="button-group">
          <t-button @click="showSavedConfig(0)">Save1</t-button>
          <t-button @click="showSavedConfig(1)">Save2</t-button>
          <t-button @click="showSavedConfig(2)">Save3</t-button>
        </div>
        </div>
      </div>
      <div class="input-group">
      <t-select id='compressor-select' name="compressor_id" v-model="compressor_id" :options="compressorOptions" label="Compressor:" />
      <t-input name="bound" v-model="bound" label="Bound:" placeholder="bound" />
      </div>
      <div id="metric-selection" :class="closed">
      <t-cascader name="selectedMetrics" v-model="selectedMetrics" :options="compressorMetrics" multiple label="Select Metrics:"
        placeholder="Select Compressor Metrics" :popup-props="{ trigger: 'click'}"/> 
      </div>
      <div class="button-group2">
        <t-button @click="saveConfiguration">Save Configuration</t-button>
        <t-button @click="confirmConfiguration">Confirm Configuration</t-button>
        <t-button id='update_button' @click="submitConfiguration">Submit</t-button>
      </div>
      <div v-if="showConfigWindow" class="config-window">
        <h3> Saved Configuration </h3>
        <p><strong> Compressor ID: </strong>{{ savedConfigurations[selectedSaveSlot].compressor_id }}</p>
        <p><strong> Bound: </strong>{{ savedConfigurations[selectedSaveSlot].compressor_config['pressio:abs'] }}</p>
        <p><strong> Metrics: </strong>{{ savedConfigurations[selectedSaveSlot].early_config['composite:plugins'].join(', ') }}</p>
        <t-button @click="clearSave(selectedSaveSlot)">Clear</t-button>
        <t-button @click="cancelConfiguration">Cancel</t-button>
        
      </div>
      <p id="temp1" ></p>
  </div>
</template>
//<style scoped src="@/assets/DataSelection.css"></style>
<script>
import axios from 'axios'
import emitter from './eventBus.js';
import config from '../../config.json';
export default {
name:'DataSelection',
data(){
    return{
      loaddata:0,
      formData: new FormData(),
      host:config.API_HOST,
      port:config.API_PORT,
      loading:false,
      compressor_id:'',
      num_compressors:0,
      bound:null,
      input_data:null,
      selectedFile: null,
      msg:'',
      closed: false,
      compare_data:{'compressor_id':[],'bound':[],'metrics':[],'input_data':''},
      compressorOptions: [
      { label: 'SZ', value: 'sz' },
      { label: 'ZFP', value: 'zfp' },
      { label: 'MGARD', value: 'mgard' },
      ],
      selectedMetrics: [],
      savedConfigurations: {
        '0':{ compressor_id: '', early_config: {}, compressor_config: {} },
        '1':{ compressor_id: '', early_config: {}, compressor_config: {} },
        '2':{ compressor_id: '', early_config: {}, compressor_config: {} }
      },
      selectedSaveSlot: null,
      showConfigWindow: false,
      compressorMetrics: [
      {
        label: 'Composite', value:'composite'
      },
      {
        label: 'Error Stat', value:'error_stat'
      },
      {
        label: 'Size',value:"size"
      },
      {
        label: 'Time', value:"time"
      }
    ],
  };   
},
computed: {
  flattenedCompressorMetrics() {
      return this.compressorMetrics.map(category => {
      return {
        label: category.label,
        options: category.children.map(metrics => ({
          label: metrics.label,
          value: metrics.value
        }))
      };
      });
  },
},
methods: {
    saveConfiguration() {
        for (let i = 0; i < 3; i++) {
          if (this.savedConfigurations[i].compressor_id === '') {
            this.selectedSaveSlot = i;
  
            // Prepare early_config and compressor_config
            const early_config = {
              "pressio:metric": "composite",
              "composite:plugins": [...this.selectedMetrics],
            };
  
            const compressor_config = {
              "pressio:abs": this.bound,
            };
  
            this.savedConfigurations[this.selectedSaveSlot].compressor_id = this.compressor_id;
            this.savedConfigurations[this.selectedSaveSlot].early_config = early_config;
            this.savedConfigurations[this.selectedSaveSlot].compressor_config = compressor_config;
            this.showConfigWindow = true;
            this.$message.success(`Configuration saved to Save${i + 1}`);
            return;
          }
        }
        this.$message.error('All save slots are full. Please edit or delete a save slot to continue.');
      },

    confirmConfiguration() {
      this.$message.success('All configurations confirmed.');
      console.log("Configurations Confimed:", this.savedConfigurations);
    },
    showSavedConfig(slot) {
      this.selectedSaveSlot = slot;
      this.showConfigWindow = true;
    },
    clearSave(slot) {
      this.savedConfigurations[slot] = { compressor_id: '', early_config: {}, compressor_config: {} };
      this.$message.info(`Save${slot + 1} cleared.`);
      this.showConfigWindow = false; // Close the config window after clearing
    },
    // editConfiguration() {
    //     this.compressor_id = this.savedConfigurations[this.selectedSaveSlot].compressor_id;
    //     this.bound = this.savedConfigurations[this.selectedSaveSlot].compressor_config['pressio:abs'];
    //     this.selectedMetrics = [...this.savedConfigurations[this.selectedSaveSlot].early_config['composite:plugins']];
    // },
    cancelConfiguration() {
      this.showConfigWindow = false;
    },
    submitConfiguration() {
        const metricsSelected = Object.values(this.selectedMetrics).flat().length > 0;
        if (this.compressor_id.length === 0 || this.bound === null || !metricsSelected) {
          this.msg = this.$message.info({
            content: 'Invalid Input',
            theme: "warning",
            duration: 1000,
            zIndex: 1001,
            attach: document.body,
          });
        } else {
          this.loading = true;
          // this.formData = new FormData();

          const plainMetrics = [...this.selectedMetrics];
          console.log('Plain Metrics:', plainMetrics);

          const early_config = {
              "pressio:metric": "composite",
              "composite:plugins": this.selectedMetrics,
          };
          console.log('Early config metrics:', early_config);
          const compressor_config = {
              "pressio:abs": this.bound, // Use the bound provided by the user
          };

          console.log('Compressor ID:', this.compressor_id);
          console.log('Bound:', this.bound);
          console.log('Early Config:', early_config);
          console.log('Compressor Config:', compressor_config);
          
          
          this.formData.append('loaddata', this.loaddata);
          this.formData.append('slice_id', 0);
          
          console.log("data transfer");
          
          if(this.formData.has("configurations")){
              this.formData.delete("configurations");
            }
          console.log('FormData Entries before submission:', [...this.formData.entries()]);
          this.formData.append("configurations",JSON.stringify(this.savedConfigurations));
          console.log('FormData Entries before submission2:', [...this.formData.entries()]);
          console.log('FormData before submission:', [...this.formData]);
          //const backendProtocol = window.location.protocol;
          //const backendHost = window.location.hostname;
          //const backendPort = '5001';       
          //const baseURL = `${backendProtocol}//${backendHost}:${backendPort}`;
          axios.post(`/indexlist`, this.formData)
            .then(response => {
              console.log('Response from server:', response.data);
              
              for(const key in response.data)
              {
                let element = response.data[key]
                
                if(key=='input_data') continue;
                this.compare_data['compressor_id'].push(key);
                this.compare_data['bound'].push(element['bound']);
                if (element['metrics']) {
                  this.compare_data['metrics'].push(element['metrics']);
                } else {
                    console.warn("Metrics returned from the backend are null or undefined.");
                }
              }
              
              this.input_data = response.data['input_data']
              
              document.getElementById('temp1').innerHTML = JSON.stringify(this.compare_data);
              emitter.emit('myEvent', this.compare_data);
              emitter.emit('inputdata', {"input_data":this.input_data, "width": this.width, "height":this.height, "depth":this.depth});
              
              this.loading = false;
            })
            .catch(error => {
            console.error('Error submitting configuration:', error.response ? error.response.data : error.message);
            alert('An error occurred. Please check the console for details.');
            });

        }
        console.log('FormData after submission:', [...this.formData]);
      }
      
    },
    mounted() {

      emitter.on('file-selected', (data) => {
            console.log("datamounted", data);
            this.formData.append('file', data["file"]);

            this.width = data["width"]
            this.height = data["height"]
            this.depth = data["depth"]

            this.formData.append('width', data["width"]);
            this.formData.append('height', data["height"]);
            this.formData.append('depth', data["depth"]);
            this.formData.append('precision', data["precision"]);
          });
    },
  };
</script>
<style scoped>
@import "@/assets/DataSelection.css";
</style>
