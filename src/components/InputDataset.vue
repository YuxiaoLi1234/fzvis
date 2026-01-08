<template>
  <div class="container align-items-center">
    <h1 class="h4 px-2 mt-3">Dataset Settings
      <i type="button" class="bi bi-info-circle ms-2 fs-5" data-bs-container="body" data-bs-toggle="popover" data-bs-placement="right" data-bs-html="true" data-bs-content="Currently support <b>raw</b> and <b>NetCDF</b> file formats."></i>
    </h1>
    
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

      <small v-if="isFormValid" class="pt-1 text-muted">Click submit button to upload the dataset.</small>
      <small v-else class="pt-1 text-muted">Please fill all fields to submit changes.</small>
    </div>

    <button type="button" class="btn btn-success my-1" @click="uploadFile" :disabled="!isFormValid">
      {{ currentDataset == null ? 'Upload' : 'Update' }}
    </button>
    <!-- Button trigger modal -->
    <button id="viewDatasetsBtn" type="button" class="btn btn-info ms-2 my-1" @click="viewDatasets" title="View all uploaded datasets">View datasets</button>
    <div v-if="currentDataset == null" class="alert alert-danger mt-1">
      No dataset selected for processing.
    </div>
    <div v-else class="alert alert-success mt-1">
      Current dataset: 
      <strong >{{ currentDataset.name }}</strong>
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
          </div>
          <div id="datasetModalBody" v-else class="modal-body">
            <p v-if="isLoadingDatasets" class="text-info">Loading datasets from server...</p>
            <p v-else class="text-warning">No saved datasets!</p>
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
import axios from 'axios';
import { Modal, Tooltip, Popover } from 'bootstrap';

