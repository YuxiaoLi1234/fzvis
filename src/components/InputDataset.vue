<template>
  <div id="input-dataset">
    <h3>Upload Input Dataset</h3>
    
    <div id="input-dataset-container">
      <input type="file" id="fileloader" @change="handleFileChange">
      <t-button class="submit-button-input" @click="emitFileData" :disabled="!isFormValid">Submit</t-button>
      <div id="whd" class="input-section">
        <t-input id='width' label="width:" v-model="width" placeholder=500 class="input-field"/>
        <t-input id='height' label="height:" v-model="height" placeholder=500 class="input-field"/>
        <t-input id='depth' label="depth:" v-model="depth" placeholder=1 class="input-field"/>
        <t-input id='precision' label="precision:" v-model="precision" placeholder="d" class="input-field"/>
      </div>
    </div>

    
    <t-button class="view-datasets-button" @click="toggleDataPanel">View Uploaded Datasets</t-button>

    <!-- 数据面板（弹出窗口） -->
    <div v-if="showDataPanel" id="data-panel">
      <div class="data-panel-header">
        <h3>Saved Datasets</h3>
        <button @click="toggleDataPanel" class="close-button">❌</button>
      </div>
      <ul>
        <li v-for="dataset in uploadedDatasets" :key="dataset.id">
          <span @click="restoreDataset(dataset)" class="dataset-item">{{ dataset.name }}</span>
          <button @click="deleteDataset(dataset.id)" class="delete-button">❌</button>
        </li>
      </ul>
    </div>

  </div>
</template>
<style scoped>
@import "@/assets/InputDataset.css";
</style>
<script>
import emitter from './eventBus.js';
export default {
  name: 'InputDataset',
  data() {
    return {
      depth: null,
      width: null,
      height: null,
      precision: null,
      fileContent: "",
      formData: new FormData(),
      files: [],
      file: '',
      uploadedDatasets: [], 
      showDataPanel: false, // 控制弹窗显示
    };
  },
  methods:{
    handleFileChange(event) {
      const newFile = event.target.files[0];
      if (newFile) {
        this.file = newFile;
        
        const reader = new FileReader();
        reader.onload = (e) => {
          this.fileContent = e.target.result; // 存储文件数据
        };

        reader.readAsArrayBuffer(newFile); // 读取二进制数据
      }
    },
    emitFileData() {
      const dataset ={
        file: this.file,
        width: this.width,
        height: this.height,
        depth: this.depth,
        precision: this.precision
        
      };
      

      if (dataset.file && dataset.width && dataset.height && dataset.depth && dataset.precision) {
        // 生成唯一ID
        const datasetId = `${this.file.name}-${Date.now()}`;

        // 记录到数据面板
        
        this.uploadedDatasets.push({
          id: datasetId,
          name: this.file.name,
          width: this.width,
          height: this.height,
          depth: this.depth,
          precision: this.precision,
          file: this.file,
          content: this.fileContent
        });
        
        console.log("Uploaded Datasets:", this.uploadedDatasets);
        console.log("Emitting file data:", dataset);
        emitter.emit('file-selected', dataset);
        emitter.emit('file-input',  this.uploadedDatasets[this.uploadedDatasets.length - 1]);
        this.$message.success('Dataset emitted successfully!');
      } else {
        this.$message.error('Please fill in all fields before submitting.');
      }
    },
    requestSuccessMethod(file /* UploadFile */) {
      console.log(file, file.raw);
      return new Promise((resolve) => {
        let percent = 0;
        const percentTimer = setInterval(() => {
          if (percent + 10 < 99) {
            percent += 10;
            this.$refs.uploadRef.uploadFilePercent({ file, percent });
            
          } else {
            clearInterval(percentTimer);
          }
        }, 100);

        const timer = setTimeout(() => {
          resolve({ status: 'success', response: { url: 'https://tdesign.gtimg.com/site/avatar.jpg' } });

          clearTimeout(timer);
          clearInterval(percentTimer);
        }, 800);
        console.log(resolve)
        
      });
    },
    requestFailMethod(file ) {
      console.log(file);
      return new Promise((resolve) => {
        resolve({ status: 'fail', error: '上传失败，请检查文件是否符合规范' });
      });
    },
    restoreDataset(dataset) {
      this.file = dataset.file;
      this.fileContent = dataset.name;
      this.width = dataset.width;
      this.height = dataset.height;
      this.depth = dataset.depth;
      this.precision = dataset.precision;

      console.log("Restored dataset:", dataset);
    },


    deleteDataset(datasetId) {
      this.uploadedDatasets = this.uploadedDatasets.filter(dataset => dataset.id !== datasetId);
      console.log("Deleted dataset:", datasetId);
    },

    toggleDataPanel() {
      this.showDataPanel = !this.showDataPanel;
    }
  },
  computed: {
    requestMethod() {
      return this[this.uploadMethod];
    },
    //Check if all form fields are filled before allowing emission
        isFormValid() {
          return this.file && this.width && this.height && this.depth && this.precision;
        },
  },
  watch: {
    uploadMethod() {
        this.files = [];
    },
    },
};
</script>
 
