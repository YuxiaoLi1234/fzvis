<template>
  <div class="container align-items-center" id="modals">

      <!-- Options panel -->
      <div class="options-panel px-2">
        <h1 class="h3 pt-3 pb-2">Available Options</h1>
        <div class="dropdown">
          <select id="compressor" class="form-select m-1" aria-label="compressor" v-model="selectedCompressor" @change="getCompressorConfigs">
            <option value=null disabled selected>Select compressor</option>
            <option v-for="compressor in availableOptions?.Compressor" :key="compressor.id" :value="compressor">{{ compressor }}</option>
          </select>
          <span class="text-warning text-align-center">
            <i class="bi bi-exclamation-triangle-fill me-1"></i>
            Not all compressors are fully supported or tested.
          </span>
        </div>
        
        <div v-if="selectedCompressor" class="p-2">
          <div class="card">
            <div class="card-body" v-if="selectedCompressor in this.compressorOptions">
              <h5 class="card-title">{{ selectedCompressor }}</h5>
              <p class="card-text" v-show="compressorOptions[selectedCompressor]['Highlevel'].length > 0">High-level options are listed here.</p>
              <div class="d-flex flex-wrap mb-2" v-show="compressorOptions[selectedCompressor]['Highlevel'].length > 0">
                <div class="me-2 mb-2" v-for="option in compressorOptions[selectedCompressor]['Highlevel']" :key="option.id">
                  <div class="form-floating">
                    <input v-if="option.label == 'Nthreads'" type="number" class="form-control" style="width:120px;" title="Number of threads to use" :id="option.id" :placeholder="option.label" min="1" step="1" v-model="configuredValues['Highlevel'][option.id]">
                    <input v-else type="number" class="form-control" style="width:120px;" :title="optionDocs[option.id]" :id="option.id" :placeholder="option.label" min="0" step="any" v-model="configuredValues['Highlevel'][option.id]">
                    <label :for="option.id">{{ option.label }}</label>
                  </div>
                </div>
              </div>

              <div class="d-flex align-items-center mb-2">
                <p class="card-text mb-0">Detailed options are listed here.</p>
                <button class="btn btn-outline-success btn-sm ms-2" @click="randomlyPickOptions" type="button">
                  Pick for me
                </button>
              </div>

              <div id="detailConfigPanel">
                <div class="d-flex align-items-center mb-2 me-2" v-for="(optionList, optionName) in compressorOptions[selectedCompressor]['Detail']" :key="optionName">
                  <multiselect v-model="configuredValues['Detail'][optionName]" :options="optionList" :searchable="true" :multiple="optionName === 'Metric'" :close-on-select="optionName !== 'Metric'" :clear-on-select="false" :placeholder="`Select ${optionName}`" label="label" show-label="false" track-by="id" :title="optionDocs[optionList[0].type] || 'No documentation available'" aria-label="optionName">
                  </multiselect>
                </div>
              </div>
              <small class="d-block mb-2 text-muted">
                {{ isConfigValid ? "Click submit to record configuration." : "Please fill all fields to submit." }}
              </small>
              <button type="button" class="btn btn-primary me-2" :disabled="!isConfigValid" data-bs-toggle="modal" data-bs-target="#saveConfigModal" @click="currentConfigName = selectedCompressor + '_' + getFormattedTimestamp()">Save</button>
              <button type="reset" class="btn btn-secondary" @click="resetConfiguredValues">Reset</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Save configuration modal -->
      <div id="saveConfigModal" class="modal fade" tabindex="-1" aria-labelledby="saveConfigModalLabel" data-bs-keyboard="false" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered modal-sm">
          <div class="modal-content">
            <div class="modal-header">
              <h1 class="modal-title fs-5" id="saveConfigModalLabel">Save current configuration</h1>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
              <div class="form-floating">
                <input type="text" class="form-control" id="floatingConfigName" placeholder="Configuration name" v-model="currentConfigName">
                <label for="floatingConfigName">Configuration name</label>
              </div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
              <button type="button" class="btn btn-primary" data-bs-dismiss="modal" @click="handleConfigurationCheck" :disabled="currentConfigName == ''">Save changes</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Confirmation modal for replacing existing configuration -->
      <div id="replaceConfigModal" class="modal fade" tabindex="-1" aria-labelledby="replaceConfigModalLabel" data-bs-backdrop="static" data-bs-keyboard="false" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered modal-sm">
          <div class="modal-content">
            <div class="modal-header">
              <h1 class="modal-title fs-5" id="replaceConfigModalLabel">Configuration Already Exists</h1>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
              <p>A configuration named "<strong>{{ currentConfigName }}</strong>" already exists. Do you want to replace it?</p>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal" data-bs-toggle="modal" data-bs-target="#saveConfigModal">Cancel</button>
              <button type="button" class="btn btn-warning" data-bs-dismiss="modal" @click="handleConfigurationSave">Replace</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Base configurations panel with force-directed graph -->
      <div class="p-2">
        <div class="card border-primary" style="height: 350px;">
          <div class="card-header d-flex justify-content-between align-items-center">
            <h6 class="mb-0">Configuration Graph</h6>
            <div class="d-flex align-items-center">
              <span class="badge bg-info me-2">{{ Object.keys(baseConfigurations).length }}</span>
              <button class="btn btn-outline-primary btn-sm" @click="openLargeGraphModal" title="Open Large View">
                <i class="bi bi-arrows-fullscreen"></i>
              </button>
            </div>
          </div>
          
          <div class="card-body p-2" style="height: calc(100% - 120px); overflow: hidden;">
            <!-- Graph container -->
            <div id="configuration-graph" ref="graphContainer" style="width: 100%; height: 100%; border: 1px solid #dee2e6; border-radius: 0.375rem; cursor: grab;">
              <svg ref="graphSvg" width="100%" height="100%"></svg>
            </div>
            
            <!-- No configurations message -->
            <div v-if="Object.keys(baseConfigurations).length === 0" class="text-center text-muted mt-3">
              <p class="mb-0">No saved configurations yet.</p>
            </div>
          </div>
          
          <div class="card-footer text-center" style="height: 60px;">
            <button type="button" class="btn btn-primary w-60" @click="submitConfigurations" :disabled="Object.keys(savedConfigurations).length === 0">
              Run All {{ Object.keys(savedConfigurations).length }} Configurations
            </button>
          </div>
        </div>
      </div>

      <!-- Large Graph Modal -->
      <div id="largeGraphModal" class="modal fade" tabindex="-1" aria-labelledby="largeGraphModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-fullscreen">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title" id="largeGraphModalLabel">Configuration Graph - Large View</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body p-0">
              <div id="large-configuration-graph" ref="largeGraphContainer" style="width: 100%; height: 100%; cursor: grab;">
                <svg ref="largeGraphSvg" width="100%" height="100%"></svg>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Node context menu -->
      <div id="node-context-menu" class="context-menu" style="display: none; position: absolute; z-index: 1000; background: white; border: 1px solid #ccc; border-radius: 4px; padding: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
        <div class="context-menu-item" @click="editNodeErrorBound" style="padding: 4px 8px; cursor: pointer; border-radius: 4px;">
          <i class="bi bi-pencil-square me-2"></i>Edit Error Bound
        </div>
        <div class="context-menu-item" @click="deleteNode" style="padding: 4px 8px; cursor: pointer; border-radius: 4px;">
          <i class="bi bi-trash me-2"></i>Delete
        </div>
        <div class="context-menu-item" @click="promoteToBase" style="padding: 4px 8px; cursor: pointer; border-radius: 4px;">
          <i class="bi bi-arrow-up-circle me-2"></i>Promote to Base
        </div>
        <div class="context-menu-item" @click="bulkGenerate" style="padding: 4px 8px; cursor: pointer; border-radius: 4px;">
          <i class="bi bi-lightning-charge me-2"></i>Bulk Generate
        </div>
      </div>
      
      <!-- Bulk generation modal -->
      <div id="bulkGenerationModal" class="modal fade" tabindex="-1" aria-labelledby="bulkGenerationModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered modal-sm">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title" id="bulkGenerationModalLabel">Bulk Configuration Generator</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
              <form>
                <div class="mb-3">
              <div class="form-floating">
                <input type="number" id="numConfigs" class="form-control" v-model="bulkSettings.count" min="1" max="1000" placeholder="Number of Configurations">
                <label for="numConfigs">Number of Configurations</label>
              </div>
                </div>
                <div class="mb-3">
              <div class="form-floating">
                <select id="generationType" class="form-select" v-model="bulkSettings.distribution">
                  <option value="linear">Linear Distribution</option>
                  <option value="exponential">Exponential Distribution</option>
                  <option value="random">Random Distribution</option>
                </select>
                <label for="generationType">Generation Type</label>
              </div>
                </div>
                <div class="mb-3">
              <div class="form-floating">
                <input type="number" id="minBound" class="form-control" v-model="bulkSettings.minBound" step="0.00001" placeholder="Min Error Bound">
                <label for="minBound">Min Error Bound</label>
              </div>
                </div>
                <div class="mb-3">
              <div class="form-floating">
                <input type="number" id="maxBound" class="form-control" v-model="bulkSettings.maxBound" step="0.00001" placeholder="Max Error Bound">
                <label for="maxBound">Max Error Bound</label>
              </div>
                </div>
              </form>
            </div>
            <div class="modal-footer d-flex justify-content-between">
              <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancel</button>
              <button type="button" class="btn btn-primary" data-bs-dismiss="modal" :disabled="!isBulkConfigValid" @click="generateBulkConfigurations">Generate</button>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Alert message box -->
      <div id="compressorAlert" class="alert alert-dismissible fade" role="alert" tabindex="-1">
        <span id="compressorAlertMessage">Placeholder</span>
        <!-- <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button> -->
      </div>

    </div>
