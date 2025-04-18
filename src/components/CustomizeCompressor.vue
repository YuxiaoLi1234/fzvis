<template>
  <div class="container align-items-center" id="modals">

      <!-- 📌 Options panel -->
      <div class="options-panel px-2">
        <h1 class="h3 pt-3 pb-2">Available Options</h1>

        <div class="dropdown">
          <select id="compressor" class="form-select m-1 w-auto" aria-label="compressor" v-model="selectedCompressor" @change="handleCompressorChange">
            <option value=null disabled selected>Select compressor</option>
            <option v-for="compressor in availableCompressors" :key="compressor.id" :value="compressor.id">{{ compressor.label }}</option>
          </select>
        </div>

        <div v-if="selectedCompressor" class="pt-2">
          <div class="card">
            <div class="card-body" v-if="this.selectedCompressor in this.compressorOptions">
              <h5 class="card-title">{{ this.selectedCompressor }}</h5>
              <p class="card-text">Detailed options are listed here.</p>
              <div v-for="(optionList, optionName) in this.compressorOptions[this.selectedCompressor]" :key="optionName">
                <select class="form-select mb-2 me-2" :key="optionName" v-model="configuredValues[optionName]" aria-label="optionName">
                  <option value=null disabled selected>Select {{ optionName }}</option>
                  <option v-for="option in optionList" :key="option.id" :value="option">{{ option.label }}</option>
                </select>
                <input v-if="optionName === 'Error Bound' && configuredValues[optionName]" type="number" class="form-control w-auto mb-2" placeholder="Enter bound value" min="0" step="0.001" v-model="configuredValues[optionName].value">
              </div>
              <small class="d-block mb-2 text-muted">
                {{ isConfigValid ? 'Click submit to record configuration.' : 'Please fill all fields to submit.' }}
              </small>
              <button type="button" class="btn btn-primary me-2" :disabled="!isConfigValid" data-bs-toggle="modal" data-bs-target="#saveConfigModal">Submit</button>
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
      <div class="dropzone-panel p-2" @dragover.prevent @drop="onDrop">

        <!-- 📌 Current configurations -->
        <div class="dropped-item" v-for="(item, index) in droppedItems" :key="item.id">
          <span class="item-category">{{ item.type }}</span>
          <span>{{ item.label }}</span>

          <input 
            v-if="item.type === 'error bound'" 
            type="number" 
            v-model="item.value" 
            placeholder="Enter bound value" 
            class="error-input"
          />

          <button class="remove-button" @click="removeItem(index)">✖</button>
        </div>

        <div v-if="Object.keys(this.savedConfigurations).length < 2" class="text-info pb-2">
          There is <strong>{{ Object.keys(this.savedConfigurations).length }}</strong> saved configuration.
        </div>
        <div v-else class="text-info pb-2">
          There are <strong>{{ Object.keys(this.savedConfigurations).length }}</strong> saved configurations.
        </div>

        <div class="d-flex flex-wrap gap-2">
          <button type="button" class="btn btn-primary" @click="submitConfigurations" :disabled="Object.keys(savedConfigurations).length === 0">Submit Configurations</button>
          <button type="button" class="btn btn-secondary" :disabled="Object.keys(savedConfigurations).length === 0" data-bs-toggle="modal" data-bs-target="#showConfigModal">View Configurations</button>
        </div>
      </div>

      <!-- Show saved configuration modal -->
      <div id="showConfigModal" class="modal fade" tabindex="-1" aria-labelledby="showConfigModalLabel" data-bs-backdrop="static" data-bs-keyboard="false" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h1 class="modal-title fs-5" id="showConfigModalLabel">Saved configuration</h1>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
              <div v-for="(config, name) in savedConfigurations" :key="name" class="config-card">
                <h4>{{ name }}</h4>
                <ul v-if="editingConfig !== name">
                  <li><strong>Compressor:</strong> {{ config.compressor_id.toUpperCase() }}</li>
                  <li v-for="(value, key) in formatConfig(config.compressor_config)" :key="key">
                    <strong>{{ key }}:</strong> {{ value }}
                  </li>
                </ul>
                <ul v-else>
                  <li>
                    <strong>Compressor:</strong> {{ config.compressor_id.toUpperCase() }}
                  </li>
                  <li v-for="(value, key) in editingData.compressor_config" :key="key">
                    <strong>{{ get_formatkey(key) }}:</strong>
                    <input v-model="editingData.compressor_config[key]" class="edit-input" />
                  </li>
                </ul>
              </div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
              <button type="button" class="btn btn-primary">Edit configuration</button>
            </div>
          </div>
        </div>
      </div>


      <!-- 📌 已保存的配置 -->
      <div v-if="showModal" class="modal">
        <div class="modal-content">
          <h3>Saved Configurations</h3>
          
          <div v-for="(config, name) in savedConfigurations" :key="name" class="config-card">
            <h4 class="config-title">{{ name }}</h4>
            <ul v-if="editingConfig !== name">
              <li><strong>Compressor:</strong> {{ config.compressor_id.toUpperCase() }}</li>
              <li v-for="(value, key) in formatConfig(config.compressor_config)" :key="key">
                <strong>{{ key }}:</strong> {{ value }}
              </li>
            </ul>
            <ul v-else>
              <li>
                <strong>Compressor:</strong> {{ config.compressor_id.toUpperCase() }}
              </li>
              <li v-for="(value, key) in editingData.compressor_config" :key="key">
                <strong>{{ get_formatkey(key) }}:</strong>
                <input v-model="editingData.compressor_config[key]" class="edit-input" />
              </li>
            </ul>

            <div class="button-group">
              <!-- 🚀 编辑和保存按钮 -->
              <button class="edit-button" v-if="editingConfig !== name" @click="startEditing(name)">Edit</button>
              <button class="save-button" v-else @click="saveEdit(name)">Save</button>
              <button class="cancel-button" @click="cancelEdit()">Cancel</button>
            </div>
            <button class="delete-button" @click="deleteConfiguration(name)">Delete</button>
          </div>
          <button class="close-button" @click="closeModal">Close</button>
        </div>
      </div>
    </div>
