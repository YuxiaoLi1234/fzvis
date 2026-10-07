<template>
  <div class="container align-items-center">
    <h1 class="h4 px-2 mt-3">Dataset Settings
      <i
        type="button"
        class="bi bi-info-circle ms-2 fs-5"
        v-popover:right="{ html: true, content: 'Currently support <b>raw</b> and <b>NetCDF</b> file formats.' }"
      ></i>
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
                <option value="f">float32 (f)</option>
                <option value="d">float64 (d)</option>
                <option value="i8">int8 (i8)</option>
                <option value="u8">uint8 (u8)</option>
                <option value="i16">int16 (i16)</option>
                <option value="u16">uint16 (u16)</option>
                <option value="i32">int32 (i32)</option>
                <option value="u32">uint32 (u32)</option>
              </select>
            </div>
          </div>
        </div>
        <!-- endianness -->
        <div class="col-md-6">
          <div class="row g-1 align-items-center">
            <div class="col">
              <select class="form-select" aria-label="endianness" v-model="endianness">
                <option value="" disabled selected>Endianness</option>
                <option value="little">Little-endian</option>
                <option value="big">Big-endian</option>
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
    <button id="viewDatasetsBtn" type="button" class="btn btn-info ms-2 my-1" @click="viewDatasets" :disabled="isApplyingDatasetSelection || isLoadingDatasets" title="View all uploaded datasets">View datasets</button>
    <div v-if="currentDataset == null" class="alert alert-danger mt-1">
      No dataset selected for processing.
    </div>
    <div v-else class="alert alert-success mt-1">
      Current dataset: 
      <strong>{{ $maskDisplayPath(currentDataset.name) }}</strong>
    </div>

    <!-- NetCDF file explorer -->
    <div v-show="isNetCDF">
      <NetCDFControls
        v-if="currentDataset && isNetCDF"
        :dataset="currentDataset"
        @variable-loaded="handleNetCDFVariableLoaded"
      />
    </div>
    <!-- Dataset modal -->
    <div ref="datasetModalRef" id="datasetModal" class="modal fade" data-bs-backdrop="static" tabindex="-1" aria-labelledby="datasetModalLabel" aria-hidden="true">
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
                    {{ $maskDisplayPath(dataset.name) }}
                    <span class="badge bg-secondary" v-if="dataset.type === 'raw' && dataset.precision === 'f'">float32</span>
                    <span class="badge bg-secondary" v-if="dataset.type === 'raw' && dataset.precision === 'd'">float64</span>
                    <span class="badge bg-secondary" v-if="dataset.type === 'raw' && dataset.precision === 'i8'">int8</span>
                    <span class="badge bg-secondary" v-if="dataset.type === 'raw' && dataset.precision === 'u8'">uint8</span>
                    <span class="badge bg-secondary" v-if="dataset.type === 'raw' && dataset.precision === 'i16'">int16</span>
                    <span class="badge bg-secondary" v-if="dataset.type === 'raw' && dataset.precision === 'u16'">uint16</span>
                    <span class="badge bg-secondary" v-if="dataset.type === 'raw' && dataset.precision === 'i32'">int32</span>
                    <span class="badge bg-secondary" v-if="dataset.type === 'raw' && dataset.precision === 'u32'">uint32</span>
                    <span class="badge bg-info ms-1">{{ dataset.size }}</span>
                  </div>
                  <div v-if="dataset.type === 'raw'">
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
                    @click="selectDataset(dataset)">
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
import { Modal } from 'bootstrap';
import NetCDFControls from './NetCDFControls.vue';
import {
  listDatasets,
  uploadDataset,
  updateDatasets,
  downloadDataset,
} from '@/api/datasets';

