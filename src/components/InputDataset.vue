<script>
import axios from 'axios';
import { Tooltip } from 'bootstrap';

export default {
  name: 'InputDataset',
  
  props: {
    showRemoteDatasets: {
      type: Boolean,
      default: false
    }
  },

  data() {
    return {
      baseURL: localStorage.getItem("fzvis_server_address"),
      depth: null,
      width: null,
      height: null,
      precision: "",
      fileContent: "",
      files: [],
      file: null,
      currentDataset: null,
      datasetToChange: null,
      isLoadingDatasets: false,
      uploadedDatasets: [],
      datasetsToDelete:[],
      // showProgressBar removed; using global footer progress instead
      isNetCDF: false,
      ncSelectedVar: "",
      showSliceControls: false,
      sliceParams: [],
    }
  },

  computed: {
    hasDatasets() {
      return Object.keys(this.uploadedDatasets).length > 0;
    },

    // Check if all form fields are filled before allowing emission
    isFormValid() {
      if (this.isNetCDF) {
        return this.file;
      }
      // Modify dimensions of the existing dataset
      if (!this.file && this.currentDataset) {
        return this.width && this.height && this.depth && this.precision;
      }
      // Upload a new dataset
      return this.file && this.width && this.height && this.depth && this.precision;
    },

    // Check if there is a slicable dimension for a variable in NetCDF file
    hasSlicableDimensions() {
      if (!this.ncSelectedVar) return false;
      return this.currentDataset.vars[this.ncSelectedVar].shape.some(size => size > 1);
    }
  },
  
  watch: {
    ncSelectedVar(newVal) {
      this.showSliceControls = false;
      this.sliceParams = [];

      if (newVal) {
        this.initSliceParams();
      }
    },
    // Call viewDatasets when the prop becomes true after mount
    showRemoteDatasets(newVal) {
      if (newVal) {
        this.viewDatasets();
      }
    }
  },

  mounted() {
    if (this.showRemoteDatasets) {
      this.viewDatasets();
    }
  },

  updated() {
    this.initializeTooltips();
  },
  
  methods:{
    // Initialize tooltips in the DOM
    initializeTooltips() {
      document.querySelectorAll('[data-bs-toggle="tooltip"]').
        forEach(tooltip => {
          new Tooltip(tooltip);
        });
    },

    viewDatasets() {
      this.datasetToChange = this.currentDataset;
      this.datasetsToDelete = [];

      this.isLoadingDatasets = true;
      if (!this.hasDatasets) {
        axios.get(`${this.baseURL}/listDatasets`).then(response => {
          this.uploadedDatasets = response.data.datasets;
        })
        .catch(error => {
          // Show error in footer status/history
          this.$store.commit('setStatus', { type: 'danger', message: 'Failed to load saved datasets.' });
          this.$store.commit('addHistory', { kind: 'error', text: `Fetch saved datasets failed: ${error}`, timestamp: Date.now() });
        })
        .finally(() => {
          this.isLoadingDatasets = false;
        });
      } else {
        this.isLoadingDatasets = false;
      }
    },

    async handleFileChange(event) {
      const newFile = event.target.files[0];
      if (newFile) {
        this.file = newFile;
        // Handle NetCDF file format
        const validExtensions = [".nc", ".cdf", ".nc4"];
        const filename = newFile.name.toLowerCase();
        this.ncSelectedVar = "";
        this.isNetCDF = validExtensions.some(ext => filename.endsWith(ext));
        this.$store.commit("setTimeVarying", false);
        if (!this.isNetCDF) {
          const reader = new FileReader();
          reader.onload = (e) => {
            this.fileContent = e.target.result; // save file content
          };
          reader.readAsArrayBuffer(newFile); // read binary data
        }
      }
    },

    emitFileData() {
      // console.log("fileContent:", this.fileContent);
      this.$store.commit("setFileData", {
        content: this.fileContent,
        dimensions: [Number(this.width), Number(this.height), Number(this.depth)],
        precision: this.precision,
      });
      this.$store.commit("setComparisonData", null);
    },

    uploadFile() {
      // Generate form data
      const formData = new FormData();
      if (this.file) {
        formData.append("file", this.file);
      } else if (this.currentDataset) {
        formData.append("filename", this.currentDataset.name);
      }
      
      // Progress shown globally in footer
      this.$store.commit('setProgress', { active: true, percent: 0, message: 'Uploading dataset file...' });
      
      if (this.isNetCDF) {
        formData.append("type", "netcdf");
      }
      else {
        formData.append("type", "plain");
        formData.append("width", this.width);
        formData.append("height", this.height);
        formData.append("depth", this.depth);
        formData.append("precision", this.precision);
      }
      
      axios.post(`${this.baseURL}/upload`, formData, {
        onUploadProgress: (eventData) => {
          if (eventData.lengthComputable) {
            const percentComplete = Math.round((eventData.loaded / eventData.total) * 90);
            this.$store.commit('setProgress', { active: true, percent: percentComplete, message: 'Uploading dataset file...' });
          } else {
            this.$store.commit('setProgress', { active: true, message: 'Uploading dataset file...' });
          }
          this.$store.commit('setStatus', { type: 'info', message: 'Uploading dataset…' });
        }
      })
      .then(response => {
        this.currentDataset = response.data["dataset"];
        if (!this.isNetCDF) {
          this.emitFileData();
        }
        // update the cached dataset list
        if (this.uploadedDatasets) {
          this.uploadedDatasets[this.currentDataset.name] = this.currentDataset;
        }

        // finalize progress
        this.$store.commit('setProgress', { percent: 100, message: 'Finalizing upload…' });
        setTimeout(() => this.$store.commit('clearProgress'), 800);

        const dtype = this.isNetCDF ? 'NetCDF' : (this.precision === 'f' ? 'float32' : 'float64');
        this.$store.commit('setStatus', { type: 'success', message: `Uploaded dataset: ${this.currentDataset?.name || '(new)'}` });
        this.$store.commit('addHistory', { kind: 'dataset', text: `Uploaded dataset '${this.currentDataset?.name || ''}' (${dtype})`, timestamp: Date.now() });
        this.$emit('configured');
      })
      .catch(error => {
        this.$store.commit('clearProgress');
        this.$store.commit('setStatus', { type: 'danger', message: 'Upload failed.' });
        this.$store.commit('addHistory', { kind: 'error', text: `Upload failed: ${error}`, timestamp: Date.now() });
      });
    },

    async processChanges() {
      const formData = new FormData();
      
      if (this.currentDataset != this.datasetToChange) {
        this.$store.commit("setTimeVarying", false);
        formData.append("currentDataset", JSON.stringify(this.datasetToChange));
        this.file = null;   // reset the file if the user has previously selected one
        // Handle different data file types
        if (this.datasetToChange.type === "plain") {
          this.width = this.datasetToChange.width;
          this.height = this.datasetToChange.height;
          this.depth = this.datasetToChange.depth;
          this.precision = this.datasetToChange.precision;
          // Get the new file from the server asynchronously
          await axios.get(`${this.baseURL}/download`, {
            params: { filename: this.datasetToChange.name, filetype: this.datasetToChange.type },
            responseType: "arraybuffer",
            onDownloadProgress: (eventData) => {
              if (eventData.lengthComputable) {
                const percentComplete = Math.round((eventData.loaded / eventData.total) * 90);
                this.$store.commit('setProgress', { active: true, percent: percentComplete, message: 'Downloading dataset…' });
              } else {
                this.$store.commit('setProgress', { active: true, message: 'Downloading dataset…' });
              }
            }
          }).then(response => {
            this.isNetCDF = false;
            this.ncSelectedVar = "";
            this.fileContent = response.data;
            this.emitFileData();
            this.currentDataset = this.datasetToChange;

            this.$store.commit('setProgress', { percent: 100, message: 'Download complete' });
            setTimeout(() => this.$store.commit('clearProgress'), 800);

            this.$store.commit('setStatus', { type: 'success', message: `Loaded dataset: ${this.currentDataset?.name}` });
            this.$store.commit('addHistory', { kind: 'dataset', text: `Loaded dataset '${this.currentDataset?.name}'`, timestamp: Date.now() });
          }).catch(error => {
            console.error("Download file failed.", error);
            this.$store.commit('clearProgress');
            this.$store.commit('setStatus', { type: 'danger', message: 'Dataset download failed.' });
            this.$store.commit('addHistory', { kind: 'error', text: `Dataset download failed: ${error}`, timestamp: Date.now() });
          });
        }
        else if(this.datasetToChange.type === "netcdf") {
          this.ncSelectedVar = "";
          this.isNetCDF = true;
          this.currentDataset = this.datasetToChange;
          this.$store.commit('setStatus', { type: 'info', message: `Selected NetCDF dataset: ${this.currentDataset?.name}` });
          this.$store.commit('addHistory', { kind: 'dataset', text: `Selected NetCDF dataset '${this.currentDataset?.name}'`, timestamp: Date.now() });
        }
        this.$emit('configured');
      }
        
      // delete datasets
      if (this.datasetsToDelete.length > 0) {
        formData.append("deletedDatasets", JSON.stringify(this.datasetsToDelete));
        this.datasetsToDelete.forEach(key => delete this.uploadedDatasets[key]);
      }

      // check if there are any changes made 
      if (!formData.entries().next().done) {
        await axios.post(`${this.baseURL}/updateDatasets`, formData).then(response => {
          if (!(JSON.stringify(this.uploadedDatasets) === JSON.stringify(response.data.datasets))) {
            console.error("uploadedDatasets are not equal!");
          }
          if (this.datasetsToDelete.length > 0) {
            this.$store.commit('addHistory', { kind: 'dataset', text: `Deleted datasets: ${this.datasetsToDelete.join(', ')}`, timestamp: Date.now() });
            this.$store.commit('setStatus', { type: 'warning', message: `Deleted ${this.datasetsToDelete.length} dataset(s)` });
          }
        })
        .catch(error => {
          console.error("Update datasets failed.", error);
          this.$store.commit('setStatus', { type: 'danger', message: 'Updating saved datasets failed.' });
          this.$store.commit('addHistory', { kind: 'error', text: `Update saved datasets failed: ${error}`, timestamp: Date.now() });
        });
      }
    },

    initSliceParams() {
      const shape = this.currentDataset.vars[this.ncSelectedVar].shape;
      this.sliceParams = shape.map(size => ({
        start: 0, 
        end: size, 
        step: 1
      }));
    },

    selectNetCDFVariable() {
      const timeDimensionIndex = this.currentDataset.vars[this.ncSelectedVar].dimensions.findIndex(
        dim => dim.toLowerCase() === "time"
      );
      // console.log("Time dimension index:", timeDimensionIndex);
      if (timeDimensionIndex >= 0) 
        this.$store.commit("setTimeVarying", true);
      
      // Set precision
      var dtype = this.currentDataset.vars[this.ncSelectedVar].dtype;
      if (dtype === "float32") {
        this.precision = "f";
      }
      else if (dtype === "float64") {
        this.precision = "d";
      }

      // Set dimensions
      var dims = this.currentDataset.vars[this.ncSelectedVar].shape;
      const slicedDims = dims.map((size, dimIndex) => {
        if (size == 1) return 1;
        const slice = this.sliceParams[dimIndex];
        if (!slice) return size;

        const start = slice.start || 0;
        const end = slice.end !== undefined ? slice.end : size;
        const step = slice.step || 1;

        return Math.ceil((end - start) / step);
      });

      if (slicedDims.length === 2) {
        this.height = slicedDims[0];
        this.width = slicedDims[1];
        this.depth = 1;
      }
      else if (slicedDims.length === 3) {
        this.depth = slicedDims[timeDimensionIndex > 0 ? timeDimensionIndex : 0];
        this.height = slicedDims[(timeDimensionIndex === 2 || timeDimensionIndex === -1) ? 0 : 1];
        this.width = slicedDims[(timeDimensionIndex === 2 || timeDimensionIndex === -1) ? 1 : 2];
      }

      const slices = this.sliceParams
        .filter(param => param != null)
        .map(param => ({
          start: param.start,
          end: param.end,
          step: param.step,
        }));
      console.log("slices values:", slices);

      this.$store.commit('setProgress', { active: true, percent: 0, message: 'Downloading variable data…' });
    
      // Get the variable data from the backend server
      axios.get(`${this.baseURL}/download`, {
        params: { 
          filename: this.currentDataset.name, 
          filetype: "netcdf", 
          variable: this.ncSelectedVar,
          slices: JSON.stringify(slices),
        },
        responseType: "arraybuffer",
        onDownloadProgress: (eventData) => {
          if (eventData.lengthComputable) {
            const percentComplete = Math.round((eventData.loaded / eventData.total) * 90);
            this.$store.commit('setProgress', { active: true, percent: percentComplete, message: 'Downloading variable data…' });
          } else {
            this.$store.commit('setProgress', { active: true, message: 'Downloading variable data…' });
          }
        }
      }).then(response => {
        this.fileContent = response.data;
        this.emitFileData();

        this.$store.commit('setProgress', { percent: 100, message: 'Variable download complete' });
        setTimeout(() => this.$store.commit('clearProgress'), 800);

        this.$store.commit('setStatus', { type: 'success', message: `Loaded variable '${this.ncSelectedVar}' from ${this.currentDataset?.name}` });
        this.$store.commit('addHistory', { kind: 'dataset', text: `Loaded variable '${this.ncSelectedVar}' from dataset '${this.currentDataset?.name}'`, timestamp: Date.now() });
      }).catch(error => {
        console.error("Download file failed.", error);
        this.$store.commit('clearProgress');
        this.$store.commit('setStatus', { type: 'danger', message: 'Variable download failed.' });
        this.$store.commit('addHistory', { kind: 'error', text: `Variable download failed: ${error}`, timestamp: Date.now() });
      });
    }
  },
};
</script>

