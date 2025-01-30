<template>
  <div class="container-wrapper" id = "modals">
  <div class="drag-drop-container">
    <!-- 左侧可选项 -->
    <div class="options-panel">
      <h3>Available Options</h3>
      <div
        class="draggable-item"
        v-for="option in availableOptions"
        :key="option.id"
        draggable="true"
        @dragstart="onDragStart(option)"
      >
        {{ option.label }}
      </div>
    </div>

    <!-- 右侧配置区域 -->
    <div
      class="dropzone-panel"
      @dragover.prevent
      @drop="onDrop"
    >
      <h3>Current Configuration</h3>

      <!-- 配置名字输入框 -->
      <div class="config-name-row">
        <span>Configuration Name:</span>
        <input
          v-model="currentConfigName"
          type="text"
          placeholder="Enter configuration name"
          class="config-name-input"
        />
      </div>

      <!-- 当前配置项 -->
      <div
        class="dropped-item"
        v-for="(item, index) in droppedItems"
        :key="item.id"
      >
        <span>{{ item.label }}</span>
        <input
          v-if="item.label.startsWith('Error Bound:')"
          type="number"
          v-model="item.value"
          placeholder="Enter value"
          class="error-input"
        />
        <button class="remove-button" @click="removeItem(index)">✖</button>
      </div>

      <!-- 保存和查看按钮 -->
      <div class="button-group">
        <button
          class="save-button"
          @click="saveConfiguration"
          :disabled="!isSaveEnabled"
        >
          Save Configuration
        </button>

        <button 
          class="submit-button" 
          @click="submitConfigurations" 
          :disabled="Object.keys(savedConfigurations).length === 0"
        >
          Submit All Configurations
        </button>

        <button
          class="view-button"
          @click="viewConfiguration"
          :disabled="Object.keys(savedConfigurations).length === 0"
        >
          View Configurations
        </button>
      </div>
    </div>

    <!-- 模态框显示已保存的配置 -->
    <div v-if="showModal" class="modal">
    <div class="modal-content">
      <h3>Saved Configurations</h3>
      <!-- 配置卡片 -->
      <div v-for="(config, name) in savedConfigurations" :key="name" class="config-card">
        <h4 class="config-title">{{ name }}</h4>
        <ul v-if="!editingConfig || editingConfig !== name" class="config-details">
          <li><strong>Error Bound Type:</strong> {{ config.error_bound.toUpperCase() }}</li>
          <li><strong>Bound Value:</strong> {{ config.bound }}</li>
          <li><strong>Compressor Type:</strong> {{ config.compressor_id.toUpperCase() }}</li>
          <button class="edit-button" @click="startEditing(name)">Edit</button>
        </ul>

        <!-- 编辑模式 -->
        <div v-else class="edit-panel">
          <label>
            Error Bound Type:
            <select v-model="editingData.error_bound">
              <option value="abs">ABS</option>
              <option value="rel">REL</option>
            </select>
          </label>
          <label>
            Bound Value:
            <input type="number" v-model="editingData.bound" placeholder="Enter value" />
          </label>
          <label>
            Compressor Type:
            <select v-model="editingData.compressor_id">
              <option value="sz3">SZ3</option>
              <option value="zfp">ZFP</option>
            </select>
          </label>
          <div class="edit-actions">
            <button @click="saveEdit(name)">Save</button>
            <button @click="cancelEdit">Cancel</button>
          </div>
        </div>
      </div>

      <!-- 关闭按钮 -->
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
      availableOptions: [
        { id: 3, label: "Compressor: SZ3" },
        { id: 4, label: "Compressor: ZFP" },
        { id: 1, label: "Error Bound: abs" },
        { id: 2, label: "Error Bound: rel" },
        
      ],
      droppedItems: [], // 当前配置的项目
      currentConfigName: "", // 用户输入的配置名称
      savedConfigurations: {}, // 保存的所有配置对象
      showModal: false, // 是否显示模态框

      editingConfig: null, // 当前正在编辑的配置名
      editingData: {}, // 编辑中的数据
      compare_data:{'compressor_id':[],'compressor_name':[],'bound':[],'metrics':[],'input_data':''},
      input_data:null,
      formattedConfigurations:null,
      formData: new FormData(),
    };
  },
  computed: {
    isSaveEnabled() {
      return (
        this.currentConfigName &&
        this.droppedItems.some((item) => item.label.startsWith("Error Bound:")) &&
        this.droppedItems.some((item) => item.label.startsWith("Compressor:")) &&
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
    onDragStart(option) {
      event.dataTransfer.setData("text", JSON.stringify(option));
    },
    onDrop() {
      const data = JSON.parse(event.dataTransfer.getData("text"));

      // 处理 Error Bound 类型
      if (data.label.startsWith("Error Bound:")) {
        const existingIndex = this.droppedItems.findIndex((item) =>
          item.label.startsWith("Error Bound:")
        );
        if (existingIndex !== -1) {
          this.droppedItems.splice(existingIndex, 1, { ...data, value: null });
        } else {
          this.droppedItems.push({ ...data, value: null });
        }
      }
      // 处理 Compressor 类型
      else if (data.label.startsWith("Compressor:")) {
        const existingIndex = this.droppedItems.findIndex((item) =>
          item.label.startsWith("Compressor:")
        );
        if (existingIndex !== -1) {
          this.droppedItems.splice(existingIndex, 1, data);
        } else {
          this.droppedItems.push(data);
        }
      }
    },
    removeItem(index) {
      this.droppedItems.splice(index, 1);
    },
    saveConfiguration() {
      if (!this.isSaveEnabled) return;

      const config = {};
      this.droppedItems.forEach((item) => {
        if (item.label.startsWith("Error Bound:")) {
          config.error_bound = item.label.split(": ")[1].toLowerCase();
          config.bound = item.value;
        } else if (item.label.startsWith("Compressor:")) {
          config.compressor_id = item.label.split(": ")[1].toLowerCase();
        }
      });

      this.savedConfigurations[this.currentConfigName] = config;

      // 清空当前配置和名字
      this.droppedItems = [];
      this.currentConfigName = "";
    },
    viewConfiguration() {
      d3.select("#modals").style("z-index", "200");
      this.showModal = true;
      
    },

    formatSavedConfigurations() {
      return Object.entries(this.savedConfigurations).map(([name, config]) => {
        const errorBoundType = config.error_bound.toUpperCase();
        const errorBoundValue = config.bound;
        const compressorType = config.compressor_id.toUpperCase();

        return `${name}: error bound (${errorBoundType}): ${errorBoundValue}, compressor type: ${compressorType}`;
      });
    },

    startEditing(name) {
    this.editingConfig = name;
    this.editingData = { ...this.savedConfigurations[name] }; // 深拷贝数据进行编辑
    },
    saveEdit(name) {
      this.savedConfigurations[name] = { ...this.editingData }; // 直接更新配置
      this.cancelEdit();
    },
    cancelEdit() {
      this.editingConfig = null;
      this.editingData = {};
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
              compressor_config: {
                ["pressio:"+config.error_bound]: config.bound,
              },
            };
          }
        );

        // 打印结果或传递到后端
        if(this.formData.has("configurations")){
            this.formData.delete("configurations");
        }
        this.formData.append("configurations",JSON.stringify(formattedConfigurations));
        console.log("Formatted Configurations:", formattedConfigurations);
        axios.post(`http://localhost:5002/indexlist`, this.formData)
            .then(response => {
              // let cnt = 0;
              const names = Object.values(formattedConfigurations).map((d)=>d.compressor_name);
              console.log("names:",names)
              for(const key in response.data)
              {
                  let element = response.data[key]
                  console.log(element,key)

                  if(key=='input_data') continue;
                  if(key=='decp_data') continue;
                  
                  
                  this.compare_data['compressor_id'].push(key);
                  this.compare_data['bound'].push(element['bound']);
                  if (element['metrics']) {
                      this.compare_data['metrics'].push(element['metrics']);
                  } else {
                      console.warn("Metrics returned from the backend are null or undefined.");
                  }
                }
                
                this.input_data = response.data['input_data']
                this.compare_data['compressor_name'] = names
                // document.getElementById('temp1').innerHTML = JSON.stringify(this.compare_data);
                emitter.emit('myEvent', this.compare_data);
                emitter.emit('inputdata', {"input_data":this.input_data, "width": this.width, "height":this.height, "depth":this.depth,"compressor_name":names, "decp_data": response.data['decp_data']});
              
          })
          .catch(error => {
              
              console.error('Error submitting configuration:', error.response ? error.response.data : error.message);
              alert('An error occurred. Please check the console for details.');
          });
        
        return formattedConfigurations;
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



  
  