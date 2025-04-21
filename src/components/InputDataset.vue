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

    <!-- Progress bar -->
    <div v-show="showProgressBar" class="progress my-2">
      <div id="progressBar" class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" aria-valuenow="75" aria-valuemin="0" aria-valuemax="100" style="width: 0%">0%</div>
    </div>

    <!-- Alert message box -->
    <div id="uploadAlert" class="alert alert-dismissible fade" role="alert" tabindex="-1">
      <span id="uploadAlertMessage">Placeholder</span>
      <!-- <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button> -->
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
              <li v-for="(dataset, key) in uploadedDatasets" :key="dataset.id" class="my-2">
                <span v-if="datasetsToDelete.includes(key)" class="pe-2 text-decoration-line-through">{{ dataset.name }}</span>
                <span v-else class="pe-2">{{ dataset.name }}</span>
                <!-- highlight the currently selected dataset -->
                <button v-if="dataset.name == datasetToChange?.name" class="btn btn-primary ms-1" aria-label="Select" title="Select the dataset"><i class="bi bi-check2-circle"></i></button>
                <button v-else @click="datasetToChange = dataset" class="btn btn-outline-primary ms-1" aria-label="Select" :disabled="datasetsToDelete.includes(key)" title="Select the dataset"><i class="bi bi-check2-circle"></i></button>

                <button v-if="datasetsToDelete.includes(key)" class="btn btn-danger ms-1" aria-label="Delete" title="Delete the dataset"><i class="bi bi-trash"></i></button>
                <button v-else @click="datasetsToDelete.push(key)" class="btn btn-outline-danger ms-1" aria-label="Delete" :disabled="datasetToChange?.name == dataset.name" title="Delete the dataset"><i class="bi bi-trash"></i></button>
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

import emitter from './eventBus.js';
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
      showProgressBar: false,
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
      
      this.showProgressBar = true;
      const baseURL = process.env.VUE_APP_API_BASE;
      const alertBox = document.getElementById("uploadAlert");
      const alertMessage = document.getElementById("uploadAlertMessage");
      const progressBar = document.getElementById("progressBar");
      
      axios.post(`${baseURL}/upload`, formData, {
        onUploadProgress: function(eventData) {
          if (eventData.lengthComputable) {
            const percentComplete = Math.round((eventData.loaded / eventData.total) * 90);
            progressBar.style.width = percentComplete + '%';
            progressBar.setAttribute("aria-valuenow", percentComplete);
            progressBar.textContent = percentComplete + '%';
          }
          if (alertBox && alertMessage) {
            alertBox.classList.remove("alert-danger");
            alertBox.classList.remove("alert-success");
            alertBox.classList.add("alert-secondary", "show");
            alertMessage.textContent = "Processing...";
          }
        }
      })
      .then(response => {
        this.currentDataset = response.data.dataset;
        progressBar.style.width = "100%";
        progressBar.setAttribute("aria-valuenow", 100);
        progressBar.textContent = "100%";
        setTimeout(() => {
          this.showProgressBar = false;
          progressBar.style.width = "0%";
        }, 3000);

        if (alertBox && alertMessage) {
          alertBox.classList.remove("alert-danger");
          alertBox.classList.remove("alert-secondary");
          alertBox.classList.add("alert-success", "show");
          alertMessage.textContent = "File uploaded successfully!";
          // Auto dismiss
          setTimeout(() => {
            alertBox.classList.remove("show");
          }, 5000);
        }
      })
      .catch (error => {
        if (alertBox && alertMessage) {
          alertBox.classList.remove("alert-success");
          alertBox.classList.remove("alert-secondary");
          alertBox.classList.add("alert-danger", "show");
          alertMessage.textContent = `Upload failed. ${error}`;
          // Auto dismiss
          setTimeout(() => {
            alertBox.classList.remove("show");
          }, 6000);
        }
      });

      emitter.emit('file-selected', this.currentDataset);
      // emitter.emit('file-input', this.uploadedDatasets[0]);
      // alert('Dataset emitted successfully!');
    },

    rollbackData() {
      this.datasetToChange = this.currentDataset;
      this.datasetsToDelete = [];
    },

    processChanges() {
      const formData = new FormData();
      
      if (this.currentDataset != this.datasetToChange) {
        this.currentDataset = this.datasetToChange;
        this.width = this.currentDataset.width;
        this.height = this.currentDataset.height;
        this.depth = this.currentDataset.depth;
        this.precision = this.currentDataset.precision;
        formData.append("currentDataset", JSON.stringify(this.currentDataset));
      }

      // delete datasets
      if (this.datasetsToDelete.length > 0) {
        formData.append("deletedDatasets", JSON.stringify(this.datasetsToDelete));
      }

      // check if there are any changes made 
      if (!formData.entries().next().done) {
        const baseURL = process.env.VUE_APP_API_BASE;
        axios.post(`${baseURL}/updateDatasets`, formData).then(response => {
          this.uploadedDatasets = response.data.datasets;
          console.log("uploadedDatasets:", JSON.stringify(this.uploadedDatasets));
        })
        .catch (error => {
          console.log("Update datasets failed.", error);
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
 
