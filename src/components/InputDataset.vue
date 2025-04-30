<template>
  <div class="container align-items-center">
    <h1 class="h3 px-2 pt-3 pb-2">Dataset Settings</h1>
    
    <input type="file" class="form-control" id="fileloader" @change="handleFileChange">

    <div class="row g-3 py-2">
      <div class="col-md-4 py-1">
        <label for="width" class="form-label mx-1 mb-0">Width:</label>
        <input class="form-control" type="number" min="1" label="width:" v-model="width" placeholder="500" />
      </div>
      <div class="col-md-4 py-1">
        <label for="height" class="form-label mx-1 mb-0">Height:</label>
        <input class="form-control" type="number" min="1" label="height:" v-model="height" placeholder="500" />
      </div>
      <div class="col-md-4 py-1">
        <label for="depth" class="form-label mx-1 mb-0">Depth:</label>
        <input class="form-control" type="number" min="1" label="depth:" v-model="depth" placeholder="500" />
      </div>
      <div class="col-md-6 mt-1 py-1">
        <select class="form-select m-1 w-auto" aria-label="precision" v-model="precision">
          <option value="" disabled selected>Select precision</option>
          <option value="f">single (f)</option>
          <option value="d">double (d)</option>
        </select>
      </div>
      <small v-if="isFormValid" class="py-0 mt-0 text-muted">Click submit button to upload the dataset.</small>
      <small v-else class="py-0 mt-0 text-muted">Please fill all fields to submit the file.</small>
    </div>
    <button type="button" class="btn btn-success me-2 my-1" @click="uploadFile" :disabled="!isFormValid">Submit</button>
    <!-- Button trigger modal -->
    <button id="viewDatasetsBtn" type="button" class="btn btn-info my-1" @click="viewDatasets" title="View all uploaded datasets">View datasets</button>
    <div v-if="currentDataset == null" class="text-danger mt-1">
      No dataset selected for processing.
    </div>
    <div v-else class="text-success mt-1">
      Current dataset: 
      <strong >{{ currentDataset.name }}</strong>
    </div>

    <!-- Progress bar -->
    <div v-show="showProgressBar" class="progress my-2">
      <div ref="progressBar" class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" aria-valuenow="75" aria-valuemin="0" aria-valuemax="100" style="width: 0%">0%</div>
    </div>

    <!-- Alert message box -->
    <div ref="progressAlert" class="alert alert-dismissible fade" role="alert" tabindex="-1">
      <span ref="progressAlertMessage">Placeholder</span>
      <!-- <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button> -->
    </div>

    <!-- Dataset modal -->
    <div id="datasetModal" class="modal fade" data-bs-backdrop="static" tabindex="-1" aria-labelledby="datasetModalLabel" aria-hidden="true">
      <div class="modal-dialog modal-dialog-scrollable">
        <div class="modal-content">
          <div class="modal-header">
            <h1 class="modal-title fs-5" id="datasetModalLabel">Saved datasets</h1>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <!-- Modal body -->
          <div class="modal-body overflow-auto" v-if="hasDatasets">
            <ul class="list-group">
              <li v-for="(dataset, key) in uploadedDatasets" :key="dataset.id" 
                :class="['list-group-item', 'd-flex', 'justify-content-between', 'align-items-start', { 'active': dataset.name == datasetToChange?.name, 'list-group-item-danger': datasetsToDelete.includes(key) }]">
                <div class="ms-2 me-auto">
                  <div :class="['fw-bold', { 'text-decoration-line-through': datasetsToDelete.includes(key) }]">
                    {{ dataset.name }}
                    <span class="badge bg-secondary" v-if="dataset.precision === 'f'">float32</span>
                    <span class="badge bg-secondary" v-else-if="dataset.precision === 'd'">float64</span>
                    <span class="badge bg-info ms-1">{{ dataset.size }}</span>
                  </div>
                  dimensions: ({{ dataset.width }} &times; {{ dataset.height }} &times; {{ dataset.depth }})
                </div>
                <!-- Select and delete buttons -->
                <div class="d-flex align-items-center">
                  <button class="btn btn-sm ms-2"
                    :class="dataset.name == datasetToChange?.name ? 'btn-primary' : 'btn-outline-primary'"
                    :aria-label="dataset.name == datasetToChange?.name ? 'Deselect' : 'Select'"
                    :title="dataset.name == datasetToChange?.name ? 'Deselect the dataset' : 'Select the dataset'"
                    :disabled="dataset.name == datasetToChange?.name || datasetsToDelete.includes(key)"
                    @click="datasetToChange = dataset">
                    <i :class="dataset.name == datasetToChange?.name ? 'bi bi-check-circle' : 'bi bi-circle'"></i>
                  </button>
                  <button class="ms-2 btn btn-sm" type="button"
                    :class="[datasetsToDelete.includes(key) ? 'btn-danger' : 'btn-outline-danger']"
                    :title="datasetsToDelete.includes(key) ? 'Undo delete' : 'Delete the dataset'"
                    :aria-label="datasetsToDelete.includes(key) ? 'Undo delete' : 'Delete'"
                    :hidden="datasetToChange?.name == dataset.name"
                    @click="datasetsToDelete.includes(key)
                              ? datasetsToDelete.splice(datasetsToDelete.indexOf(key), 1)
                              : datasetsToDelete.push(key)">
                    <i class="bi bi-trash"></i>
                  </button>
                </div>
              </li>
            </ul>
          </div>
          <div v-else class="modal-body text-warning">
            No saved datasets!
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
            <button type="button" class="btn btn-primary" data-bs-dismiss="modal" @click="processChanges">Save changes</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>