</template>


<!-- <style scoped src="@/assets/CustomizeCompressor.css"></style> -->
<script>
import axios from 'axios'
import emitter from './eventBus.js';
import * as d3 from 'd3';

export default {
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
      currentConfigName: "", // 用户输入的配置名称
      savedConfigurations: {}, // 保存的所有配置对象
      droppedItems: [], // 当前配置的项目
      showModal: false, // 是否显示模态框
      selectedCompressor:null,
      editingConfig: null, // 当前正在编辑的配置名
      editingData: {}, // 编辑中的数据
      compare_data:{'compressor_id':[],'compressor_name':[],'bound':[],'metrics':[],'input_data':''},
      input_data:null,
      formattedConfigurations:null,
      formData: new FormData(),
      compressorParams:[],
      expandedCategories: []
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
      const options = this.compressorOptions[this.selectedCompressor];
      if (!options) return false;

      return Object.keys(options).every(optionName => {
        const config = this.configuredValues[optionName];
        if (!config?.id) return false;
        if (optionName === 'Error Bound') {
          return (
            config.value !== undefined && // Value exists
            config.value !== ''       // Not empty string
          );
        }
        
        return true; // Other fields only need id
      });
    },

    isSaveEnabled() {
      return (
        this.currentConfigName &&
        this.droppedItems.some((item) => item.label.startsWith("Error Bound:")) &&
        this.droppedItems.some((item) => item.label.startsWith("Compressor:")) 
        &&
        this.droppedItems.some(
          (item) =>
            item.label.startsWith("Error Bound:") &&
            item.value != null &&
            item.value > 0
        )
      );
    },

  },

  methods: {
    formatCategoryName(category) {
      return category
        .replace(/_/g, " ") // Replace underscores with spaces
        .replace("str", "") // Remove "str" suffix (if present)
        .replace(/\b\w/g, (char) => char.toUpperCase()); // Capitalize first letter of each word
    },

    resetConfiguredValues() {
      // Handle case where options already exist
      this.configuredValues = {};
      const options = this.compressorOptions[this.selectedCompressor];
      Object.keys(options).forEach(optionName => {
        this.configuredValues[optionName] = null;
      });
    },

    handleCompressorChange() {
      // Only send the request if options for the selected compressor haven't been fetched before
      if (!(this.selectedCompressor in this.compressorOptions)) {
        let formData = new FormData();
        formData.append("get_options", 1);
        formData.append("compressor_id", this.selectedCompressor);
        axios.post(`http://localhost:5003/indexlist`, formData)
        .then(response => {
          const rawOptions = response.data;
          const filteredOptions = {...Object.fromEntries(Object.entries(rawOptions).filter(([key]) => key.startsWith(this.selectedCompressor)))};

          let formattedOptions = {
            ...Object.entries(filteredOptions).reduce((acc, [category, values]) => {
              // remove `sz3:` prefix and `_str` suffix
              const formattedCategory = category.replace(`${this.selectedCompressor}:`, "").replace("_str", "").replace("_mode", "").replace("_algo", "");
              
              acc[this.formatCategoryName(formattedCategory)] = values.map(value => ({
                id: `${category}-${value}`,
                label: `${this.formatCategoryName(formattedCategory)}: ${value}`, // format label for display
                type: category
              }));
              return acc;
            }, {})
          };
          
          // Manually add error bound option if missing
          const hasErrorBound = Object.keys(formattedOptions).some(category => category.toLowerCase().includes("error bound"));
          if (!hasErrorBound) {
            formattedOptions["Error Bound"] = [{
              id: "pressio:abs",
              label: "Error Bound: ABS",
              type: "error bound"
            }];
          }

          Object.keys(formattedOptions).forEach(optionName => {
            this.configuredValues[optionName] = null;
          });
          this.compressorOptions[this.selectedCompressor] = formattedOptions;
          console.log("formattedOptions", formattedOptions);
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

    handleSaveConfiguration() {
      const config = {"compressor_config":{}};
      console.log("configuredValues", JSON.stringify(this.configuredValues));

      config.compressor_id = this.selectedCompressor;
      // 遍历 droppedItems，分类存入不同配置项
      Object.values(this.configuredValues).forEach((item) => {
          console.log(item.label, item.id)
          if (item.label.startsWith("Error Bound:")) {
              if(item.id.split(":")[0] != this.selectedCompressor){
                config["compressor_config"][item.id] = item.value
              }
              else{
                const errorMode = item.label.split(": ")[1];
                config["compressor_config"][`${this.selectedCompressor}:${errorMode.toLowerCase()}_error_bound`] = item.value;
              }
          }
          
          else if(!item.label.startsWith("Compressor:")) {
            console.log(item.id)
            config["compressor_config"][item.id.split("-")[0]]= item.id.split("-")[1];
          }
      });

      // Save current configuration
      // corrected config format:
      // savedConfig {"compressor_config":{"sz3:algorithm_str":"ALGO_INTERP","sz3:abs_error_bound":0.001,"sz3:intrep_algo_str":"INTERP_ALGO_CUBIC","sz3:metric":"composite"},"compressor_id":"sz3"}
      this.savedConfigurations[this.currentConfigName] = config;
      console.log("config", JSON.stringify(config));
      this.currentConfigName = "";
    },

    viewConfiguration() {
      d3.select("#modals").style("z-index", "200");
      this.showModal = true;
    },

    formatConfig(compressorConfig) {
      if (!compressorConfig) return {};

      const formattedConfig = {};
      Object.entries(compressorConfig).forEach(([key, value]) => {
        let formattedKey = key.replace(/^.*?:/, ""); // 移除 `sz3:` 或 `pressio:`
        formattedKey = formattedKey.replace(/_str$/, ""); // 移除 `_str` 后缀
        formattedKey = formattedKey.replace(/_mode$/, ""); // 移除 `_mode` 后缀
        formattedKey = formattedKey.replace(/_algo$/, ""); // 移除 `_algo` 后缀
        formattedKey = formattedKey.replace("_error_bound", " Error Bound"); // 处理 error bound 特殊格式
        formattedKey = formattedKey.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());

        formattedConfig[formattedKey] = value;
      });

      return formattedConfig;
    },

    get_formatkey(key){
      let formattedKey = key.replace(/^.*?:/, ""); // 移除 `sz3:` 或 `pressio:`
      formattedKey = formattedKey.replace(/_str$/, ""); // 移除 `_str` 后缀
      formattedKey = formattedKey.replace(/_mode$/, ""); // 移除 `_mode` 后缀
      formattedKey = formattedKey.replace(/_algo$/, ""); // 移除 `_algo` 后缀
      formattedKey = formattedKey.replace("_error_bound", " Error Bound"); // 处理 error bound 特殊格式
      formattedKey = formattedKey.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());


      return formattedKey;
    },

    startEditing(name) {
      console.log("Editing:", name);
      this.editingConfig = name;
      this.editingData = JSON.parse(JSON.stringify(this.savedConfigurations[name])); // 深拷贝，防止直接修改原数据
    },

    saveEdit(name) {
      console.log("Saving:", name, this.editingData);
      
      // 更新 Vue 状态
      this.savedConfigurations[name] = JSON.parse(JSON.stringify(this.editingData));
      this.cancelEdit();
      // // 提交修改到后端
      // let formData = new FormData();
      // formData.append("edit_config", 1);
      // formData.append("config_name", name);
      // formData.append("updated_config", JSON.stringify(this.savedConfigurations[name]));

      // axios.post("http://localhost:5003/edit_config", formData)
      //   .then(response => {
      //     console.log("Update Success:", response.data);
      //   })
      //   .catch(error => {
      //     console.error("Error updating configuration:", error.response ? error.response.data : error.message);
      //     alert("An error occurred. Please check the console for details.");
      //   });

      // this.cancelEdit();
    },

    cancelEdit() {
      this.editingConfig = null;
      this.editingData = {};
    },

    deleteConfiguration(name) {
      if (confirm(`Are you sure you want to delete the configuration "${name}"?`)) {
        delete this.savedConfigurations[name]; // 直接删除对象属性
        this.savedConfigurations = { ...this.savedConfigurations }; // 重新赋值触发 Vue 响应式更新
      }
    },

    closeModal() {
      d3.select("#modals").style("z-index", "100");
      this.showModal = false;
      
    },

    submitConfigurations() {
      console.log("In function submitConfigurations()");
      const formattedConfigurations = Object.entries(this.savedConfigurations).map(([name, config]) => {
        console.log(name, config)
        
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
      
      axios.post(`http://localhost:5003/indexlist`, this.formData).then(response => {
        const names = Object.values(formattedConfigurations).map((d)=>d.compressor_name);
        const configs = Object.values(formattedConfigurations).map((d)=>d.compressor_config);
        console.log("response: ", response.data)
        for(const key in response.data) {
          let element = response.data[key]
          console.log(element,key)

          if(key=='input_data') continue;
          if(key=='decp_data') continue;
          
          this.compare_data['compressor_id'].push(response.data[key]['compressor_id']);
          this.compare_data['bound'].push(element['bound']);
          if (element['metrics']) {
            this.compare_data['metrics'].push(element['metrics']);
          } else {
            console.warn("Metrics returned from the backend are null or undefined.");
          }
        }
          
        this.input_data = response.data['input_data']
        this.compare_data['compressor_name'] = names
        this.compare_data['compressor_config'] = configs
        // document.getElementById('temp1').innerHTML = JSON.stringify(this.compare_data);
        emitter.emit('myEvent', this.compare_data);
        emitter.emit('inputdata', {"input_data":this.input_data, "width": this.width, "height":this.height, "depth":this.depth,"compressor_name":names, "decp_data": response.data['decp_data']});
        emitter.emit('compressor_configuration', this.savedConfigurations);
      }).catch(error => {
        console.error('Error submitting configuration:', error.response ? error.response.data : error.message);
        alert('An error occurred. Please check the console for details.');
      });
      
      return formattedConfigurations;
    },
    
    toggleCategory(categoryName) {
      if (this.expandedCategories.includes(categoryName)) {
        this.expandedCategories = this.expandedCategories.filter(c => c !== categoryName);
      } else {
        this.expandedCategories.push(categoryName);
      }
    },

    resetAvailableOptions() {
      this.availableOptions = [...this.initialOptions]; // 还原原始选项
    },

  },

  mounted() {
    // this.resetAvailableOptions();
    // this.availableOptions = [...this.initialCompressorOptions];
    emitter.on('file-selected', (data) => {
          console.log("datamounted", data);
          this.formData = new FormData();
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
