<template>
  <div class="container-wrapper" id="modals">
    <div class="drag-drop-container">
      <!-- 📌 左侧可选项 -->
       
      <div class="options-panel">
        <h3>Available Options</h3>

        <div 
          v-for="(categoryOptions, categoryName) in categorizedOptions"
          :key="categoryName"
        >
        <div class="category-header" @click="toggleCategory(categoryName)">
          {{ categoryName }} ▾
        </div>

      <transition name="fade">
        <div v-if="expandedCategories.includes(categoryName)" class="category-options">
          <div 
            class="draggable-item"
            v-for="option in categoryOptions"
            :key="option.id"
            draggable="true"
            @dragstart="onDragStart(option)"
          >
            {{ option.label }}
          </div>
        </div>
      </transition>
    </div>


      </div>

      <!-- 📌 右侧配置区域 -->
      <div class="dropzone-panel" @dragover.prevent @drop="onDrop">
        <h3>Current Configuration</h3>

        <div class="config-name-row">
          <span>Configuration Name:</span>
          <input v-model="currentConfigName" type="text" placeholder="Enter configuration name" class="config-name-input" />
        </div>

        <!-- 📌 当前已选配置 -->
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

        <div class="button-group">
          <button class="save-button" @click="saveConfiguration" :disabled="!isSaveEnabled">Save Configuration</button>
          <button class="submit-button" @click="submitConfigurations" :disabled="Object.keys(savedConfigurations).length === 0">Submit All Configurations</button>
          <button class="view-button" @click="viewConfiguration" :disabled="Object.keys(savedConfigurations).length === 0">View Configurations</button>
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
  </div>
</template>




<style scoped src="@/assets/CustomizeCompressor.css"></style>
<script>
import axios from 'axios'
import emitter from './eventBus.js';
import * as d3 from 'd3';