import axios from 'axios'
import { Modal } from 'bootstrap';
import { ref } from 'vue';
export default {
  name: 'InputDataset',
  
  setup() {
    const progressBar = ref(null);
    const progressAlert = ref(null);
    const progressAlertMessage = ref(null);

    return {
      progressBar,
      progressAlert,
      progressAlertMessage,
    };
  },

  data() {
    return {
      depth: null,
      width: null,
      height: null,
      precision: "",
      fileContent: "",
      files: [],
      file: null,
      currentDataset: null,
      datasetToChange: null,
      uploadedDatasets: [],
      datasetsToDelete:[],
      showProgressBar: false,
    }
  },

  computed: {
    hasDatasets() {
      return Object.keys(this.uploadedDatasets).length > 0;
    },

    // Check if all form fields are filled before allowing emission
    isFormValid() {
      // Modify dimensions of the existing dataset
      if (!this.file && this.currentDataset) {
        return this.width && this.height && this.depth && this.precision;
      }
      // Upload a new dataset
      return this.file && this.width && this.height && this.depth && this.precision;
    },
  },
  
  methods:{
    viewDatasets() {
      this.datasetToChange = this.currentDataset;
      this.datasetsToDelete = [];
      var modalElement = document.getElementById("datasetModal");

      if (!this.hasDatasets) {
        const baseURL = process.env.VUE_APP_API_BASE;
        axios.get(`${baseURL}/listDatasets`).then(response => {
          this.uploadedDatasets = response.data.datasets;
          if (modalElement) {
            var modal = new Modal(modalElement);
            modal.show();
          }
        })
        .catch(error => {
          if (this.progressAlert && this.progressAlertMessage) {
            this.progressAlert.classList.remove("alert-success");
            this.progressAlert.classList.add("alert-danger", "show");
            this.progressAlertMessage.textContent = `Fetch saved datasets failed. ${error}`;
            // Auto dismiss
            setTimeout(() => {
              this.progressAlert.classList.remove("show");
            }, 6000);
          }
        });
      }
      else {
        if (modalElement) {
          var modal = new Modal(modalElement);
          modal.show();
        }
      }
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

    emitFileData() {
      this.$store.commit("setFileData", {
        content: this.fileContent,
        dimensions: [Number(this.width), Number(this.height), Number(this.depth)],
        precision: this.precision
      });
    },

    uploadFile() {
      // Generate form data
      const formData = new FormData();
      if (this.file) {
        formData.append("file", this.file);
      } else if (this.currentDataset) {
        formData.append("filename", this.currentDataset.name);
      }
      formData.append("width", this.width);
      formData.append("height", this.height);
      formData.append("depth", this.depth);
      formData.append("precision", this.precision);
      
      this.showProgressBar = true;
      const baseURL = process.env.VUE_APP_API_BASE;
      
      axios.post(`${baseURL}/upload`, formData, {
        onUploadProgress: (eventData) => {
          if (eventData.lengthComputable) {
            const percentComplete = Math.round((eventData.loaded / eventData.total) * 90);
            this.progressBar.style.width = percentComplete + '%';
            this.progressBar.setAttribute("aria-valuenow", percentComplete);
            this.progressBar.textContent = percentComplete + '%';
          }
          this.progressAlert.classList.remove("alert-danger");
          this.progressAlert.classList.remove("alert-success");
          this.progressAlert.classList.add("alert-secondary", "show");
          this.progressAlertMessage.textContent = "Uploading the dataset file...";
        }
      })
      .then(response => {
        this.currentDataset = response.data.dataset;
        this.emitFileData();
        // update the cached dataset list
        // or simply set `hasDatasets` to false?
        if (this.uploadedDatasets) {
          this.uploadedDatasets[this.currentDataset.name] = this.currentDataset;
        }
        this.progressBar.style.width = "100%";
        this.progressBar.setAttribute("aria-valuenow", 100);
        this.progressBar.textContent = "100%";
        setTimeout(() => {
          this.showProgressBar = false;
          this.progressBar.style.width = "0%";
        }, 3000);

        this.progressAlert.classList.remove("alert-danger");
        this.progressAlert.classList.remove("alert-secondary");
        this.progressAlert.classList.add("alert-success", "show");
        this.progressAlertMessage.textContent = "Uploaded file successfully!";
        // Auto dismiss
        setTimeout(() => {
          this.progressAlert.classList.remove("show");
        }, 5000);
      })
      .catch(error => {
        this.progressAlert.classList.remove("alert-success");
        this.progressAlert.classList.remove("alert-secondary");
        this.progressAlert.classList.add("alert-danger", "show");
        this.progressAlertMessage.textContent = `Upload file failed. ${error}`;
      });
    },

    async processChanges() {
      var btn = document.getElementById("viewDatasetsBtn");
      btn.disabled = true;
      const formData = new FormData();
      const baseURL = process.env.VUE_APP_API_BASE;
      
      if (this.currentDataset != this.datasetToChange) {
        this.file = null;   // reset the file if the user has previously selected one
        this.width = this.datasetToChange.width;
        this.height = this.datasetToChange.height;
        this.depth = this.datasetToChange.depth;
        this.precision = this.datasetToChange.precision;
        // console.log("Change dataset to:", JSON.stringify(this.datasetToChange));
        // Get the new file from the server asynchronously
        formData.append("currentDataset", JSON.stringify(this.datasetToChange));
        await axios.get(`${baseURL}/download`, {
          params: { filename: this.datasetToChange.name },
          responseType: "arraybuffer", 
          onDownloadProgress: (eventData) => {
            this.showProgressBar = true;
            if (eventData.lengthComputable) {
              const percentComplete = Math.round((eventData.loaded / eventData.total) * 90);
              this.progressBar.style.width = percentComplete + '%';
              this.progressBar.setAttribute("aria-valuenow", percentComplete);
              this.progressBar.textContent = percentComplete + '%';
            }

            this.progressAlert.classList.remove("alert-danger");
            this.progressAlert.classList.remove("alert-success");
            this.progressAlert.classList.add("alert-secondary", "show");
            this.progressAlertMessage.textContent = "Waiting to download the dataset...";
          }
        }).then(response => {
          this.fileContent = response.data;
          this.emitFileData();
          this.currentDataset = this.datasetToChange;
          this.progressBar.style.width = "100%";
          this.progressBar.setAttribute("aria-valuenow", 100);
          this.progressBar.textContent = "100%";

          this.progressAlert.classList.remove("alert-danger");
          this.progressAlert.classList.remove("alert-secondary");
          this.progressAlert.classList.add("alert-success", "show");
          this.progressAlertMessage.textContent = "Downloaded file successfully!";
          // Auto dismiss
          setTimeout(() => {
            this.showProgressBar = false;
            this.progressBar.style.width = "0%";
            this.progressAlert.classList.remove("show");
          }, 5000);

        })
        .catch(error => {
          console.error("Download file failed.", error);
        });
      }

      // delete datasets
      if (this.datasetsToDelete.length > 0) {
        formData.append("deletedDatasets", JSON.stringify(this.datasetsToDelete));
        this.datasetsToDelete.forEach(key => delete this.uploadedDatasets[key]);
      }

      // check if there are any changes made 
      if (!formData.entries().next().done) {
        await axios.post(`${baseURL}/updateDatasets`, formData).then(response => {
          if (!(JSON.stringify(this.uploadedDatasets) === JSON.stringify(response.data.datasets))) {
            console.error("uploadedDatasets are not equal!");
          }
        })
        .catch(error => {
          console.error("Update datasets failed.", error);
        });
      }
      btn.disabled = false;
    },
  },
  
};
</script>
 
