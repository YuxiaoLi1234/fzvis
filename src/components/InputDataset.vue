<template>
  <div id="input-dataset">
      <div id="input-dataset-container">
      <h3>Upload Input Dataset</h3>
      <input type="file" id="fileloader" @change="handleFileChange">
      <div id="whd" class="input-section">
      <!-- <t-input id='width' label="width:" v-model="width" placeholder=500 @input="emitFileData" class="input-field"/>
      <t-input id='height' label="height:" v-model="height" placeholder=500 @input="emitFileData" class="input-field"/>
      <t-input id='depth' label="depth:" v-model="depth" placeholder=1 @input="emitFileData" class="input-fielddepth"/>
      <t-input id='precision' label="precision:" v-model="precision" placeholder="d" @input="emitFileData" class="input-field"/> -->
      <t-input id='width' label="width:" v-model="width" placeholder=500 class="input-field"/>
      <t-input id='height' label="height:" v-model="height" placeholder=500 class="input-field"/>
      <t-input id='depth' label="depth:" v-model="depth" placeholder=1 class="input-fielddepth"/>
      <t-input id='precision' label="precision:" v-model="precision" placeholder="d" class="input-field"/>
      </div>

      <!-- Add a button for emitting the data -->
      <t-button class= "submit-button-input" @click="emitFileData" :disabled="!isFormValid">Submit</t-button>

      
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
  depth:null,
  width:null,
  height:null,
  precision:null,
  fileContent:"",
  formData: new FormData(),
  files:[],
  infoMessage:'',
  file:'',
  uploadMethod: 'requestSuccessMethod',
  };
},
// computed: {
//     // Check if all form fields are filled before allowing emission
//     isFormValid() {
//       return this.file && this.width && this.height && this.depth && this.precision;
//     },
//   },
methods:{
handleFileChange(event){
  
  const file = event.target.files[0]; 
  if(this.formData.has('file')){
    this.formData.delete("file");
  }
  this.formData.append("file", file);
  this.fileContent = file.name;
  this.file = file;
  //this.emitFileData();
},

emitFileData() {
      // if (this.file && this.width && this.height && this.depth && this.precision) {
      if(this.isFormValid) {
        console.log("Emitting file data:", this.fileContent, this.width, this.height, this.depth);
        emitter.emit('file-selected', {
          file: this.file,
          width: this.width,
          height: this.height,
          depth: this.depth,
          precision: this.precision
        });
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
 