<template>
  <div class="container align-items-center">
    <div v-if="showRemoteDatasets">
      <h1 class="h4">Saved datasets</h1>
      <div class="card-body overflow-auto mt-2" style="max-height: 50vh;">
        <template v-if="hasDatasets">
          <ul class="list-group">
            <li v-for="(dataset, key) in uploadedDatasets" :key="dataset.id" 
              :class="['list-group-item', 'd-flex', 'justify-content-between', 'align-items-start', { 'active': dataset.name == datasetToChange?.name, 'list-group-item-danger': datasetsToDelete.includes(key) }]">
              <div class="ms-2 me-auto">
                <div :class="['fw-bold', 'text-break', { 'text-decoration-line-through': datasetsToDelete.includes(key) }]">
                  {{ dataset.name }}
                  <span class="badge bg-secondary" v-if="dataset.type === 'plain' && dataset.precision === 'f'">float32</span>
                  <span class="badge bg-secondary" v-if="dataset.type === 'plain' && dataset.precision === 'd'">float64</span>
                  <span class="badge bg-info ms-1">{{ dataset.size }}</span>
                </div>
                <div v-if="dataset.type === 'plain'">
                  dimensions: ({{ dataset.width }} &times; {{ dataset.height }} &times; {{ dataset.depth }})
                </div>
                <div v-else-if="dataset.type === 'netcdf'">
                  variables: [
                    <span v-for="(name, idx) in Object.keys(dataset.vars)" :key=name>
                      <span v-if="idx !== 0">, </span>{{ name }}
                    </span>]
                </div>
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
        </template>
        <template v-else>
          <p v-if="isLoadingDatasets" class="text-info">Loading datasets from server...</p>
          <p v-else class="text-warning">No saved datasets!</p>
        </template>
      </div>
      <div class="card-footer d-flex justify-content-end gap-2 mt-3">
        <button type="button" class="btn btn-secondary">Close</button>
        <button type="button" class="btn btn-primary" @click="processChanges()">Save changes</button>
      </div>
    </div>

    <div v-else>
      <input type="file" class="form-control mt-3 mb-2" id="fileloader" @change="handleFileChange">
      <div v-if="isNetCDF">
        <small class="py-0 mt-0 text-muted">Click submit button to parse the NetCDF file.</small>
      </div>
      <div v-else class="row g-3 align-items-center my-2">
        <!-- precision -->
        <div class="col-md-6">
          <div class="row g-1 align-items-center">
            <div class="col">
              <select class="form-select" aria-label="precision" v-model="precision">
                <option value="" disabled selected>Data precision</option>
                <option value="f">single (f)</option>
                <option value="d">double (d)</option>
              </select>
            </div>
          </div>
        </div>
        <!-- depth -->
        <div class="col-md-6">
          <div class="row g-1 align-items-center">
            <div class="col-auto">
              <label for="depth" class="form-label">Depth:</label>
            </div>
            <div class="col">
              <input class="form-control ms-1" type="number" min="1" label="depth:" v-model="depth" placeholder="500" id="depth" />
            </div>
          </div>
        </div>
        <!-- width -->
        <div class="col-md-6">
          <div class="row g-1 align-items-center">
            <div class="col-auto">
              <label for="width" class="form-label mb-0">Width:</label>
            </div>
            <div class="col">
              <input class="form-control ms-1" type="number" min="1" label="width:" v-model="width" placeholder="500" id="width" />
            </div>
          </div>
        </div>
        <!-- height -->
        <div class="col-md-6">
          <div class="row g-1 align-items-center">
            <div class="col-auto">
              <label for="height" class="form-label mb-0">Height:</label>
            </div>
            <div class="col">
              <input class="form-control ms-1" type="number" min="1" label="height:" v-model="height" placeholder="500" id="height" />
            </div>
          </div>
        </div>

        <small v-if="isFormValid" class="pt-1 text-muted">Click the upload button to upload the dataset.</small>
        <small v-else class="pt-1 text-muted">Please fill all fields to upload the file.</small>
      </div>

      <button type="button" class="btn btn-success my-1" @click="uploadFile" :disabled="!isFormValid">Upload</button>
      <!-- <button id="viewDatasetsBtn" v-if="showRemoteDatasets" type="button" class="btn btn-info ms-2 my-1" @click="viewDatasets" title="View all uploaded datasets">View datasets</button> -->
    </div>
    
    <!-- NetCDF file explorer -->
    <div v-show="isNetCDF">
      <table class="table mt-2" v-if="currentDataset">
        <thead>
          <tr>
            <th></th>
            <th>name</th>
            <th>type</th>
            <th>dimensions</th>
          </tr>
        </thead>
        <tbody v-for="(props, name) in currentDataset.vars" :key="name">
          <tr :class="ncSelectedVar === name ? 'table-primary' : ''">
            <td style="vertical-align: middle; text-align: center;"><input class="form-check-input" type="radio" name="netcdf-var-select" :value="name" v-model="ncSelectedVar"></td>
            <td style="vertical-align: middle;">{{ name }}</td>
            <td style="vertical-align: middle;">{{ props.dtype }}</td>
            <td><a class="text-decoration-underline text-dark" data-bs-toggle="tooltip" data-bs-placement="right" :title="'[' + props.dimensions + ']'">{{ props.shape }}</a></td>
          </tr>
        </tbody>
      </table>

      <!-- Slicing filter -->
      <div v-show="ncSelectedVar" class="slice-controls-container mt-3">
        <!-- checkbox -->
        <div class="d-flex align-items-center gap-3">
          <div class="form-check ms-1">
            <input class="form-check-input" type="checkbox" id="showSliceControls" v-model="showSliceControls" @change="initSliceParams">
            <label class="form-check-label mb-2" for="showSliceControls">
              Enable slicing
            </label>
          </div>
          <button class="btn btn-primary" @click="selectNetCDFVariable">Apply</button>
        </div>

        <!-- parameter settings -->
        <div v-if="showSliceControls" class="card mt-2">
          <div class="card-header">
            <h5>Slice variable: {{ ncSelectedVar }}</h5>
          </div>
          <div class="card-body">
            <template v-for="(dimSize, dimIndex) in currentDataset.vars[ncSelectedVar].shape">
              <div v-if="dimSize > 1"  :key="dimIndex" class="mb-3">
                <label class="form-label">Dimension {{ dimIndex }} (size: {{ dimSize }})</label>
                <div class="row g-2">
                  <div class="col">
                    <div class="form-floating">
                      <input type="number" class="form-control" :id="'start-'+dimIndex" :min="0" :max="dimSize-1" v-model.number="sliceParams[dimIndex].start">
                      <label :for="'start-'+dimIndex">Start</label>
                    </div>
                  </div>
                  <div class="col">
                    <div class="form-floating">
                      <input type="number" class="form-control" :id="'end-'+dimIndex" min="1" :max="dimSize" v-model.number="sliceParams[dimIndex].end">
                      <label :for="'end-'+dimIndex">End</label>
                    </div>
                  </div>
                  <div class="col">
                    <div class="form-floating">
                      <input type="number" class="form-control" :id="'step-'+dimIndex" min="1" v-model.number="sliceParams[dimIndex].step">
                      <label :for="'step-'+dimIndex">Step</label>
                    </div>
                  </div>
                </div>
              </div>
            </template>
            <div v-if="!hasSlicableDimensions" class="alert alert-info">
              This variable has no dimensions with size > 1 available for slicing.
            </div>
          </div>
        </div>
      </div>
    </div>
    
  </div>
</template>