</template>


<script>
import axios from 'axios';
import { Modal, Popover } from 'bootstrap';
import Multiselect from 'vue-multiselect';
import * as d3 from 'd3';

export default {
  components: {
    Multiselect,
  },
  data() {
    return {
      baseURL: localStorage.getItem("fzvis_server_address"),
      availableOptions: {
        "Compressor": [
          { id: "binning", label: "Compressor: Binning", type: "compressor" },
          { id: "chunking", label: "Compressor: Chunking", type: "compressor" },
          { id: "roibin", label: "Compressor: Roibin", type: "compressor" },
          { id: "sz3", label: "Compressor: SZ3", type: "compressor" },
          { id: "zfp", label: "Compressor: ZFP", type: "compressor" },
        ]
      },
      initialOptions:{
        "Compressor": [ "sz3", "zfp" ]
      },
      baseConfigurations: {},
      derivedConfigurations: {},
      compressorOptions: {},
      configuredValues: {},
      currentConfigName: "", // input configuration name
      optionDocs: {},        // documentation for each option
      savedConfigurations: {}, // all the saved configurations
      selectedCompressor: null,
      selectedBaseConfig: null,
      editingConfig: null,
      editingData: {},
      compare_data: {},
      formattedConfigurations: null,
      formData: new FormData(),
      bulkSettings: {
        count: 10,
        minBound: 0.00001,
        maxBound: 0.001,
        distribution: "linear",
      },
      expandedBaseConfigs: {}, // track which base configs are expanded
      editingErrorBound: {},
      // Force-directed graph properties
      graphData: { nodes: [], links: [] },
      simulation: null,
      selectedNode: null,
      isDragging: false,
      contextMenuTarget: null,
      resizeObserver: null,
      // Zoom and pan functionality
      zoomBehavior: null,
      largeZoomBehavior: null,
      largeSimulation: null,
    };
  },

  computed: {
    isBulkConfigValid() {
      const { minBound, maxBound } = this.bulkSettings;
      return minBound > 0 && maxBound > minBound;
    },

    isConfigValid() {
      const options = this.compressorOptions[this.selectedCompressor]["Detail"];
      if (!options) return false;

      return Object.values(this.configuredValues["Detail"]).every((item) => {
        // // handle error bound: must have a value
        // if (item?.label?.startsWith("Error Bound:")) {
        //   return item?.value !== undefined && item.value !== "";
        // }

        // handle arrays: must be non-empty
        if (Array.isArray(item)) {
          return item.length > 0;
        }

        // regular options: must have an id
        return item?.id !== undefined;
      });
    },

    fileData() {
      return this.$store.state.fileData;
    }
  },

  watch: {
    baseConfigurations: {
      handler() {
        this.initializePopovers();
        this.updateGraphData();
      },
      deep: true,
    },
    
    derivedConfigurations: {
      handler() {
        this.savedConfigurations = Object.values(this.derivedConfigurations)
          .reduce((acc, derivedConfigs) => {
            Object.entries(derivedConfigs).forEach(([configName, config]) => {
              acc[configName] = config;
            });
            return acc;
          }, {}
        );
        this.updateGraphData();
      },
      deep: true,
    },
    // "configuredValues.Highlevel": {
    //   handler() {
    //     this.resetErrorBound();
    //   },
    //   deep: true,
    // }
  },

  mounted: function () {
    this.getAvailableCompressors();
    // Initialize graph after component is mounted and refs are available
    this.$nextTick(() => {
      this.initializeGraph();
      this.setupResizeObserver();
    });
    // Hide context menu when clicking elsewhere
    document.addEventListener('click', this.hideContextMenu);
    
    // Listen for tab changes to re-initialize graph when compressor tab becomes active
    const compressorTab = document.getElementById('compressor-tab');
    if (compressorTab) {
      compressorTab.addEventListener('shown.bs.tab', () => {
        this.$nextTick(() => {
          this.initializeGraph();
        });
      });
    }
  },

  beforeUnmount() {
    document.removeEventListener('click', this.hideContextMenu);
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
    }
  },

  methods: {
    formatBaseConfig(config) {
      let content = "";
      content += Object.entries(config.compressor_config || {})
      .map(([key, value]) => `<strong>${key.split(':').pop()}:</strong> ${value}`)
      .join("<br>");
      content += "<br>";
      content += Object.entries(config.early_config || {})
      .map(([key, value]) => `<strong>${key.split(':').pop()}:</strong> ${value}`)
      .join("<br>");
      return content;
    },

    formatConfig(compressorConfig) {
      if (!compressorConfig) return {};

      return Object.fromEntries(
        Object.entries(compressorConfig).map(
          ([key, value]) => [this.getFormattedKey(key), value]
        )
      );
    },

    generateBulkConfigurations() {
      if (!this.baseConfigurations[this.selectedBaseConfig]) {
        console.log("Base configuration not found:", this.selectedBaseConfig);
        return;
      }

      const baseConfig = this.baseConfigurations[this.selectedBaseConfig];
      console.log("baseConfig:", baseConfig);
      const { count, minBound, maxBound, distribution } = this.bulkSettings;
      
      // Validate inputs
      if (!count || count <= 0 || !minBound || !maxBound) {
        console.log("Invalid input values for bulk generation.");
        return;
      }
      
      let errorBoundKeys = []
      console.log("baseConfig.compressor_id:", baseConfig.compressor_id);
      if (baseConfig?.compressor_id === "sz3") {
        const errorBoundModeKey = Object.keys(baseConfig.compressor_config).find(key => key.includes("error_bound_mode_str"));
        const errorBoundMode = errorBoundModeKey ? baseConfig.compressor_config[errorBoundModeKey].toLowerCase() : "abs"; // default to "abs" if not found
        if (errorBoundMode.includes("abs")) {
          errorBoundKeys.push(baseConfig.compressor_id + ":" + "abs_error_bound");
        } 
        if (errorBoundMode.includes("rel")) {
          errorBoundKeys.push(baseConfig.compressor_id + ":" + "rel_error_bound");
        } 
        if (errorBoundMode.includes("psnr")) {
          errorBoundKeys.push(baseConfig.compressor_id + ":" + "psnr_error_bound");
        }
        if (errorBoundMode.includes("norm")) {
          errorBoundKeys.push(baseConfig.compressor_id + ":" + "l2_norm_error_bound");
        }
      }
      
      // Generate configurations with different error bounds
      for (let i = 1; i <= count; i++) {
        let errorBound;
        
        // Calculate error bound based on distribution type
        if (distribution === 'linear') {
          errorBound = minBound + ((maxBound - minBound) / (count - 1)) * (i - 1);
        }
        else if (distribution === 'exponential') {
          // Exponential distribution
          const lambda = Math.log(maxBound / minBound) / count;
          errorBound = minBound * Math.exp(lambda * i);
        }
        else if (distribution === 'random') {
          // Random distribution
          errorBound = Math.random() * (maxBound - minBound) + minBound;
        }
        
        // Create a deep copy of the base configuration
        const newConfig = JSON.parse(JSON.stringify(baseConfig));
        newConfig["base_config"] = this.selectedBaseConfig;
        errorBoundKeys.forEach(ek => {
          newConfig.compressor_config[ek] = errorBound;
        });
        
        // Create a unique name for this configuration
        const configName = this.selectedBaseConfig + "_" + String(i).padStart(3, '0');
        this.derivedConfigurations[this.selectedBaseConfig][configName] = newConfig;
      }
    },

    getAvailableCompressors() {
      const alertBox = document.getElementById("compressorAlert");
      const alertMessage = document.getElementById("compressorAlertMessage");
      axios.get(`${this.baseURL}/allCompressors`).then(response => {
        this.initialOptions["Compressor"] = response.data.compressors;
      })
      .catch(error => {
        if (alertBox && alertMessage) {
          alertBox.classList.remove("alert-success");
          alertBox.classList.add("alert-danger", "show");
          alertMessage.textContent = `Fetch available compressors failed. ${error}`;
          // Auto dismiss
          setTimeout(() => {
            alertBox.classList.remove("show");
          }, 6000);
        }
      });
      this.availableOptions = this.initialOptions;
    },

    getCompressorConfigs() {
      // Only send the request if options for the selected compressor haven't been fetched before
      if (!(this.selectedCompressor in this.compressorOptions)) {
        let formData = new FormData();
        formData.append("get_options", 1);
        formData.append("compressor_id", this.selectedCompressor);

        var formattedOptions = {};
        axios.post(`${this.baseURL}/indexlist`, formData).then(response => {
          const doc = response.data.doc;
          Object.entries(doc).forEach(([key, value]) => {
            this.optionDocs[key] = value;
          });

          const highlevel = response.data.highlevel;
          formattedOptions["Highlevel"] = highlevel.map(item => ({
            id: item,
            label: this.getFormattedKey(item),
            type: "Highlevel",
          }));

          const rawOptions = response.data.options;
          const filteredOptions = {...Object.fromEntries(Object.entries(rawOptions).filter(([key]) => key.startsWith(this.selectedCompressor)))};

          formattedOptions["Detail"] = {
            ...Object.entries(filteredOptions).reduce((acc, [category, values]) => {
              // remove `sz3:` prefix and `_str` suffix
              const formattedCategory = this.getFormattedKey(category);
              
              if (Array.isArray(values)) {
                acc[formattedCategory] = values.map(value => ({
                  id: value,
                  label: `${formattedCategory}: ${value}`, // format label for display
                  type: category,
                }));
              } else {
                // For non-array categories, convert to object with formatted keys
                acc[formattedCategory] = [{
                  id: values,
                  label: `${formattedCategory}: ${values}`, // format label for display
                  type: category,
                }];
              }
              return acc;
            }, {})
          };
          formattedOptions["Detail"]["Metric"] = formattedOptions["Detail"]["Metric"].filter(item => item.id !== "composite");
          
          // // Manually add error bound option if missing
          // const hasErrorBound = Object.keys(formattedOptions["Detail"]).some(category => category.toLowerCase().includes("error bound"));
          // if (!hasErrorBound) {
          //   formattedOptions["Detail"]["Error Bound"] = [{
          //     id: "pressio:abs",
          //     label: "Error Bound: ABS",
          //     type: "error bound",
          //   }];
          // }

          this.configuredValues = {};
          Object.entries(formattedOptions).forEach(([category, options]) => {
            this.configuredValues[category] = {};
            // High-level options should be an array
            if (Array.isArray(options)) {
              options.forEach(item => {
                this.configuredValues[category][item.id] = null;
              });
            }
            else {
              Object.keys(options).forEach(optionKey => {
                this.configuredValues[category][optionKey] = null;
              });
            }
          });
          this.compressorOptions[this.selectedCompressor] = formattedOptions;
          console.log("formattedOptions:", formattedOptions);
        })
        .catch(error => {
          console.error("Error submitting configuration:", error.response ? error.response.data : error.message);
          alert("An error occurred. Please check the console for details.");
        });
      }
      else {
        // Handle case where options already exist
        this.resetConfiguredValues();
      }
    },

    getErrorBoundKey(config) {
      // Find the error bound key in the compressor_config
      console.log("error bound key:", Object.keys(config.compressor_config)
        .find(key => key.endsWith('error_bound')) || '');
      return Object.keys(config.compressor_config)
        .find(key => key.endsWith('error_bound')) || '';
    },

    getFormattedTimestamp() {
      const pad = (n) => n.toString().padStart(2, "0");
      const now = new Date();
      const month = pad(now.getMonth() + 1);
      const day = pad(now.getDate());
      const hours = pad(now.getHours());
      const minutes = pad(now.getMinutes());
      // const seconds = pad(now.getSeconds());

      return `${month}_${day}_${hours}_${minutes}`;
    },

    getFormattedKey(key){
      return key
        .replace(/^.*?:/, "")               // remove namespace prefix like `sz3:` or `pressio:`
        .replace(/_str$/, "")               // remove `_str` suffix
        .replace(/_mode$/, "")              // remove `_mode` suffix
        .replace(/_algo$/, "")              // remove `_algo` suffix
        .replace("_error_bound", " Error Bound") // special handling
        .replace(/_/g, " ")                 // underscores to spaces
        .replace(/\b\w/g, c => c.toUpperCase()); // capitalize words
    },

    // handleHighLevelInput(optionId) {
    //   if (optionId) {
    //     if (optionId.toLowerCase().includes("abs")) {
    //       const selected = this.configuredValues["Detail"]?.["Error Bound"];
    //       if (selected) {
    //         this.configuredValues["Detail"]["Error Bound"].value = this.configuredValues["Highlevel"][optionId];
    //       }
    //     }
    //     else if (optionId.toLowerCase().includes("rel")) {
    //       const selected = this.configuredValues["Detail"]?.["Error Bound"];
    //       if (selected) {
    //         this.configuredValues["Detail"]["Error Bound"].value = this.configuredValues["Highlevel"][optionId];
    //       }
    //     }
    //   }
    // },

    handleConfigurationCheck() {
      if (this.baseConfigurations[this.currentConfigName]) {
        // Show confirmation modal
        const replaceModal = new Modal(document.getElementById("replaceConfigModal"));
        replaceModal.show();
      } else {
        // Save directly if no conflict
        this.handleConfigurationSave();
      }
    },

    handleConfigurationSave() {
      const config = {"compressor_config":{}};
      console.log("configuredValues", JSON.stringify(this.configuredValues));

      config.compressor_id = this.selectedCompressor;
      config["early_config"] = {
        "pressio:metric": "composite",
        "composite:plugins": [],
      };

      Object.entries(this.configuredValues["Highlevel"]).forEach(([key, value]) => {
        if (value !== null && value !== undefined) {
          config["compressor_config"][key] = value;
        }
      });
      Object.values(this.configuredValues["Detail"]).forEach((item) => {
        // if item is an array (only metrics right now?)
        if (Array.isArray(item)) {
          item.forEach(element => {
            if (element?.id) {
              config["early_config"]["composite:plugins"].push(element.id);
            }
          });
        }
        
        // value of error bound will be stored in highlevel?
        // else if (item.label.startsWith("Error Bound:")) {
        //   if(item.id.split(":")[0] != this.selectedCompressor){
        //     config["compressor_config"][item.id] = item.value
        //   }
        //   else{
        //     const errorMode = item.label.split(": ")[1];
        //     config["compressor_config"][`${this.selectedCompressor}:${errorMode.toLowerCase()}_error_bound`] = item.value;
        //   }
        // }
        else if(!item.label.startsWith("Compressor:")) {
          config["compressor_config"][item.type] = item.id;
        }
      });

      // Save current configuration
      // corrected config format:
      // savedConfig {"compressor_config":{"sz3:algorithm_str":"ALGO_INTERP","sz3:abs_error_bound":0.001,"sz3:intrep_algo_str":"INTERP_ALGO_CUBIC","sz3:metric":"composite"},"compressor_id":"sz3"}
      this.baseConfigurations[this.currentConfigName] = config;
      this.derivedConfigurations[this.currentConfigName] = {};
      console.log("baseConfigurations", JSON.stringify(this.baseConfigurations));
      this.currentConfigName = "";
    },

    handleOptionsChange(optionName) {
      if (optionName === "Error Bound") {
        const selected = this.configuredValues["Detail"]?.["Error Bound"];
        if (selected && selected.id.toLowerCase().includes("abs")) {
          this.configuredValues["Detail"]["Error Bound"].value = this.configuredValues["Highlevel"]["pressio:abs"];
        }
        if (selected && selected.id.toLowerCase().includes("rel")) {
          this.configuredValues["Detail"]["Error Bound"].value = this.configuredValues["Highlevel"]["pressio:rel"];
        }
      }
    },

    initializePopovers() {
      this.$nextTick(() => {
        document.querySelectorAll('[data-bs-toggle="popover"]')
          .forEach(popover => {
            const instance = Popover.getInstance(popover);
            if (instance) {
              instance.dispose();
            }
            // Create new popover
            new Popover(popover);
          });
      });
    },

    prepareBulkGeneration(name) {
      if (!this.baseConfigurations[name]) {
        console.log("Configuration not found:", name);
        return;
      }
      this.selectedBaseConfig = name;
    },

    // Randomly pick option values for the selected compressor
    randomlyPickOptions() {
      const detailOptions = this.compressorOptions[this.selectedCompressor]['Detail'];
      Object.keys(detailOptions).forEach(optionName => {
        const optionList = detailOptions[optionName];
        if (optionName === 'Metric') {
          // For Metric (multiple selection), use ["time", "size", "error_stat"]
          this.configuredValues['Detail'][optionName] = detailOptions['Metric'].filter(item => 
            ['time', 'size', 'error_stat'].includes(item.id)
          );
        }
        else {
          // For single selection options, pick one random option
          const randomIndex = Math.floor(Math.random() * optionList.length);
          this.configuredValues['Detail'][optionName] = optionList[randomIndex];
        }
      });
    },
    
    removeConfiguration(baseName, configName = "") {
      if (configName === "") {
        if (confirm(`Are you sure you want to delete "${baseName}"?`)) {
          delete this.baseConfigurations[baseName];
          delete this.expandedBaseConfigs[baseName];
          if (this.compare_data) {
            Object.keys(this.derivedConfigurations[baseName]).forEach(name => {
              delete this.compare_data[name];
            });
          }
          delete this.derivedConfigurations[baseName];
        }
      } else {
        if (confirm(`Are you sure you want to delete "${configName}"?`)) {
          delete this.derivedConfigurations[baseName][configName];
          if (this.compare_data && this.compare_data[configName]) {
            console.log("compare_data === store object?", this.compare_data === this.$store.state.comparisonData);
            delete this.compare_data[configName];
            console.log("After deletion:", this.compare_data);
            console.log("Store after:", this.$store.state.comparisonData);
          }
        }
      }
    },

    resetAvailableOptions() {
      this.availableOptions = [...this.initialOptions];
    },

    resetConfiguredValues() {
      // Handle case where options already exist
      this.configuredValues = {};
      const allOptions = this.compressorOptions[this.selectedCompressor];
      Object.entries(allOptions).forEach(([category, options]) => {
        this.configuredValues[category] = {};
        Object.keys(options).forEach(option => {
          this.configuredValues[category][option] = null;
        })
      });
    },

    submitConfigurations() {
      const alertBox = document.getElementById("compressorAlert");
      const alertMessage = document.getElementById("compressorAlertMessage");

      if (this.fileData) {
        console.log("savedConfigurations:", this.savedConfigurations);
        // const formattedConfigurations = Object.entries(this.savedConfigurations).map(([name, config]) => {
        //   return {
        //     compressor_id: config.compressor_id || "unknown",
        //     compressor_name: name,
        //     early_config: config["early_config"],
        //     compressor_config: config["compressor_config"],
        //   };
        // });
        // console.log("Formatted Configurations:", formattedConfigurations);
  
        // Clear out previous configurations
        if(this.formData.has("configurations")){
          this.formData.delete("configurations");
        }
  
        if(this.formData.has("get_options")){
          this.formData["get_options"] = 0;
        } else {
          this.formData.append("get_options", 0);
        }
        this.formData.append("configurations", JSON.stringify(this.savedConfigurations));
        this.compare_data = null;
        
        if (alertBox && alertMessage) {
          alertBox.classList.remove("alert-danger");
          alertBox.classList.remove("alert-success");
          alertBox.classList.add("alert-secondary", "show");
          alertMessage.textContent = "Processing...";
        }

        axios.post(`${this.baseURL}/indexlist`, this.formData).then(response => {
          this.compare_data = response.data;
          Object.keys(this.compare_data).forEach(key => {
            this.compare_data[key]["compressor_config"] = this.formatConfig(this.savedConfigurations[key]["compressor_config"]);
          });
          // console.log("compare_data:", this.compare_data);
          // console.log("compressor config:", Object.values(this.compare_data).map(d => d["compressor_config"]));
          // const names = Object.values(formattedConfigurations).map((d)=>d.compressor_name);
          // const configs = Object.values(formattedConfigurations).map((d)=>d.compressor_config);

          // this.compare_data = {
          //   "compressor_id":[],
          //   "bound":[],
          //   "metrics":[],
          // };

          // for (const key in response.data) {
          //   let element = response.data[key];
          //   this.compare_data["compressor_id"].push(element["compressor_id"]);
          //   this.compare_data["bound"].push(element["bound"]);
          //   if (element["metrics"]) {
          //     this.compare_data["metrics"].push(element["metrics"]);
          //   } else {
          //     console.warn("Metrics returned from the backend are null or undefined.");
          //   }
          // }

          // this.compare_data["compressor_name"] = names;
          // this.compare_data["compressor_config"] = configs;
          // this.compare_data["decp_data"] = response.data["decp_data"];
          this.$store.commit("setComparisonData", this.compare_data);
  
          if (alertBox && alertMessage) {
            alertBox.classList.remove("alert-danger");
            alertBox.classList.remove("alert-secondary");
            alertBox.classList.add("alert-success", "show");
            alertMessage.textContent = "Compression executed successfully!";
            // Auto dismiss
            setTimeout(() => {
              alertBox.classList.remove("show");
            }, 6000);
          }
        }).catch(error => {
          if (alertBox && alertMessage) {
            alertBox.classList.remove("alert-success");
            alertBox.classList.remove("alert-secondary");
            alertBox.classList.add("alert-danger", "show");
            if (error.response) {
              alertMessage.textContent = `Compression failed. ${error.response.data.error}`;
            } else {
              alertMessage.textContent = `Compression failed. ${error}`;
            }
            // Auto dismiss
            setTimeout(() => {
              alertBox.classList.remove("show");
            }, 8000);
          }
          console.error("Error submitting configuration:", error.response ? error.response.data : error.message);
          // alert("An error occurred. Please check the console for details.");
        });
        
        // return formattedConfigurations;
      }
      // No dataset file selected
      else {
        if (alertBox && alertMessage) {
          alertBox.classList.remove("alert-success");
          alertBox.classList.remove("alert-secondary");
          alertBox.classList.add("alert-danger", "show");
          alertMessage.textContent = "No dataset selected!";
        }
      }
    },

    toggleDerivedConfigsVisibility(baseConfigName) {
      // Initialize if needed
      if (this.expandedBaseConfigs[baseConfigName] === undefined) {
        this.expandedBaseConfigs[baseConfigName] = false;
      }
      this.expandedBaseConfigs[baseConfigName] = !this.expandedBaseConfigs[baseConfigName];
    },

    // Force-directed graph methods
    initializeGraph() {
      // Check if refs are available
      if (!this.$refs.graphContainer || !this.$refs.graphSvg) {
        console.warn('Graph container refs not available yet');
        return;
      }

      const width = this.$refs.graphContainer.clientWidth;
      const height = this.$refs.graphContainer.clientHeight;

      // Check if dimensions are valid
      if (width === 0 || height === 0) {
        console.warn('Graph container has invalid dimensions:', { width, height });
        // Use default dimensions if container isn't visible yet
        const defaultWidth = 600;
        const defaultHeight = 300;
        
        // Set explicit dimensions on the container
        this.$refs.graphContainer.style.width = defaultWidth + 'px';
        this.$refs.graphContainer.style.height = defaultHeight + 'px';
        
        // Use default dimensions for initialization
      this.initializeGraphWithDimensions(defaultWidth, defaultHeight);
      return;
    }

    this.initializeGraphWithDimensions(width, height);
  },

  initializeGraphWithDimensions(width, height) {
    const svg = d3.select(this.$refs.graphSvg)
      .attr('width', width)
      .attr('height', height);

    // Clear any existing content
    svg.selectAll("*").remove();

    // Create main group for zoom/pan
    const mainGroup = svg.append("g").attr("class", "main-group");

    // Create groups for different elements
    mainGroup.append("g").attr("class", "links");
    mainGroup.append("g").attr("class", "nodes");

    // Initialize zoom behavior
    this.zoomBehavior = d3.zoom()
      .scaleExtent([0.1, 4])
      .on("zoom", (event) => {
        console.log('Zoom event triggered:', event.transform);
        mainGroup.attr("transform", event.transform);
      });

    console.log('Applying zoom behavior to SVG...');
    svg.call(this.zoomBehavior);
    console.log('Zoom behavior applied successfully');
    
    // Test SVG event handling
    svg.on('click', function() {
      console.log('SVG clicked - events are working');
    });

    // Initialize force simulation
    this.simulation = d3.forceSimulation()
      .force("link", d3.forceLink().id(d => d.id).distance(60))
      .force("charge", d3.forceManyBody().strength(-200))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide().radius(25));

    console.log('Graph initialized with dimensions:', { width, height });
    this.updateGraphData();
  },

    // Method to manually refresh the graph
    refreshGraph() {
      this.$nextTick(() => {
        this.initializeGraph();
      });
    },

    updateGraphData() {
      if (!this.simulation) {
        console.warn('Simulation not initialized, attempting to initialize graph');
        this.initializeGraph();
        return;
      }

      const nodes = [];
      const links = [];

      console.log('Base configurations:', this.baseConfigurations);
      console.log('Derived configurations:', this.derivedConfigurations);

      // Add base configuration nodes
      Object.keys(this.baseConfigurations).forEach(baseName => {
        nodes.push({
          id: baseName,
          type: 'base',
          name: baseName,
          config: this.baseConfigurations[baseName],
          derivedCount: Object.keys(this.derivedConfigurations[baseName] || {}).length,
          showDerived: false
        });
      });

      // Add derived configuration nodes (if their base is expanded)
      Object.entries(this.derivedConfigurations).forEach(([baseName, derivedConfigs]) => {
        const baseNode = nodes.find(n => n.id === baseName);
        if (baseNode && baseNode.showDerived) {
          Object.entries(derivedConfigs).forEach(([derivedName, derivedConfig]) => {
            nodes.push({
              id: derivedName,
              type: 'derived',
              name: derivedName,
              config: derivedConfig,
              baseName: baseName
            });

            // Add link between base and derived
            links.push({
              source: baseName,
              target: derivedName
            });
          });
        }
      });

      console.log('Generated nodes:', nodes);
      console.log('Generated links:', links);

      this.graphData = { nodes, links };
      this.renderGraph();
    },

    renderGraph() {
      if (!this.$refs.graphSvg) {
        console.warn('SVG ref not available for rendering');
        return;
      }

      const svg = d3.select(this.$refs.graphSvg);
      const mainGroup = svg.select(".main-group");

      // Update simulation
      this.simulation.nodes(this.graphData.nodes);
      this.simulation.force("link").links(this.graphData.links);

      console.log('Rendering graph with', this.graphData.nodes.length, 'nodes and', this.graphData.links.length, 'links');

      // Render links
      const link = mainGroup.select(".links")
        .selectAll("line")
        .data(this.graphData.links)
        .join("line")
        .attr("stroke", "#999")
        .attr("stroke-opacity", 0.6)
        .attr("stroke-width", 2);

      // Render nodes
      const node = mainGroup.select(".nodes")
        .selectAll("g")
        .data(this.graphData.nodes)
        .join("g")
        .attr("class", "node")
        .call(this.createDragBehavior());

      // Clear previous content
      node.selectAll("*").remove();

      // Add circles for nodes
      node.append("circle")
        .attr("r", d => d.type === 'base' ? 18 : 13)
        .attr("fill", d => d.type === 'base' ? "#0d6efd" : "#6c757d")
        .attr("stroke", "#fff")
        .attr("stroke-width", 2);

      // Add text labels
      node.append("text")
        .attr("text-anchor", "middle")
        .attr("dy", ".35em")
        .attr("font-size", "9px")
        .attr("fill", "white")
        .text(d => d.name.length > 6 ? d.name.substring(0, 6) + "..." : d.name);

      // Add badge for derived count on base nodes
      node.filter(d => d.type === 'base' && d.derivedCount > 0)
        .append("circle")
        .attr("cx", 13)
        .attr("cy", -13)
        .attr("r", 7)
        .attr("fill", "#dc3545");

      node.filter(d => d.type === 'base' && d.derivedCount > 0)
        .append("text")
        .attr("x", 13)
        .attr("y", -13)
        .attr("text-anchor", "middle")
        .attr("dy", ".35em")
        .attr("font-size", "7px")
        .attr("fill", "white")
        .text(d => d.derivedCount);

      // Add event listeners
      node
        .on("click", this.handleNodeClick)
        .on("contextmenu", this.handleNodeContextMenu)
        .on("mouseover", this.handleNodeMouseOver)
        .on("mouseout", this.handleNodeMouseOut);

      // Update positions on tick
      this.simulation.on("tick", () => {
        link
          .attr("x1", d => d.source.x)
          .attr("y1", d => d.source.y)
          .attr("x2", d => d.target.x)
          .attr("y2", d => d.target.y);

        node
          .attr("transform", d => `translate(${d.x},${d.y})`);
      });

      this.simulation.alpha(1).restart();
    },

    createDragBehavior() {
      return d3.drag()
        .on("start", (event, d) => {
          this.isDragging = true;
          if (!event.active) this.simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
          
          // Disable zoom during drag
          if (this.zoomBehavior) {
            d3.select(this.$refs.graphSvg).on('.zoom', null);
          }
        })
        .on("drag", (event, d) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on("end", (event, d) => {
          if (!event.active) this.simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
          
          // Re-enable zoom after drag
          if (this.zoomBehavior) {
            d3.select(this.$refs.graphSvg).call(this.zoomBehavior);
          }
          
          setTimeout(() => {
            this.isDragging = false;
          }, 100);
        });
    },

    handleNodeClick(event, node) {
      if (this.isDragging) return;
      
      if (node.type === 'base') {
        // Toggle derived configurations visibility
        const graphNode = this.graphData.nodes.find(n => n.id === node.id);
        graphNode.showDerived = !graphNode.showDerived;
        this.updateGraphData();
      }
    },

    handleNodeContextMenu(event, node) {
      event.preventDefault();
      this.contextMenuTarget = node;
      
      const menu = document.getElementById('node-context-menu');
      menu.style.left = event.pageX + 'px';
      menu.style.top = event.pageY + 'px';
      menu.style.display = 'block';
    },

    handleNodeMouseOver(event, node) {
      const tooltip = d3.select("body").append("div")
        .attr("class", "graph-tooltip")
        .style("position", "absolute")
        .style("background", "rgba(0,0,0,0.8)")
        .style("color", "white")
        .style("padding", "8px")
        .style("border-radius", "4px")
        .style("font-size", "12px")
        .style("z-index", "1000")
        .style("left", (event.pageX + 10) + "px")
        .style("top", (event.pageY - 10) + "px");

      if (node.type === 'base') {
        tooltip.html(`
          <strong>${node.name}</strong><br/>
          Compressor: ${node.config.compressor_id?.toUpperCase() || 'Unknown'}<br/>
          Derived configs: ${node.derivedCount}<br/>
          <em>Click to expand/collapse</em>
        `);
      } else {
        const errorBoundKey = this.getErrorBoundKey(node.config);
        const errorBound = errorBoundKey ? node.config.compressor_config[errorBoundKey] : 'N/A';
        tooltip.html(`
          <strong>${node.name}</strong><br/>
          Base: ${node.baseName}<br/>
          Error Bound: ${errorBound}<br/>
          <em>Right-click for options</em>
        `);
      }
    },

    handleNodeMouseOut() {
      d3.selectAll(".graph-tooltip").remove();
    },

    hideContextMenu() {
      const menu = document.getElementById('node-context-menu');
      if (menu) {
        menu.style.display = 'none';
      }
    },

    // Context menu actions
    editNodeErrorBound() {
      if (this.contextMenuTarget && this.contextMenuTarget.type === 'derived') {
        const errorBoundKey = this.getErrorBoundKey(this.contextMenuTarget.config);
        if (errorBoundKey) {
          const newValue = prompt('Enter new error bound:', this.contextMenuTarget.config.compressor_config[errorBoundKey]);
          if (newValue !== null && !isNaN(parseFloat(newValue))) {
            this.contextMenuTarget.config.compressor_config[errorBoundKey] = parseFloat(newValue);
            this.updateGraphData();
          }
        }
      }
      this.hideContextMenu();
    },

    deleteNode() {
      if (this.contextMenuTarget) {
        if (this.contextMenuTarget.type === 'base') {
          this.removeConfiguration(this.contextMenuTarget.id);
        } else {
          this.removeConfiguration(this.contextMenuTarget.baseName, this.contextMenuTarget.id);
        }
      }
      this.hideContextMenu();
    },

    promoteToBase() {
      if (this.contextMenuTarget && this.contextMenuTarget.type === 'derived') {
        const derivedConfig = this.contextMenuTarget.config;
        const newBaseName = this.contextMenuTarget.id + '_base';
        
        // Create new base configuration
        this.baseConfigurations[newBaseName] = {
          ...derivedConfig,
          base_config: undefined
        };
        this.derivedConfigurations[newBaseName] = {};
        
        // Remove from derived configurations
        delete this.derivedConfigurations[this.contextMenuTarget.baseName][this.contextMenuTarget.id];
      }
      this.hideContextMenu();
    },

    bulkGenerate() {
      if (this.contextMenuTarget && this.contextMenuTarget.type === 'base') {
        this.prepareBulkGeneration(this.contextMenuTarget.id);
        const modal = new Modal(document.getElementById('bulkGenerationModal'));
        modal.show();
      }
      this.hideContextMenu();
    },

    setupResizeObserver() {
      if (!this.$refs.graphContainer) return;
      
      // Use ResizeObserver to detect when container becomes visible or changes size
      this.resizeObserver = new ResizeObserver(entries => {
        for (let entry of entries) {
          const { width, height } = entry.contentRect;
          if (width > 0 && height > 0 && this.simulation) {
            // Container is now visible and has valid dimensions
            console.log('Container resized to:', { width, height });
            this.initializeGraphWithDimensions(width, height);
          }
        }
      });
      
      this.resizeObserver.observe(this.$refs.graphContainer);
    },

    resetZoom() {
      console.log('resetZoom called');
      console.log('zoomBehavior exists:', !!this.zoomBehavior);
      console.log('graphSvg ref exists:', !!this.$refs.graphSvg);
      
      if (this.zoomBehavior && this.$refs.graphSvg) {
        const svg = d3.select(this.$refs.graphSvg);
        console.log('Resetting zoom...');
        svg.transition().duration(750).call(
          this.zoomBehavior.transform,
          d3.zoomIdentity
        );
      } else {
        console.log('Cannot reset zoom - missing zoomBehavior or SVG ref');
      }
    },

    resetLargeZoom() {
      if (this.largeZoomBehavior && this.$refs.largeGraphSvg) {
        const svg = d3.select(this.$refs.largeGraphSvg);
        svg.transition().duration(750).call(
          this.largeZoomBehavior.transform,
          d3.zoomIdentity
        );
      }
    },

    openLargeGraphModal() {
      const modal = new Modal(document.getElementById('largeGraphModal'));
      modal.show();
      
      // Initialize large graph after modal is shown
      modal._element.addEventListener('shown.bs.modal', () => {
        this.$nextTick(() => {
          this.initializeLargeGraph();
        });
      }, { once: true });
    },

    initializeLargeGraph() {
      if (!this.$refs.largeGraphContainer || !this.$refs.largeGraphSvg) {
        console.warn('Large graph container refs not available yet');
        return;
      }

      const width = this.$refs.largeGraphContainer.clientWidth;
      const height = this.$refs.largeGraphContainer.clientHeight;

      const svg = d3.select(this.$refs.largeGraphSvg)
        .attr('width', width)
        .attr('height', height);

      // Clear any existing content
      svg.selectAll("*").remove();

      // Create main group for zoom/pan
      const mainGroup = svg.append("g").attr("class", "large-main-group");

      // Create groups for different elements
      mainGroup.append("g").attr("class", "large-links");
      mainGroup.append("g").attr("class", "large-nodes");

      // Initialize zoom behavior for large graph
      this.largeZoomBehavior = d3.zoom()
        .scaleExtent([0.1, 10])
        .on("zoom", (event) => {
          mainGroup.attr("transform", event.transform);
        });

      svg.call(this.largeZoomBehavior);

      // Initialize force simulation for large graph
      this.largeSimulation = d3.forceSimulation()
        .force("link", d3.forceLink().id(d => d.id).distance(100))
        .force("charge", d3.forceManyBody().strength(-400))
        .force("center", d3.forceCenter(width / 2, height / 2))
        .force("collision", d3.forceCollide().radius(40));

      console.log('Large graph initialized with dimensions:', { width, height });
      this.renderLargeGraph();
    },

    renderLargeGraph() {
      if (!this.$refs.largeGraphSvg || !this.largeSimulation) {
        console.warn('Large SVG ref or simulation not available for rendering');
        return;
      }

      const svg = d3.select(this.$refs.largeGraphSvg);
      const mainGroup = svg.select(".large-main-group");

      // Update simulation
      this.largeSimulation.nodes(this.graphData.nodes);
      this.largeSimulation.force("link").links(this.graphData.links);

      console.log('Rendering large graph with', this.graphData.nodes.length, 'nodes and', this.graphData.links.length, 'links');

      // Render links
      const link = mainGroup.select(".large-links")
        .selectAll("line")
        .data(this.graphData.links)
        .join("line")
        .attr("stroke", "#999")
        .attr("stroke-opacity", 0.6)
        .attr("stroke-width", 3);

      // Render nodes
      const node = mainGroup.select(".large-nodes")
        .selectAll("g")
        .data(this.graphData.nodes)
        .join("g")
        .attr("class", "large-node")
        .call(this.createLargeDragBehavior());

      // Clear previous content
      node.selectAll("*").remove();

      // Add circles for nodes (larger for big view)
      node.append("circle")
        .attr("r", d => d.type === 'base' ? 25 : 18)
        .attr("fill", d => d.type === 'base' ? "#0d6efd" : "#6c757d")
        .attr("stroke", "#fff")
        .attr("stroke-width", 3);

      // Add text labels (larger font)
      node.append("text")
        .attr("text-anchor", "middle")
        .attr("dy", ".35em")
        .attr("font-size", "12px")
        .attr("fill", "white")
        .text(d => d.name.length > 10 ? d.name.substring(0, 10) + "..." : d.name);

      // Add badge for derived count on base nodes
      node.filter(d => d.type === 'base' && d.derivedCount > 0)
        .append("circle")
        .attr("cx", 18)
        .attr("cy", -18)
        .attr("r", 10)
        .attr("fill", "#dc3545");

      node.filter(d => d.type === 'base' && d.derivedCount > 0)
        .append("text")
        .attr("x", 18)
        .attr("y", -18)
        .attr("text-anchor", "middle")
        .attr("dy", ".35em")
        .attr("font-size", "10px")
        .attr("fill", "white")
        .text(d => d.derivedCount);

      // Add event listeners
      node
        .on("click", this.handleNodeClick)
        .on("contextmenu", this.handleNodeContextMenu)
        .on("mouseover", this.handleNodeMouseOver)
        .on("mouseout", this.handleNodeMouseOut);

      // Update positions on tick
      this.largeSimulation.on("tick", () => {
        link
          .attr("x1", d => d.source.x)
          .attr("y1", d => d.source.y)
          .attr("x2", d => d.target.x)
          .attr("y2", d => d.target.y);

        node
          .attr("transform", d => `translate(${d.x},${d.y})`);
      });

      this.largeSimulation.alpha(1).restart();
    },

    createLargeDragBehavior() {
      return d3.drag()
        .on("start", (event, d) => {
          this.isDragging = true;
          if (!event.active) this.largeSimulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on("drag", (event, d) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on("end", (event, d) => {
          if (!event.active) this.largeSimulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
          
          setTimeout(() => {
            this.isDragging = false;
          }, 100);
        });
    },

  },
};
</script>

<style src="vue-multiselect/dist/vue-multiselect.min.css"></style>

<style scoped>
.context-menu {
  background: white;
  border: 1px solid #ccc;
  border-radius: 4px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
  padding: 0;
  min-width: 150px;
}

.context-menu-item {
  padding: 8px 12px;
  cursor: pointer;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.context-menu-item:hover {
  background-color: #f8f9fa;
}

.context-menu-item:active {
  background-color: #e9ecef;
}

#configuration-graph {
  overflow: hidden;
  box-sizing: border-box;
}

#configuration-graph:active {
  cursor: grabbing;
}

#configuration-graph svg {
  display: block;
}

#large-configuration-graph {
  overflow: hidden;
  box-sizing: border-box;
  cursor: grab;
}

#large-configuration-graph:active {
  cursor: grabbing;
}

.node {
  cursor: pointer;
}

.large-node {
  cursor: pointer;
}

.node circle {
  transition: r 0.2s, fill 0.2s;
}

.node:hover circle {
  r: 22;
}

.graph-tooltip {
  pointer-events: none;
}
</style> 