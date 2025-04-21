<template>
  <div class="container align-items-center">
    <h1 class="h3 px-2 pt-3 pb-2">Dataset Settings</h1>
    
    <input type="file" class="form-control" id="fileloader" @change="handleFileChange">

    <div id="whd" class="row g-3 py-2">
      <div class="col-md-4 py-1">
        <label for="width" class="form-label mx-1 mb-0">Width:</label>
        <input class="form-control" type="number" min="1" id="width" label="width:" v-model="width" placeholder="500" />
      </div>
      <div class="col-md-4 py-1">
        <label for="height" class="form-label mx-1 mb-0">Height:</label>
        <input class="form-control" type="number" min="1" id="height" label="height:" v-model="height" placeholder="500" />
      </div>
      <div class="col-md-4 py-1">
        <label for="depth" class="form-label mx-1 mb-0">Depth:</label>
        <input class="form-control" type="number" min="1" id="depth" label="depth:" v-model="depth" placeholder="500" />
      </div>
      <div class="col-md-6 mt-1 py-1">
        <select id="precision" class="form-select m-1 w-auto" aria-label="precision" v-model="precision">
          <option value="" disabled selected>select precision</option>
          <option value="f">single (f)</option>
          <option value="d">double (d)</option>
        </select>
      </div>
      <small v-if="isFormValid" class="py-0 mt-0 text-muted">Click submit button to upload the dataset.</small>
      <small v-else class="py-0 mt-0 text-muted">Please fill all fields to submit.</small>
    </div>
    <button type="button" class="btn btn-success me-2 my-1" @click="uploadFile" :disabled="!isFormValid">Submit</button>
    <!-- Button trigger modal -->
    <button type="button" class="btn btn-info my-1" @click="fetchDatasets" title="View all uploaded datasets">View datasets</button>
    <div v-if="currentDataset == null" class="text-danger mt-1">
      No dataset selected for processing.
    </div>
    <div v-else class="text-success mt-1">
      Current dataset: 
      <strong >{{ currentDataset.name }}</strong>
    </div>

    <div id="uploadAlert" class="alert alert-dismissible fade" role="alert" tabindex="-1">
      <span id="uploadAlertMessage">Placeholder</span>
      <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    </div>

    <!-- Dataset modal -->
    <div id="datasetModal" class="modal fade" data-bs-backdrop="static" tabindex="-1" aria-labelledby="datasetModalLabel" aria-hidden="true">
      <div class="modal-dialog modal-dialog-scrollable">
        <div class="modal-content">
          <div class="modal-header">
            <h1 class="modal-title fs-5" id="datasetModalLabel">Saved datasets</h1>
            <!-- <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button> -->
          </div>
          <div class="modal-body overflow-auto">
            <ul v-if="hasDatasets">
              <li v-for="(dataset, key) in uploadedDatasets" :key="dataset.id">
                <span v-if="datasetsToDelete.includes(key)" class="pe-2 text-decoration-line-through">{{ dataset.name }}</span>
                <span v-else class="pe-2">{{ dataset.name }}</span>
                <!-- highlight the currently selected dataset -->
                <button v-if="datasetToChange?.name == dataset.name" class="btn btn-primary ms-1" aria-label="Select" title="Select the dataset"><i class="bi bi-check2-circle"></i></button>
                <button v-else @click="restoreDataset(dataset)" class="btn btn-outline-primary ms-1" aria-label="Select" :disabled="datasetsToDelete.includes(key)" title="Select the dataset"><i class="bi bi-check2-circle"></i></button>

                <button v-if="datasetsToDelete.includes(key)" class="btn btn-danger ms-1" aria-label="Delete" title="Delete the dataset"><i class="bi bi-trash"></i></button>
                <button v-else @click="deleteDataset(key)" class="btn btn-outline-danger ms-1" aria-label="Delete" :disabled="datasetToChange?.name == dataset.name" title="Delete the dataset"><i class="bi bi-trash"></i></button>
              </li>
            </ul>
            <div v-else class="text-warning py-2">
              No saved datasets!
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal" @click="rollbackData">Close</button>
            <button type="button" class="btn btn-primary" data-bs-dismiss="modal" @click="processChanges">Save changes</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>

