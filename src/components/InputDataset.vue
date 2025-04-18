<template>
  <div class="container align-items-center">
    <h1 class="h3 px-2 pt-3 pb-2">Dataset Settings</h1>
    
    <input type="file" class="form-control" id="fileloader" @change="handleFileChange">

    <div id="whd" class="row g-3 py-2">
      <div class="col-md-4">
        <label for="width" class="form-label mx-1 mb-0">Width:</label>
        <input class="form-control" type="number" min="1" id="width" label="width:" v-model="width" placeholder="500" />
      </div>
      <div class="col-md-4">
        <label for="height" class="form-label mx-1 mb-0">Height:</label>
        <input class="form-control" type="number" min="1" id="height" label="height:" v-model="height" placeholder="500" />
      </div>
      <div class="col-md-4">
        <label for="depth" class="form-label mx-1 mb-0">Depth:</label>
        <input class="form-control" type="number" min="1" id="depth" label="depth:" v-model="depth" placeholder="500" />
      </div>
      <label for="precision" class="form-label col-md-3 pt-2 mt-1 ms-1">Precision:</label>
      <div class="col-md-6 pt-1 mt-0 pb-0">
        <select id="precision" class="form-select m-1 w-auto" aria-label="precision" v-model="precision">
          <option value="" disabled selected>select value</option>
          <option value="f">single (f)</option>
          <option value="d">double (d)</option>
        </select>
      </div>
      <small v-if="isFormValid" class="py-0 mt-0 text-muted">Click submit button to upload the dataset.</small>
      <small v-else class="py-0 mt-0 text-muted">Please fill all fields to submit.</small>
    </div>
    <button type="button" class="btn btn-success me-2 mb-2" @click="emitFileData" :disabled="!isFormValid">Submit</button>
    <!-- Button trigger modal -->
    <button type="button" class="btn btn-info mb-2" data-bs-toggle="modal" data-bs-target="#datasetModal">View datasets</button>
    <div v-if="this.curDatasetIndex < 0" class="text-warning">
      No dataset selected for compression/visualization.
    </div>
    <div v-else-if="hasDatasets">
      Currently selected dataset: 
      <strong >{{ this.uploadedDatasets[this.curDatasetIndex].name }}</strong>
    </div>

    <!-- Dataset modal -->
    <div id="datasetModal" class="modal fade" tabindex="-1" aria-labelledby="datasetModalLabel" aria-hidden="true">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h1 class="modal-title fs-5" id="datasetModalLabel">Saved datasets</h1>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <ul v-if="hasDatasets">
              <li v-for="(dataset, index) in uploadedDatasets" :key="dataset.id">
                <span @click="restoreDataset(dataset)" class="dataset-item">{{ dataset.name }}</span>
                <button @click="deleteDataset(index)" class="btn-close" aria-label="Delete"></button>
              </li>
            </ul>
            <div v-else class="text-warning py-2">
              No saved datasets!
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
            <button type="button" class="btn btn-primary">Save changes</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>

// import emitter from './eventBus.js';
export default {
  name: 'InputDataset',
  data() {
    return {
      depth: null,
      width: null,
      height: null,
      precision: "",
      fileContent: "",
      files: [],
      file: '',
      uploadedDatasets: [],
      curDatasetIndex: -1,
    };
  },
  methods:{
    handleFileChange(event) {
      const newFile = event.target.files[0];
      if (newFile) {
        this.file = newFile;
        
        const reader = new FileReader();
        reader.onload = (e) => {
          this.fileContent = e.target.result; // save file content
        };

        reader.readAsArrayBuffer(newFile); // read binary data
      }
    },

    async emitFileData() {
      // Generate form data
      const formData = new FormData();
      formData.append("file", this.file);
      formData.append("width", this.width);
      formData.append("height", this.height);
      formData.append("depth", this.depth);
      formData.append("precision", this.precision);

      try {
        const baseURL = process.env.VUE_APP_API_BASE;
        const response = await fetch(`${baseURL}/upload`, {
          method: "POST",
          body: formData
        });

        const result = await response.json();
        if (response.ok) {
          alert("File uploaded successfully!");
          console.log("Server response:", result);
        } else {
          throw new Error(result.error || "Upload failed");
        }
      } catch (error) {
        console.error("Upload error:", error);
        alert(`Upload failed: ${error.message}`);
      }
      
      // Generate a unique ID for the dataset
      const datasetId = `${this.file.name}-${Date.now()}`;

      // Record the dataset information in the panel
      this.uploadedDatasets.unshift({
        id: datasetId,
        name: this.file.name,
        width: this.width,
        height: this.height,
        depth: this.depth,
        precision: this.precision,
        file: this.file,
        content: this.fileContent
      });
      
      this.curDatasetIndex = 0;
      // console.log("Uploaded Datasets:", this.uploadedDatasets);
      // console.log("Emitting file data:", dataset);
      // emitter.emit('file-selected', dataset);
      // emitter.emit('file-input', this.uploadedDatasets[0]);
      // alert('Dataset emitted successfully!');
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

    requestFailMethod(file) {
      console.log(file);
      return new Promise((resolve) => {
        resolve({ status: 'fail', error: 'Upload failed, please double check the file!' });
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

    deleteDataset(index) {
      this.uploadedDatasets.splice(index, 1);
      if (this.curDatasetIndex == index) this.curDatasetIndex = -1;
      console.log("Deleted dataset index:", index);
    },
  },
  computed: {
    hasDatasets() {
      return this.uploadedDatasets.length > 0;
    },

    requestMethod() {
      return this[this.uploadMethod];
    },

    // Check if all form fields are filled before allowing emission
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
 