export default {
  data() {
    return {
      // selectedCompressor: null, // 当前选中的 compressor
      availableOptions: { 
        "Compressor": [
          { id: "sz3", label: "Compressor: SZ3", type: "compressor" },
          { id: "zfp", label: "Compressor: ZFP", type: "compressor" }
        ]
      },
      sz3Options: {
        algorithm_str: ["ALGO_INTERP", "ALGO_INTERP_LORENZO", "ALGO_LORENZO_REG"],
        error_bound_mode_str: ["ABS", "ABS_AND_REL", "ABS_OR_REL", "NORM", "PSNR", "REL"],
        intrep_algo_str: ["INTERP_ALGO_CUBIC", "INTERP_ALGO_LINEAR"]
      },
    //   compressorOptions: { 
    //   sz3: {
    //     algorithm_str: ["ALGO_INTERP", "ALGO_INTERP_LORENZO", "ALGO_LORENZO_REG"],
    //     error_bound_mode_str: ["ABS", "ABS_AND_REL", "ABS_OR_REL", "NORM", "PSNR", "REL"],
    //     intrep_algo_str: ["INTERP_ALGO_CUBIC", "INTERP_ALGO_LINEAR"]
    //   },
    //   zfp: {
    //     mode: ["fixed-accuracy", "fixed-rate", "fixed-precision"],
    //     compressionType: ["lossless", "near-lossless", "lossy"]
    //   }
    // },
    initialOptions:{
      "Compressor": [
          { id: "sz3", label: "Compressor: SZ3", type: "compressor" },
          { id: "zfp", label: "Compressor: ZFP", type: "compressor" }
        ]
    },
    compressorOptions: {
        sz3: {
          algorithm: ["ALGO_INTERP", "ALGO_INTERP_LORENZO", "ALGO_LORENZO_REG"],
          error_mode: ["ABS", "ABS_AND_REL", "ABS_OR_REL", "NORM", "PSNR", "REL"],
          intrep_algo: ["INTERP_ALGO_CUBIC", "INTERP_ALGO_LINEAR"]
        }
      },
      droppedItems: [], // 当前配置的项目
      currentConfigName: "", // 用户输入的配置名称
      savedConfigurations: {}, // 保存的所有配置对象
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

    categorizedOptions() {
      if (!this.availableOptions || Object.keys(this.availableOptions).length === 0) {
      return { "Compressor": this.availableOptions["compressor"] || [] };
    }
    return Object.keys(this.availableOptions).reduce((acc, category) => {
      acc[this.formatCategoryName(category)] = this.availableOptions[category] || [];
      return acc;
    }, {});
    }
  },
  methods: {
    formatCategoryName(category) {
    return category
      .replace(/_/g, " ") // Replace underscores with spaces
      .replace("str", "") // Remove "str" suffix (if present)
      .replace(/\b\w/g, (char) => char.toUpperCase()); // Capitalize first letter of each word
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

    loadCompressorOptions(compressor) {
      
      if (compressor === "SZ3") {
        this.compressorParams = [
          ...this.sz3Options.algorithm_str.map(option => ({ label: `Algorithm: ${option}`, type: "algorithm" })),
          ...this.sz3Options.error_bound_mode_str.map(option => ({ label: `Error Bound Mode: ${option}`, type: "error_mode" })),
          ...this.sz3Options.intrep_algo_str.map(option => ({ label: `Interp Algo: ${option}`, type: "interp_algo" })),
        ];
      } else {
        this.compressorParams = [];
      }
    },
    onDragStart(option) {
      event.dataTransfer.setData("text", JSON.stringify(option));
    },
    // onDrop() {
    //   const data = JSON.parse(event.dataTransfer.getData("text"));

    //   // 处理 Error Bound 类型
    //   if (data.label.startsWith("Error Bound:")) {
    //     const existingIndex = this.droppedItems.findIndex((item) =>
    //       item.label.startsWith("Error Bound:")
    //     );
    //     if (existingIndex !== -1) {
    //       this.droppedItems.splice(existingIndex, 1, { ...data, value: null });
    //     } else {
    //       this.droppedItems.push({ ...data, value: null });
    //     }
    //   }
    //   // 处理 Compressor 类型
    //   else if (data.label.startsWith("Compressor:")) {
    //     const existingIndex = this.droppedItems.findIndex((item) =>
    //       item.label.startsWith("Compressor:")
    //     );
    //     if (existingIndex !== -1) {
    //       this.droppedItems.splice(existingIndex, 1, data);
    //     } else {
    //       this.droppedItems.push(data);
    //     }
    //     this.selectedCompressor = data.label.split(":")[1]
    //     this.loadCompressorOptions(this.selectedCompressor);

    //     // 🔹 清除之前的 compressor，保证只有一个
    //     this.droppedItems = this.droppedItems.filter(item => item.type !== "compressor");
        
    //   }
    // },
    onDrop(event) {
      const data = JSON.parse(event.dataTransfer.getData("text"));
      // const categoryPrefix = data.label.split(":")[0].trim(); // 提取类别（如 "Error Bound Mode"）

      if (data.type === "compressor") {
        this.selectedCompressor = data.id;
        console.log(this.droppedItems)
        const existingIndex = this.droppedItems.findIndex((item) =>
          item.label.startsWith("Compressor:")
        );
        if (existingIndex !== -1) {
          this.droppedItems.splice(existingIndex, 1, data);
        } else {
          this.droppedItems.push(data);
        }
        
        // this.loadCompressorOptions(this.selectedCompressor);

        // 🔹 清除之前的 compressor，保证只有一个
        // this.droppedItems = this.droppedItems.filter(item => item.type !== "compressor");

        // const newOptions = Object.entries(this.compressorOptions[this.selectedCompressor])
        //   .flatMap(([key, values]) => values.map(value => ({
        //     id: `${this.selectedCompressor}-${key}-${value}`,
        //     label: `${key.replace("_str", "").replace(/_/g, " ")}: ${value}`,
        //     type: key
        //   })));
        // console.log(newOptions)
        // 🔹 确保其他 compressor 选项仍然存在
        // this.availableOptions = [...newOptions];f
        let formData = new FormData();
        formData.append("get_options", 1);
        formData.append("compressor_id", data.id);
        axios.post(`http://localhost:5003/indexlist`, formData).then(response => {
              
              const rawOptions = response.data
              const filteredOptions = { 
              ...Object.fromEntries(
                Object.entries(rawOptions).filter(([key]) => key.startsWith(data.id))
              )
            };

            this.availableOptions = {
                "Compressor": this.availableOptions["Compressor"], // 保留 compressor 选项
                ...Object.entries(filteredOptions).reduce((acc, [category, values]) => {
                  // **移除 `sz3:` 前缀，去掉 `_str` 后缀**
                  const formattedCategory = category.replace(`${data.id}:`, "").replace("_str", "").replace("_mode", "").replace("_algo", "");
                  
                  acc[this.formatCategoryName(formattedCategory)] = values.map(value => ({
                    id: `${category}-${value}`,
                    label: `${this.formatCategoryName(formattedCategory)}: ${value}`, // **格式化 Label**
                    type: category
                  }));
                  return acc;
                }, {})
              };

              const hasErrorBound = Object.keys(this.availableOptions).some(category =>
                category.toLowerCase().includes("error bound")
              );

              if (!hasErrorBound) {
                this.availableOptions["Error Bound"] = [{
                  id: "pressio:abs",
                  label: "Error Bound: ABS",
                  type: "error bound"
                }];
              }

            
    }).catch(error => {
            
            console.error('Error submitting configuration:', error.response ? error.response.data : error.message);
            alert('An error occurred. Please check the console for details.');
        });
      }
      
      // 处理其他类型的选项（如 error mode, algorithm 等）
      else {
        // **去掉 `sz3:` 前缀和 `_str` 后缀**
        console.log(this.selectedCompressor)
        console.log(data)
        const formattedType = data.type.replace(`${this.selectedCompressor}:`, "").replace("_str", "").replace("_mode", "").replace("_algo", "").replace("_", " ");
        const formattedLabel = data.label.replace(`${this.selectedCompressor}:`, "").replace("_str", "").replace("_mode", "").replace("_algo", "").replace("_", " ");
        console.log(data, formattedLabel)
        // **替换相同类别的配置**
        const existingIndex = this.droppedItems.findIndex(item => item.type === formattedType);
        if (existingIndex !== -1) {
          this.droppedItems.splice(existingIndex, 1, { ...data, label: formattedLabel, type: formattedType });
        } else {
          this.droppedItems.push({ ...data, label: formattedLabel, type: formattedType });
        }
        console.log(this.droppedItems)
      }
    },
    parseOptions(filteredOptions) {
      const categorizedOptions = {};

      for (const [key, values] of Object.entries(filteredOptions)) {
        // 提取分类名称，例如 "sz3:algorithm_str" -> "Algorithm"
        const category = key.split(":")[1].replace(/_/g, " ").replace("str", "").trim();

        if (!categorizedOptions[category]) {
          categorizedOptions[category] = [];
        }

        // 将选项添加到对应类别
        categorizedOptions[category].push(
          ...values.map(value => ({
            id: `${key}-${value}`,
            label: `${category}: ${value}`,
            type: key
          }))
        );
    }

    return categorizedOptions;
  },



    
  removeItem(index) {
    const removedItem = this.droppedItems.splice(index, 1)[0];

    // **如果移除的是 Compressor，则重置 availableOptions**
    if (removedItem.type === "compressor") {
      this.selectedCompressor = null;
      this.resetAvailableOptions();
    }
  },
  saveConfiguration() {
    if (!this.isSaveEnabled) return;

    const config = {"compressor_config":{}};
    console.log(this.droppedItems);

    // 获取当前 compressor_id
    const compressorItem = this.droppedItems.find(item => item.label.startsWith("Compressor:"));
    if (!compressorItem) {
        console.error("Compressor is missing!");
        return;
    }
    const compressor_id = compressorItem.label.split(": ")[1].toLowerCase();
    config.compressor_id = compressor_id; // 设定 compressor_id
    console.log(compressor_id)
    // 遍历 droppedItems，分类存入不同配置项
    this.droppedItems.forEach((item) => {
        console.log(item.label, item.id)
        if (item.label.startsWith("Error Bound:")) {
            
            console.log(item.label)
            if(item.id.split(":")[0] != compressor_id){
              config["compressor_config"][item.id] = item.value
            }
            else{
              const errorMode = item.label.split(": ")[1];
              config["compressor_config"][`${compressor_id}:${errorMode.toLowerCase()}_error_bound`] = item.value;
            }
            // config[`${compressor_id}:error_bound_mode_str`] = errorMode; // 记录 error bound mode
            // config[`${compressor_id}:${errorMode.toLowerCase()}_error_bound`] = item.value; // 记录对应 error bound 值
             // 记录对应 error bound 值
        } 
        
          
        else if(!item.label.startsWith("Compressor:")) {
          console.log(item.id)
          config["compressor_config"][item.id.split("-")[0]]= item.id.split("-")[1];
        }
        // config[`${compressor_id}_algorithm_str`] = item.label.split(": ")[1];

    });

    // 保存配置
    this.savedConfigurations[this.currentConfigName] = config;
    console.log(config)
    // 清空当前配置和名字
    this.droppedItems = [];
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
        const formattedConfigurations = Object.entries(this.savedConfigurations).map(
          ([name, config]) => {
            console.log(name, config)
            

            return {
              // 配置 compressor_id
              compressor_id: config.compressor_id || "unknown",
              compressor_name: name,
              // 配置 early_config
              early_config: {
                "pressio:metric": "composite",
                "composite:plugins": ["time", "size", "error_stat"],
              },

              // 配置 compressor_config
              compressor_config: config["compressor_config"],
            };
          }
        );

        // 打印结果或传递到后端
        if(this.formData.has("configurations")){
            this.formData.delete("configurations");
        }

        if(this.formData.has("get_options")){
            this.formData["get_options"] = 0;
        }
        else this.formData.append("get_options", 0);
        this.formData.append("configurations",JSON.stringify(formattedConfigurations));
        
        console.log("Formatted Configurations:", formattedConfigurations);
        axios.post(`http://localhost:5003/indexlist`, this.formData).then(response => {
              // let cnt = 0;
              const names = Object.values(formattedConfigurations).map((d)=>d.compressor_name);
              const configs = Object.values(formattedConfigurations).map((d)=>d.compressor_config);
              console.log("response: ", response.data)
              for(const key in response.data)
              {
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
      }
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



  
  