export default {
  name: 'InputDataset',

  data() {
    return {
      baseURL: "/api",
      depth: null,
      width: null,
      height: null,
      precision: "",
      fileContent: "",
      file: null,
      datasetToChange: null,
      isLoadingDatasets: false,
      uploadedDatasets: [],
      datasetsToDelete:[],
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

    currentDataset() {
      return this.$store?.state?.dataset || null;
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
    currentDataset(newVal, oldVal) {
      this.fillFieldsFromDataset();
      if (newVal && newVal !== oldVal) {
        this.$store.commit('addHistory', {
          kind: 'dataset',
          text: `Changed data file to: ${newVal.name}`,
          timestamp: Date.now()
        });
      }
    }
  },

  mounted() {
    this.initializeTooltips();
    this.initializePopovers();
    this.fillFieldsFromDataset();
  },

  updated() {
    this.initializeTooltips();
    this.initializePopovers();
  },
  
  methods:{
    fillFieldsFromDataset() {
      const ds = this.currentDataset;
      if (!ds) {
        this.isNetCDF = false;
        this.precision = "";
        this.width = null;
        this.height = null;
        this.depth = null;
        return;
      }
      this.isNetCDF = ds.type === 'netcdf';
      if (ds.type === 'plain') {
        const dims = Array.isArray(ds.dimensions)
          ? ds.dimensions
          : [ds.width, ds.height, ds.depth];
        this.width = Number(dims?.[0]) || null;
        this.height = Number(dims?.[1]) || null;
        this.depth = Number(dims?.[2]) || null;
        if (ds.precision) this.precision = ds.precision;
      }
    },
    // Initialize tooltips in the DOM
    initializeTooltips() {
      document.querySelectorAll('[data-bs-toggle="tooltip"]')
        .forEach(tooltip => {
          new Tooltip(tooltip);
        });
    },

    // Initialize popovers in the DOM
    initializePopovers() {
      document.querySelectorAll('[data-bs-toggle="popover"]').
        forEach(el => {
          // Avoid duplicating instances if re-initialized
          const instance = Popover.getInstance(el);
          if (!instance) {
            Popover.getOrCreateInstance(el);
          }
        });
    },

    viewDatasets() {
      this.datasetToChange = this.currentDataset;
      this.datasetsToDelete = [];
      var modalElement = document.getElementById("datasetModal");
      if (modalElement) {
        var modal = new Modal(modalElement);
        modal.show();
      }

      this.isLoadingDatasets = true;
      if (!this.hasDatasets) {
        this.$store.commit("setProgress", { active: true, percent: 0, message: "Loading datasets..." });
        this.$store.commit("setStatus", { type: "info", message: "Loading datasets from server..." });
  axios.get(`${this.baseURL}/listDatasets`).then(response => {
          this.uploadedDatasets = response.data.datasets;
          this.$store.commit("setProgress", { active: false, percent: 100, message: "Datasets loaded" });
          this.$store.commit("setStatus", { type: "success", message: "Datasets loaded successfully!" });
        })
        .catch(error => {
          this.$store.commit("setProgress", { active: false, percent: 0, message: "Failed to load datasets" });
          this.$store.commit("setStatus", { type: "danger", message: `Fetch saved datasets failed. ${error}` });
        });
      }
      this.isLoadingDatasets = false;
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
      this.$store.commit("setFileData", {
        dataset: {
          name: this.currentDataset?.name || null,
          type: this.isNetCDF ? 'netcdf' : 'plain',
          content: this.fileContent,
          dimensions: [Number(this.width), Number(this.height), Number(this.depth)],
          precision: this.precision,
          vars: this.currentDataset?.vars || undefined,
          size: this.currentDataset?.size || undefined,
        }
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

      // Set progress bar active in store
      this.$store.commit("setProgress", { active: true, percent: 0, message: "Uploading file..." });
      this.$store.commit("setStatus", { type: "info", message: "Uploading file..." });

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
            const percent = Math.round((eventData.loaded / eventData.total) * 100);
            this.$store.commit("setProgress", { active: true, percent, message: `Uploading... ${percent}%` });
          }
        }
      }).then(response => {
        const serverDataset = response.data["dataset"] || {};
        this.$store.commit("setProgress", { active: false, percent: 100, message: "Upload complete" });
        this.$store.commit("setStatus", { type: "success", message: "Uploaded file successfully!" });
        // update the cached dataset list
        if (this.uploadedDatasets && serverDataset?.name) {
          this.uploadedDatasets[serverDataset.name] = serverDataset;
        }
        // Persist dataset in store (avoid local copy)
        if (this.isNetCDF) {
          this.$store.commit("setFileData", {
            dataset: {
              name: serverDataset?.name || null,
              type: "netcdf",
              content: null,
              dimensions: serverDataset?.dimensions || null,
              precision: serverDataset?.precision || "",
              vars: serverDataset?.vars || undefined,
              size: serverDataset?.size || undefined,
            }
          });
        } else {
          this.$store.commit("setFileData", {
            dataset: {
              name: serverDataset?.name || null,
              type: "plain",
              content: this.fileContent,
              dimensions: [Number(this.width), Number(this.height), Number(this.depth)],
              precision: this.precision,
              // vars will be cleared in the store for plain datasets
              vars: undefined,
              size: undefined,
            }
          });
        }
      })
      .catch(error => {
        this.$store.commit("setProgress", { active: false, percent: 0, message: "Upload failed" });
        this.$store.commit("setStatus", { type: "danger", message: `Upload file failed. ${error}` });
      });
    },

    async processChanges() {
      var btn = document.getElementById("viewDatasetsBtn");
      btn.disabled = true;
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
          // Show progress in status bar
          this.$store.commit("setProgress", { active: true, percent: 0, message: "Downloading dataset..." });
          this.$store.commit("setStatus", { type: "info", message: "Downloading dataset..." });
          // Get the new file from the server asynchronously
          await axios.get(`${this.baseURL}/download`, {
            params: { filename: this.datasetToChange.name, filetype: this.datasetToChange.type },
            responseType: "arraybuffer",
            onDownloadProgress: (eventData) => {
              if (eventData.lengthComputable) {
                const percentComplete = Math.round((eventData.loaded / eventData.total) * 100);
                this.$store.commit("setProgress", { active: true, percent: percentComplete, message: `Downloading... ${percentComplete}%` });
              }
            }
          }).then(response => {
            this.isNetCDF = false;
            this.ncSelectedVar = "";
            this.fileContent = response.data;
            // Persist downloaded dataset in store
            this.$store.commit("setFileData", {
              dataset: {
                name: this.datasetToChange.name,
                type: "plain",
                content: this.fileContent,
                dimensions: [Number(this.width), Number(this.height), Number(this.depth)],
                precision: this.precision,
                vars: undefined,
                size: undefined,
              }
            });
            this.$store.commit("setProgress", { active: false, percent: 100, message: "Download complete" });
            this.$store.commit("setStatus", { type: "success", message: "Downloaded file successfully!" });
          }).catch(error => {
            this.$store.commit("setProgress", { active: false, percent: 0, message: "Download failed" });
            this.$store.commit("setStatus", { type: "danger", message: `Download file failed. ${error}` });
            console.error("Download file failed.", error);
          });
        }
        else if(this.datasetToChange.type === "netcdf") {
          this.ncSelectedVar = "";
          this.isNetCDF = true;
          this.$store.commit("setFileData", {
            dataset: {
              name: this.datasetToChange.name,
              type: "netcdf",
              content: null,
              dimensions: this.datasetToChange.dimensions || null,
              precision: this.datasetToChange.precision || "",
              vars: this.datasetToChange.vars || undefined,
              size: this.datasetToChange.size || undefined,
            }
          });
        }
      }
        
      // delete datasets
      if (this.datasetsToDelete.length > 0) {
        formData.append("deletedDatasets", JSON.stringify(this.datasetsToDelete));
        this.datasetsToDelete.forEach(key => delete this.uploadedDatasets[key]);
      }

      // check if there are any changes made 
      if (!formData.entries().next().done) {
        this.$store.commit("setProgress", { active: true, percent: 0, message: "Saving dataset changes..." });
        this.$store.commit("setStatus", { type: "info", message: "Saving dataset changes..." });
  await axios.post(`${this.baseURL}/updateDatasets`, formData).then(response => {
          if (!(JSON.stringify(this.uploadedDatasets) === JSON.stringify(response.data.datasets))) {
            console.error("uploadedDatasets are not equal!");
          }
          this.$store.commit("setProgress", { active: false, percent: 100, message: "Changes saved" });
          this.$store.commit("setStatus", { type: "success", message: "Dataset changes saved!" });
        })
        .catch(error => {
          this.$store.commit("setProgress", { active: false, percent: 0, message: "Save failed" });
          this.$store.commit("setStatus", { type: "danger", message: `Update datasets failed. ${error}` });
          console.error("Update datasets failed.", error);
        });
      }
      btn.disabled = false;
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
      let dtype = this.currentDataset.vars[this.ncSelectedVar].dtype;
      if (dtype === "float32") {
        this.precision = "f";
      }
      else if (dtype === "float64") {
        this.precision = "d";
      }

      // Set dimensions
      let dims = this.currentDataset.vars[this.ncSelectedVar].shape;
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

      this.$store.commit("setProgress", { active: true, percent: 0, message: "Downloading variable data..." });
      this.$store.commit("setStatus", { type: "info", message: "Downloading variable data..." });
    
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
            const percent = Math.round((eventData.loaded / eventData.total) * 100);
            this.$store.commit("setProgress", { active: true, percent, message: `Downloading... ${percent}%` });
          }

        }
      }).then(response => {
        this.fileContent = response.data;
        // console.log("file content:", this.fileContent);
        this.emitFileData();

        this.$store.commit("setProgress", { active: false, percent: 100, message: "Download complete" });
        this.$store.commit("setStatus", { type: "success", message: "Downloaded variable data successfully!" });
      }).catch(error => {
        this.$store.commit("setProgress", { active: false, percent: 0, message: "Download failed" });
        this.$store.commit("setStatus", { type: "danger", message: `Download file failed. ${error}` });
      });
    },
  },
  
};
</script>