export default {
  name: 'InputDataset',
  components: {
    NetCDFControls,
  },
  emits: ['dataset-fetch-start', 'dataset-fetch-complete', 'dataset-fetch-error'],

  data() {
    return {
      depth: null,
      width: null,
      height: null,
      precision: "",
      endianness: "little",
      fileContent: "",
      file: null,
      datasetToChange: null,
      isLoadingDatasets: false,
      uploadedDatasets: [],
      datasetsToDelete:[],
      isApplyingDatasetSelection: false,
      lastDatasetHistoryName: null,
      isNetCDF: false,
      datasetModalInstance: null,
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
        return this.width && this.height && this.depth && this.precision && this.endianness;
      }
      // Upload a new dataset
      return this.file && this.width && this.height && this.depth && this.precision && this.endianness;
    },
  },
  
  watch: {
    currentDataset(newVal, oldVal) {
      this.fillFieldsFromDataset();
      if (newVal && newVal !== oldVal) {
        const nextName = newVal.name || null;
        const prevName = oldVal?.name || null;
        if (nextName && nextName !== prevName && nextName !== this.lastDatasetHistoryName) {
          this.$store.commit('addHistory', {
            kind: 'dataset',
            text: `Changed data file to: ${newVal.name}`,
            timestamp: Date.now()
          });
          this.lastDatasetHistoryName = nextName;
        }
      }
    }
  },

  mounted() {
    this.fillFieldsFromDataset();
    if (this.$refs.datasetModalRef) {
      this.datasetModalInstance = Modal.getOrCreateInstance(this.$refs.datasetModalRef);
    }
  },

  beforeUnmount() {
    if (this.datasetModalInstance) {
      this.datasetModalInstance.hide();
      this.datasetModalInstance.dispose();
      this.datasetModalInstance = null;
    }
  },

  methods:{
    fillFieldsFromDataset() {
      const ds = this.currentDataset;
      if (!ds) {
        this.isNetCDF = false;
        this.precision = "";
        this.endianness = "little";
        this.width = null;
        this.height = null;
        this.depth = null;
        return;
      }
      this.isNetCDF = ds.type === 'netcdf';
      if (ds.type === 'raw') {
        const dims = Array.isArray(ds.dimensions)
          ? ds.dimensions
          : [ds.width, ds.height, ds.depth];
        this.width = Number(dims?.[0]) || null;
        this.height = Number(dims?.[1]) || null;
        this.depth = Number(dims?.[2]) || null;
      if (ds.precision) this.precision = ds.precision;
      if (ds.endianness) this.endianness = ds.endianness;
      }
    },

    async viewDatasets() {
      this.datasetToChange = this.currentDataset;
      this.datasetsToDelete = [];
      this.resetDatasetModalFeedback();
      if (this.$refs.datasetModalRef) {
        this.datasetModalInstance = this.datasetModalInstance || Modal.getOrCreateInstance(this.$refs.datasetModalRef);
        this.datasetModalInstance.show();
      }

      this.isLoadingDatasets = true;
      if (!this.hasDatasets) {
        this.$store.commit("setProgress", { active: true, percent: 0, message: "Loading datasets..." });
        this.$store.commit("setStatus", { type: "info", message: "Loading datasets from server..." });
        try {
          const data = await listDatasets();
          this.uploadedDatasets = data.datasets || {};
          this.$store.commit("setProgress", { active: false, percent: 100, message: "Datasets loaded" });
          this.$store.commit("setStatus", { type: "success", message: "Datasets loaded successfully!" });
        } catch (error) {
          this.$store.commit("setProgress", { active: false, percent: 0, message: "Failed to load datasets" });
          this.$store.commit("setStatus", { type: "danger", message: `Fetch saved datasets failed. ${error}` });
        }
      }
      this.isLoadingDatasets = false;
    },

    resetDatasetModalFeedback() {
      this.isApplyingDatasetSelection = false;
    },

    selectDataset(dataset) {
      if (this.isApplyingDatasetSelection) return;
      this.datasetToChange = dataset;
      this.resetDatasetModalFeedback();
    },

    async handleFileChange(event) {
      const newFile = event.target.files[0];
      if (newFile) {
        this.file = newFile;
        // Handle NetCDF file format
        const validExtensions = [".nc", ".cdf", ".nc4"];
        const filename = newFile.name.toLowerCase();
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
          type: this.isNetCDF ? 'netcdf' : 'raw',
          content: this.fileContent,
          dimensions: [Number(this.width), Number(this.height), Number(this.depth)],
          precision: this.precision,
          endianness: this.endianness,
          vars: this.currentDataset?.vars || undefined,
          size: this.currentDataset?.size || undefined,
        }
      });
      this.$store.commit("setComparisonData", null);
      if (!this.isNetCDF && this.fileContent) {
        this.logDataRange(this.fileContent, this.precision, 'Local dataset');
      }
    },

    async uploadFile() {
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
        formData.append("type", "raw");
        formData.append("width", this.width);
        formData.append("height", this.height);
        formData.append("depth", this.depth);
        formData.append("precision", this.precision);
        formData.append("endianness", this.endianness);
      }

      try {
        const data = await uploadDataset(formData, (eventData) => {
          if (eventData.lengthComputable) {
            const percent = Math.round((eventData.loaded / eventData.total) * 100);
            this.$store.commit("setProgress", { active: true, percent, message: `Uploading... ${percent}%` });
          }
        });

        const serverDataset = data.dataset || {};
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
              endianness: serverDataset?.endianness || "little",
              vars: serverDataset?.vars || undefined,
              size: serverDataset?.size || undefined,
            }
          });
        } else {
          this.$store.commit("setFileData", {
            dataset: {
              name: serverDataset?.name || null,
              type: "raw",
              content: this.fileContent,
              dimensions: [Number(this.width), Number(this.height), Number(this.depth)],
              precision: this.precision,
              endianness: this.endianness,
              // vars will be cleared in the store for raw datasets
              vars: undefined,
              size: undefined,
            }
          });
          if (this.fileContent) {
            this.logDataRange(this.fileContent, this.precision, serverDataset?.name || 'Uploaded dataset');
          }
        }
      } catch (error) {
        this.$store.commit("setProgress", { active: false, percent: 0, message: "Upload failed" });
        this.$store.commit("setStatus", { type: "danger", message: `Upload file failed. ${error}` });
      }
    },

    async processChanges() {
      const formData = new FormData();
      if (this.currentDataset != this.datasetToChange) {
        this.isApplyingDatasetSelection = true;
        this.$store.commit("setTimeVarying", false);
        formData.append("currentDataset", JSON.stringify(this.datasetToChange));
        this.file = null;   // reset the file if the user has previously selected one
        // Handle different data file types
        if (this.datasetToChange.type === "raw") {
          this.$emit('dataset-fetch-start');
          this.width = this.datasetToChange.width;
          this.height = this.datasetToChange.height;
          this.depth = this.datasetToChange.depth;
          this.precision = this.datasetToChange.precision;
          this.endianness = this.datasetToChange.endianness || 'little';
          // Show progress in status bar
          this.$store.commit("setProgress", { active: true, percent: 0, message: "Downloading dataset..." });
          this.$store.commit("setStatus", { type: "info", message: "Downloading dataset..." });
          try {
            const data = await downloadDataset(this.datasetToChange.name, this.datasetToChange.type, (eventData) => {
              if (eventData.lengthComputable) {
                const percentComplete = Math.round((eventData.loaded / eventData.total) * 100);
                this.$store.commit("setProgress", { active: true, percent: percentComplete, message: `Downloading... ${percentComplete}%` });
              }
            });

            this.isNetCDF = false;
            this.fileContent = data;
            // Persist downloaded dataset in store
            this.$store.commit("setFileData", {
              dataset: {
                name: this.datasetToChange.name,
                type: "raw",
                content: this.fileContent,
                dimensions: [Number(this.width), Number(this.height), Number(this.depth)],
                precision: this.precision,
                endianness: this.endianness,
                vars: undefined,
                size: undefined,
              }
            });
            if (this.fileContent) {
              this.logDataRange(this.fileContent, this.precision, this.datasetToChange.name);
            }
            this.$store.commit("setProgress", { active: false, percent: 100, message: "Download complete" });
            this.$store.commit("setStatus", { type: "success", message: "Downloaded file successfully!" });
            this.isApplyingDatasetSelection = false;
            this.$emit('dataset-fetch-complete');
          } catch (error) {
            this.resetDatasetModalFeedback();
            this.$emit('dataset-fetch-error');
            this.$store.commit("setProgress", { active: false, percent: 0, message: "Download failed" });
            this.$store.commit("setStatus", { type: "danger", message: `Download file failed. ${error}` });
            console.error("Download file failed.", error);
          }
        }
        else if (this.datasetToChange.type === "netcdf") {
          this.$emit('dataset-fetch-start');
          this.isNetCDF = true;
          this.$store.commit("setFileData", {
              dataset: {
                name: this.datasetToChange.name,
                type: "netcdf",
                content: null,
                dimensions: this.datasetToChange.dimensions || null,
                precision: this.datasetToChange.precision || "",
                endianness: this.datasetToChange.endianness || "little",
                vars: this.datasetToChange.vars || undefined,
                size: this.datasetToChange.size || undefined,
              }
            });
          this.isApplyingDatasetSelection = false;
          this.$emit('dataset-fetch-complete');
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
        try {
          const data = await updateDatasets(formData);
          if (!(JSON.stringify(this.uploadedDatasets) === JSON.stringify(data.datasets))) {
            console.error("uploadedDatasets are not equal!");
          }
          this.$store.commit("setProgress", { active: false, percent: 100, message: "Changes saved" });
          this.$store.commit("setStatus", { type: "success", message: "Dataset changes saved!" });
        } catch (error) {
          this.resetDatasetModalFeedback();
          this.$store.commit("setProgress", { active: false, percent: 0, message: "Save failed" });
          this.$store.commit("setStatus", { type: "danger", message: `Update datasets failed. ${error}` });
          console.error("Update datasets failed.", error);
        }
      }
      if (!this.isApplyingDatasetSelection) {
        this.resetDatasetModalFeedback();
      }
    },

    handleNetCDFVariableLoaded({ fileContent, precision, width, height, depth }) {
      this.fileContent = fileContent;
      this.precision = precision;
      this.width = width;
      this.height = height;
      this.depth = depth;
      this.emitFileData();
    },

    getTypedArrayConstructor(precision) {
      const map = {
        f: Float32Array,
        d: Float64Array,
        i8: Int8Array,
        u8: Uint8Array,
        i16: Int16Array,
        u16: Uint16Array,
        i32: Int32Array,
        u32: Uint32Array,
      };
      return map[precision] || null;
    },

    logDataRange(buffer, precision, label = 'dataset', endianness = this.endianness) {
      const ctor = this.getTypedArrayConstructor(precision);
      if (!ctor) {
        console.warn(`[Dataset] Unsupported precision '${precision}' for range log.`);
        return;
      }
      const viewBuffer = this.maybeSwapEndian(buffer, precision, endianness);
      const view = new ctor(viewBuffer);
      let min = Infinity;
      let max = -Infinity;
      for (let i = 0; i < view.length; i += 1) {
        const v = view[i];
        if (Number.isFinite(v)) {
          if (v < min) min = v;
          if (v > max) max = v;
        }
      }
      console.log(`[Dataset] ${label} range (${precision}): [${min}, ${max}]`);
    },

    maybeSwapEndian(buffer, precision, endianness) {
      if (!buffer || !(buffer instanceof ArrayBuffer)) return buffer;
      if (!endianness || endianness === 'little') return buffer;
      const bytesPerElement = {
        f: 4, d: 8,
        i8: 1, u8: 1,
        i16: 2, u16: 2,
        i32: 4, u32: 4,
      }[precision] || 1;
      if (bytesPerElement === 1) return buffer;
      const src = new Uint8Array(buffer);
      const out = new Uint8Array(src.length);
      for (let i = 0; i < src.length; i += bytesPerElement) {
        for (let j = 0; j < bytesPerElement; j += 1) {
          out[i + j] = src[i + bytesPerElement - 1 - j];
        }
      }
      return out.buffer;
    },
  },
  
};
</script>
