<template>
  <div class="container align-items-center" id="modals">

      <!-- 📌 Options panel -->
      <div class="options-panel px-2">
        <h1 class="h3 pt-3 pb-2">Available Options</h1>

        <div class="dropdown">
          <select id="compressor" class="form-select m-1" aria-label="compressor" v-model="selectedCompressor" @change="getCompressorConfigs">
            <option value=null disabled selected>Select compressor</option>
            <option v-for="compressor in availableCompressors" :key="compressor.id" :value="compressor">{{ compressor.label }}</option>
          </select>
        </div>

        <div v-if="selectedCompressor" class="pt-2">
          <div class="card">
            <div class="card-body" v-if="selectedCompressor.id in this.compressorOptions">
              <h5 class="card-title">{{ selectedCompressor.label }}</h5>
              <p class="card-text">High-level options are listed here.</p>
              <div class="d-flex flex-wrap mb-2">
                <div class="me-2 mb-2" v-for="option in compressorOptions[selectedCompressor.id]['Highlevel']" :key="option.id">
                  <div class="form-floating">
                    <input v-if="option.label == 'Nthreads'" type="number" class="form-control" style="width:120px;" title="Number of threads to use" :id="option.id" :placeholder="option.label" min="1" step="1" v-model="configuredValues['Highlevel'][option.id]">
                    <input v-else type="number" class="form-control" style="width:120px;" title="this should be the help tooltip" :id="option.id" :placeholder="option.label" min="0" v-model="configuredValues['Highlevel'][option.id]" @input="handleHighLevelInput(option.id)">
                    <label :for="option.id">{{ option.label }}</label>
                  </div>
                </div>
              </div>
              <p class="card-text">Detailed options are listed here.</p>
              <div v-for="(optionList, optionName) in filteredDetailOptions" :key="optionName">
                <multiselect class="mb-2 me-2" :options="optionList" v-model="configuredValues['Detail'][optionName]" :close-on-select="true" :clear-on-select="false" :placeholder="`Select ${optionName}`" label="label" track-by="id" @select="handleOptionsChange(optionName)" aria-label="optionName">
                </multiselect>
                <!-- <multiselect class="mb-2 me-2" :options="optionList" v-model="configuredValues['Detail'][optionName]" :multiple="optionName === 'Metric'" :close-on-select="optionName != 'Metric'" :clear-on-select="false" :placeholder="`Select ${optionName}`" label="label" track-by="id" @select="handleOptionsChange(optionName)" aria-label="optionName">
                </multiselect> -->
                <input v-if="optionName === 'Error Bound' && configuredValues['Detail'][optionName] && !configuredValues['Highlevel']['pressio:abs'] && !configuredValues['Highlevel']['pressio:rel']" type="number" class="form-control w-auto mb-2" placeholder="Enter value" min="0" step="0.001" v-model="configuredValues['Detail'][optionName].value">
              </div>
              <small class="d-block mb-2 text-muted">
                {{ isConfigValid ? 'Click submit to record configuration.' : 'Please fill all fields to submit.' }}
              </small>
              <button type="button" class="btn btn-primary me-2" :disabled="!isConfigValid" data-bs-toggle="modal" data-bs-target="#saveConfigModal" @click="currentConfigName = selectedCompressor.id + '_' + getFormattedTimestamp()">Submit</button>
              <button type="reset" class="btn btn-secondary" @click="resetConfiguredValues">Reset</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Save configuration modal -->
      <div id="saveConfigModal" class="modal fade" tabindex="-1" aria-labelledby="saveConfigModalLabel" data-bs-backdrop="static" data-bs-keyboard="false" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered modal-sm">
          <div class="modal-content">
            <div class="modal-header">
              <h1 class="modal-title fs-5" id="saveConfigModalLabel">Save current configuration</h1>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
              <div class="form-floating">
                <input type="text" class="form-control" id="floatingConfigName" placeholder="Configuration name" v-model="currentConfigName">
                <label for="floatingConfigName">Configuration name</label>
              </div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
              <button type="button" class="btn btn-primary" data-bs-dismiss="modal" @click="handleSaveConfiguration" :disabled="currentConfigName == ''">Save changes</button>
            </div>
          </div>
        </div>
      </div>

      <!-- 📌 Configuration panel -->
      <div class="dropzone-panel p-2">
        <div v-if="Object.keys(savedConfigurations).length < 2" class="text-info pb-2">
          There is <strong>{{ Object.keys(savedConfigurations).length }}</strong> saved configuration.
        </div>
        <div v-else class="text-info pb-2">
          There are <strong>{{ Object.keys(savedConfigurations).length }}</strong> saved configurations.
        </div>

        <div class="d-flex flex-wrap gap-2">
          <button type="button" class="btn btn-primary" @click="submitConfigurations" :disabled="Object.keys(savedConfigurations).length === 0">Submit Configurations</button>
          <button type="button" class="btn btn-secondary" :disabled="Object.keys(savedConfigurations).length === 0" data-bs-toggle="modal" data-bs-target="#showConfigModal">View Configurations</button>
        </div>
      </div>

      <!-- Alert message box -->
      <div id="compressorAlert" class="alert alert-dismissible fade" role="alert" tabindex="-1">
        <span id="compressorAlertMessage">Placeholder</span>
        <!-- <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button> -->
      </div>

      <!-- Show saved configuration modal -->
      <div id="showConfigModal" class="modal fade" tabindex="-1" aria-labelledby="showConfigModalLabel" data-bs-backdrop="static" data-bs-keyboard="false" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h1 class="modal-title fs-5" id="showConfigModalLabel">Saved configuration</h1>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body" v-if="Object.keys(savedConfigurations).length > 0">
              <div v-for="(config, name) in savedConfigurations" :key="name" class="config-card">
                <h5>{{ name }}<button class="btn btn-danger ms-1" aria-label="Delete" title="Delete the configuration" @click="delete savedConfigurations[name]"><i class="bi bi-trash"></i></button></h5> 
                <ul>
                  <li><strong>Compressor:</strong> {{ config.compressor_id.toUpperCase() }}</li>
                  <li v-for="(value, key) in formatConfig(config.compressor_config)" :key="key">
                    <strong>{{ key }}:</strong> {{ value }}
                  </li>
                </ul>
              </div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
              <!-- <button type="button" class="btn btn-primary">Save changes</button> -->
            </div>
          </div>
        </div>
      </div>

    </div>