// import emitter from './eventBus.js';
import axios from 'axios'
import {Modal} from 'bootstrap';
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
      currentDataset: null,
      datasetToChange: null,
      uploadedDatasets: [],
      datasetsToDelete:[],
    }
  },

  methods:{
    fetchDatasets() {
      const baseURL = process.env.VUE_APP_API_BASE;
      axios.get(`${baseURL}/listDatasets`).then(response => {
        this.uploadedDatasets = response.data.datasets;
        this.datasetToChange = this.currentDataset;
        const modalElement = document.getElementById("datasetModal");
        if (modalElement) {
          var modal = new Modal(modalElement);
          modal.show();
        }
        // console.log("uploaded datasets:", JSON.stringify(this.uploadedDatasets));
      })
      .catch(error => {
        const alertBox = document.getElementById("uploadAlert");
        const alertMessage = document.getElementById("uploadAlertMessage");
        if (alertBox && alertMessage) {
          alertBox.classList.remove("alert-success");
          alertBox.classList.add("alert-danger", "show");
          alertMessage.textContent = `Fetch saved datasets failed. ${error}`;
          // Auto dismiss
          setTimeout(() => {
            alertBox.classList.remove("show");
          }, 6000);
        }
      });
    },

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

    uploadFile() {
      // Generate form data
      const formData = new FormData();
      
      // Generate a unique ID for the dataset
      formData.append("file", this.file);
      formData.append("width", this.width);
      formData.append("height", this.height);
      formData.append("depth", this.depth);
      formData.append("precision", this.precision);
      
      const baseURL = process.env.VUE_APP_API_BASE;
      const alertBox = document.getElementById("uploadAlert");
      const alertMessage = document.getElementById("uploadAlertMessage");

      axios.post(`${baseURL}/upload`, formData).then(response => {
        this.currentDataset = response.data.dataset;
        if (alertBox && alertMessage) {
          alertBox.classList.remove("alert-danger");
          alertBox.classList.add("alert-success", "show");
          alertMessage.textContent = "File uploaded successfully!";
          // Auto dismiss
          setTimeout(() => {
            alertBox.classList.remove("show");
          }, 4000);
        }
      })
      .catch (error => {
        if (alertBox && alertMessage) {
          alertBox.classList.remove("alert-success");
          alertBox.classList.add("alert-danger", "show");
          alertMessage.textContent = `Upload failed. ${error}`;
          // Auto dismiss
          setTimeout(() => {
            alertBox.classList.remove("show");
          }, 6000);
        }
      });

      // emitter.emit('file-selected', dataset);
      // emitter.emit('file-input', this.uploadedDatasets[0]);
      // alert('Dataset emitted successfully!');
    },

    rollbackData() {
      this.datasetToChange = this.currentDataset;
      this.datasetsToDelete = [];
    },

    processChanges() {
      this.currentDataset = this.datasetToChange;
      this.width = this.currentDataset.width;
      this.height = this.currentDataset.height;
      this.depth = this.currentDataset.depth;
      this.precision = this.currentDataset.precision;
      // this.file = dataset.file;
      // console.log("Restored dataset:", dataset);

      // delete datasets on the server side
      if (this.datasetsToDelete.length > 0) {
        const formData = new FormData();
        formData.append("datasets", this.datasetsToDelete);
        const baseURL = process.env.VUE_APP_API_BASE;
        axios.post(`${baseURL}/deleteDatasets`, formData).then(response => {
          this.uploadedDatasets = response.data.datasets;
          console.log("uploadedDatasets:", JSON.stringify(this.uploadedDatasets));
        })
        .catch (error => {
          console.log("Delete datasets failed.", error);
        });
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

    requestFailMethod(file) {
      console.log(file);
      return new Promise((resolve) => {
        resolve({ status: 'fail', error: 'Upload failed, please double check the file!' });
      });
    },

    restoreDataset(selectedDataset) {
      this.datasetToChange = selectedDataset;
    },

    deleteDataset(datasetKey) {
      this.datasetsToDelete.push(datasetKey);
    },
  },
  computed: {
    hasDatasets() {
      return Object.keys(this.uploadedDatasets).length > 0;
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
 