</template>


<script>
import axios from 'axios';
import Multiselect from 'vue-multiselect';

export default {
  components: {
    Multiselect,
  },
  data() {
    return {
      availableOptions: {
        "Compressor": [
          { id: "binning", label: "Compressor: Binning", type: "compressor" },
          { id: "chunking", label: "Compressor: Chunking", type: "compressor" },
          { id: "roibin", label: "Compressor: Roibin", type: "compressor" },
          { id: "sz3", label: "Compressor: SZ3", type: "compressor" },
          { id: "zfp", label: "Compressor: ZFP", type: "compressor" },
        ]
      },
      initialOptions:{
        "Compressor": [
          { id: "sz3", label: "Compressor: SZ3", type: "compressor" },
          { id: "zfp", label: "Compressor: ZFP", type: "compressor" }
        ]
      },
      compressorOptions: {},
      configuredValues: {},
      currentConfigName: "", // input configuration name
      savedConfigurations: {}, // all the saved configurations
      selectedCompressor: null,
      editingConfig: null,
      editingData: {},
      compare_data: {'compressor_id':[],'compressor_name':[],'bound':[],'metrics':[],'input_data':''},
      formattedConfigurations: null,
      formData: new FormData(),
    };
  },

  computed: {
    availableCompressors() {
      if (!this.availableOptions || Object.keys(this.availableOptions).length === 0) {
        return [];
      }
      return this.availableOptions["Compressor"];
    },

    isConfigValid() {
      const options = this.compressorOptions[this.selectedCompressor.id]["Detail"];
      if (!options) return false;

      return Object.values(this.configuredValues["Detail"]).every((item) => {
        // handle error bound: must have a value
        if (item?.label?.startsWith("Error Bound:")) {
          return item?.value !== undefined && item.value !== '';
        }

        // handle arrays: must be non-empty
        if (Array.isArray(item)) {
          return item.length > 0;
        }

        // regular options: must have an id
        return item?.id !== undefined;
      });
    },

    filteredDetailOptions() {
      const absVal = this.configuredValues?.Highlevel?.["pressio:abs"];
      const relVal = this.configuredValues?.Highlevel?.["pressio:rel"];

      const detailOptions = { ...this.compressorOptions[this.selectedCompressor.id]["Detail"] };

      if ("Error Bound" in detailOptions) {
        detailOptions["Error Bound"] = detailOptions["Error Bound"].filter(item => {
          const id = (item.id || '').toLowerCase();
          const containsAbs = id.includes("abs");
          const containsRel = id.includes("rel");

          if (absVal && relVal) {
            return containsAbs && containsRel;
          }
          if (!absVal && !relVal) {
            return !containsAbs && !containsRel;
          }
          if (absVal) {
            return containsAbs && !containsRel;
          }
          return false;
        });
      }

      return detailOptions;
    },

    fileData() {
      return this.$store.state.fileData;
    }
  },

  watch: {
    "configuredValues.Highlevel": {
      handler() {
        this.resetErrorBound();
      },
      deep: true,
    }
  },

  methods: {
    
    getFormattedTimestamp() {
      const pad = (n) => n.toString().padStart(2, '0');
      const now = new Date();
      const month = pad(now.getMonth() + 1);
      const day = pad(now.getDate());
      const hours = pad(now.getHours());
      const minutes = pad(now.getMinutes());
      const seconds = pad(now.getSeconds());

      return `${month}_${day}_${hours}_${minutes}_${seconds}`;
    },

    getFormattedKey(key){
      return key
        .replace(/^.*?:/, "")               // remove namespace prefix like `sz3:` or `pressio:`
        .replace(/_str$/, "")               // remove `_str` suffix
        .replace(/_mode$/, "")              // remove `_mode` suffix
        .replace(/_algo$/, "")              // remove `_algo` suffix
        .replace("_error_bound", " Error Bound") // special handling
        .replace(/_/g, " ")                 // underscores to spaces
        .replace(/\b\w/g, c => c.toUpperCase()); // capitalize words
    },

    formatConfig(compressorConfig) {
      if (!compressorConfig) return {};

      return Object.fromEntries(
        Object.entries(compressorConfig).map(
          ([key, value]) => [this.getFormattedKey(key), value]
        )
      );
    },

    resetErrorBound() {
      const selected = this.configuredValues.Detail?.['Error Bound'];
      const available = this.filteredDetailOptions?.['Error Bound'] || [];

      const stillExists = available.some(opt => opt.id === selected?.id);
      if (selected && !stillExists) {
        this.configuredValues["Detail"]["Error Bound"] = null;
      }
    },

    resetConfiguredValues() {
      // Handle case where options already exist
      this.configuredValues = {};
      const allOptions = this.compressorOptions[this.selectedCompressor.id];
      Object.entries(allOptions).forEach(([category, options]) => {
        this.configuredValues[category] = {};
        Object.keys(options).forEach(option => {
          this.configuredValues[category][option] = null;
        })
      });
    },

    getCompressorConfigs() {
      // Only send the request if options for the selected compressor haven't been fetched before
      if (!(this.selectedCompressor.id in this.compressorOptions)) {
        let formData = new FormData();
        formData.append("get_options", 1);
        formData.append("compressor_id", this.selectedCompressor.id);

        var formattedOptions = {};
        const baseURL = process.env.VUE_APP_API_BASE;
        axios.post(`${baseURL}/indexlist`, formData)
        .then(response => {
          const highlevel = response.data.highlevel;
          formattedOptions["Highlevel"] = highlevel.map(item => ({
            id: `${item}`,
            label: this.getFormattedKey(item),
            type: "Highlevel",
          }));

          const rawOptions = response.data.options;
          const filteredOptions = {...Object.fromEntries(Object.entries(rawOptions).filter(([key]) => key.startsWith(this.selectedCompressor.id)))};

          formattedOptions["Detail"] = {
            ...Object.entries(filteredOptions).reduce((acc, [category, values]) => {
              // remove `sz3:` prefix and `_str` suffix
              const formattedCategory = this.getFormattedKey(category);
              
              acc[formattedCategory] = values.map(value => ({
                id: `${category}-${value}`,
                label: `${formattedCategory}: ${value}`, // format label for display
                type: category
              }));
              return acc;
            }, {})
          };
          
          // Manually add error bound option if missing
          const hasErrorBound = Object.keys(formattedOptions["Detail"]).some(category => category.toLowerCase().includes("error bound"));
          if (!hasErrorBound) {
            formattedOptions["Detail"]["Error Bound"] = [{
              id: "pressio:abs",
              label: "Error Bound: ABS",
              type: "error bound",
            }];
          }

          this.configuredValues = {};
          Object.entries(formattedOptions).forEach(([category, options]) => {
            this.configuredValues[category] = {};
            // High-level options should be an array
            if (Array.isArray(options)) {
              options.forEach(item => {
                this.configuredValues[category][item.id] = null;
              });
            }
            else {
              Object.keys(options).forEach(optionKey => {
                this.configuredValues[category][optionKey] = null;
              });
            }
          });
          this.compressorOptions[this.selectedCompressor.id] = formattedOptions;
          console.log("formattedOptions:", formattedOptions);
          console.log("configuredValues:", JSON.stringify(this.configuredValues));
        })
        .catch(error => {
          console.error('Error submitting configuration:', error.response ? error.response.data : error.message);
          alert('An error occurred. Please check the console for details.');
        });
      }
      else {
        // Handle case where options already exist
        this.resetConfiguredValues();
      }
    },

    handleHighLevelInput(optionId) {
      if (optionId) {
        if (optionId.toLowerCase().includes("abs")) {
          const selected = this.configuredValues["Detail"]?.["Error Bound"];
          if (selected) {
            this.configuredValues["Detail"]["Error Bound"].value = this.configuredValues["Highlevel"][optionId];
          }
        }
        else if (optionId.toLowerCase().includes("rel")) {
          const selected = this.configuredValues["Detail"]?.["Error Bound"];
          if (selected) {
            this.configuredValues["Detail"]["Error Bound"].value = this.configuredValues["Highlevel"][optionId];
          }
        }
      }
    },

    handleOptionsChange(optionName) {
      // console.log("optionName:", optionName);
      if (optionName === 'Error Bound') {
        const selected = this.configuredValues["Detail"]?.["Error Bound"];
        console.log("selected:", selected);
        if (selected && selected.id.toLowerCase().includes("abs")) {
          this.configuredValues["Detail"]["Error Bound"].value = this.configuredValues["Highlevel"]["pressio:abs"];
        }
        if (selected && selected.id.toLowerCase().includes("rel")) {
          this.configuredValues["Detail"]["Error Bound"].value = this.configuredValues["Highlevel"]["pressio:rel"];
        }
      }
    },

    handleSaveConfiguration() {
      const config = {"compressor_config":{}};
      console.log("configuredValues", JSON.stringify(this.configuredValues));

      config.compressor_id = this.selectedCompressor.id;
      Object.values(this.configuredValues["Detail"]).forEach((item) => {
        // if item is an array
        if (Array.isArray(item)) {
          item.forEach(element => {
            if (element?.id) {
              const [prefix, key] = element.id.split("-");
              config["compressor_config"][prefix] = config["compressor_config"][prefix] || [];
              config["compressor_config"][prefix].push(key);
            }
          });
        }
        
        else if (item.label.startsWith("Error Bound:")) {
          if(item.id.split(":")[0] != this.selectedCompressor.id){
            config["compressor_config"][item.id] = item.value
          }
          else{
            const errorMode = item.label.split(": ")[1];
            config["compressor_config"][`${this.selectedCompressor.id}:${errorMode.toLowerCase()}_error_bound`] = item.value;
          }
        }
        
        else if(!item.label.startsWith("Compressor:")) {
          const [prefix, key] = item.id.split("-");
          config["compressor_config"][prefix] = key;
        }
      });

      // Save current configuration
      // corrected config format:
      // savedConfig {"compressor_config":{"sz3:algorithm_str":"ALGO_INTERP","sz3:abs_error_bound":0.001,"sz3:intrep_algo_str":"INTERP_ALGO_CUBIC","sz3:metric":"composite"},"compressor_id":"sz3"}
      this.savedConfigurations[this.currentConfigName] = config;
      console.log("savedConfigurations", JSON.stringify(this.savedConfigurations));
      this.currentConfigName = "";
    },

    submitConfigurations() {
      
      const alertBox = document.getElementById("compressorAlert");
      const alertMessage = document.getElementById("compressorAlertMessage");

      if (this.fileData) {
        const formattedConfigurations = Object.entries(this.savedConfigurations).map(([name, config]) => {
          return {
            compressor_id: config.compressor_id || "unknown",
            compressor_name: name,
            early_config: {
              "pressio:metric": "composite",
              "composite:plugins": ["time", "size", "error_stat"],
            },
            compressor_config: config["compressor_config"],
          };
        });
        console.log("Formatted Configurations:", formattedConfigurations);
  
        // Clear out previous configurations
        if(this.formData.has("configurations")){
          this.formData.delete("configurations");
        }
  
        if(this.formData.has("get_options")){
          this.formData["get_options"] = 0;
        } else {
          this.formData.append("get_options", 0);
        }
        this.formData.append("configurations", JSON.stringify(formattedConfigurations));
        
        if (alertBox && alertMessage) {
          alertBox.classList.remove("alert-danger");
          alertBox.classList.remove("alert-success");
          alertBox.classList.add("alert-secondary", "show");
          alertMessage.textContent = "Processing...";
        }

        const baseURL = process.env.VUE_APP_API_BASE;
        axios.post(`${baseURL}/indexlist`, this.formData).then(response => {
          const names = Object.values(formattedConfigurations).map((d)=>d.compressor_name);
          const configs = Object.values(formattedConfigurations).map((d)=>d.compressor_config);
          // console.log("response: ", response.data);
          for (const key in response.data) {
            let element = response.data[key]
  
            if(key == 'input_data') continue;
            if(key == 'decp_data') continue;
            
            this.compare_data['compressor_id'].push(response.data[key]['compressor_id']);
            this.compare_data['bound'].push(element['bound']);
            if (element['metrics']) {
              this.compare_data['metrics'].push(element['metrics']);
            } else {
              console.warn("Metrics returned from the backend are null or undefined.");
            }
          }
  
          if (alertBox && alertMessage) {
            alertBox.classList.remove("alert-danger");
            alertBox.classList.remove("alert-secondary");
            alertBox.classList.add("alert-success", "show");
            alertMessage.textContent = "Compression executed successfully!";
            // Auto dismiss
            setTimeout(() => {
              alertBox.classList.remove("show");
            }, 6000);
          }
          // this.input_data = response.data['input_data']
  
          this.compare_data['compressor_name'] = names;
          this.compare_data['compressor_config'] = configs;

          this.$store.commit("setCompressedData", response.data["decp_data"][0]);
          // document.getElementById('temp1').innerHTML = JSON.stringify(this.compare_data);
          // emitter.emit('myEvent', this.compare_data);
          // emitter.emit('inputdata', {"input_data":this.input_data, "width": this.width, "height":this.height, "depth":this.depth,"compressor_name":names, "decp_data": response.data['decp_data']});
          // emitter.emit('compressor_configuration', this.savedConfigurations);
        }).catch(error => {
          if (alertBox && alertMessage) {
            alertBox.classList.remove("alert-success");
            alertBox.classList.remove("alert-secondary");
            alertBox.classList.add("alert-danger", "show");
            if (error.response) {
              alertMessage.textContent = `Compression failed. ${error.response.data.error}`;
            } else {
              alertMessage.textContent = `Compression failed. ${error}`;
            }
            // Auto dismiss
            setTimeout(() => {
              alertBox.classList.remove("show");
            }, 6000);
          }
          console.error('Error submitting configuration:', error.response ? error.response.data : error.message);
          // alert('An error occurred. Please check the console for details.');
        });
        
        return formattedConfigurations;
      }
      // No dataset file selected
      else {
        if (alertBox && alertMessage) {
          alertBox.classList.remove("alert-success");
          alertBox.classList.remove("alert-secondary");
          alertBox.classList.add("alert-danger", "show");
          alertMessage.textContent = "No dataset selected!";
        }
      }
    },

    resetAvailableOptions() {
      this.availableOptions = [...this.initialOptions];
    },

  },
};
</script>

<style src="vue-multiselect/dist/vue-multiselect.min.css"></style>