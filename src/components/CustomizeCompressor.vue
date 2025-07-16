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

      <!-- Base configurations panel -->
      <div class="p-2">
        <div class="card border-primary">
          <div class="card-header d-flex justify-content-between align-items-center">
            <h6 class="mb-0">Base Configurations</h6>
            <span class="badge bg-info">{{ Object.keys(baseConfigurations).length }}</span>
          </div>
          
          <div class="card-body p-2" v-if="Object.keys(baseConfigurations).length > 0">
            <div class="row">
              <div class="col-12 mb-2" v-for="(config, name) in baseConfigurations" :key="name">
                <div class="card">
                  <div class="card-body p-2">
                    <div class="d-flex justify-content-between align-items-center">
                      <div>
                        <h6 class="card-title mb-1 text-primary">{{ name }}</h6>
                        <div class="small text-muted">
                          {{ config.compressor_id ? config.compressor_id.toUpperCase() : "" }}
                          <span class="badge bg-secondary pointer me-1">
                            {{ Object.keys(derivedConfigurations[name]).length }}
                          </span>
                          <template v-if="Object.keys(derivedConfigurations[name]).length > 0">
                            <small style="cursor:pointer" v-if="expandedBaseConfigs[name]" class="link-info" @click="toggleDerivedConfigsVisibility(name)">
                              (hide)
                            </small>
                            <small style="cursor:pointer" v-else class="link-info" @click="toggleDerivedConfigsVisibility(name)">
                              (show)
                            </small>
                          </template>
                        </div>
                      </div>
                      <div class="d-flex gap-2">
                        <button class="btn btn-outline-danger" title="Delete" @click="removeConfiguration(name)">
                          <i class="bi bi-trash"></i>
                        </button>
                        <button class="btn btn-outline-secondary" title="Bulk Generate" @click="prepareBulkGeneration(name)" data-bs-toggle="modal" data-bs-target="#bulkGenerationModal">
                          <i class="bi bi-lightning-charge"></i>
                        </button>
                        <button
                          class="btn btn-outline-secondary"
                          title="Details"
                          data-bs-toggle="popover"
                          data-bs-placement="right"
                          data-bs-html="true"
                          :data-bs-content="formatBaseConfig(config)"
                        >
                          <i class="bi bi-info"></i>
                        </button>
                      </div>
                    </div>
                    
                    <!-- Derived configurations list (expandable) -->
                    <div v-if="expandedBaseConfigs[name]" class="mt-3">
                      <hr class="my-2">
                      <h6 class="text-muted mb-2">Derived Configurations</h6>
                      <div class="table-responsive">
                        <table class="table table-sm table-hover">
                          <thead>
                            <tr class="text-center">
                              <th>Suffix</th>
                              <th>Error Bound</th>
                              <th>Actions</th>
                            </tr>
                          </thead>
                          <tbody class="text-center">
                            <tr v-for="(derivedConfig, derivedName) in derivedConfigurations[name]" :key="derivedName">
                              <td class="small" style="width: 20%;">{{ derivedName.substring(name.length + 1) }}</td>
                              <td style="width: 50%;">
                                <input 
                                  type="number" 
                                  class="form-control form-control-sm" 
                                  v-model="derivedConfig.compressor_config[getErrorBoundKey(derivedConfig)]" 
                                  step="0.00001" 
                                  min="0"
                                  :disabled="!editingErrorBound[derivedName]"
                                >
                              </td>
                              <td style="width: 30%">
                                <button
                                  v-if="!editingErrorBound[derivedName]"
                                  class="btn btn-sm btn-outline-primary"
                                  title="Edit"
                                  @click="editingErrorBound = { ...editingErrorBound, [derivedName]: true }"
                                >
                                  <i class="bi bi-pencil-square"></i>
                                </button>
                                <button
                                  v-else
                                  class="btn btn-sm btn-success"
                                  title="Save"
                                  @click="editingErrorBound = { ...editingErrorBound, [derivedName]: false }"
                                >
                                  <i class="bi bi-floppy"></i>
                                </button>
                                <button class="btn btn-sm btn-outline-danger ms-2" @click="removeConfiguration(name, derivedName)">
                                  <i class="bi bi-trash"></i>
                                </button>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          <div class="card-body text-center text-muted" v-else>
            <p class="mb-0">No saved configurations yet.</p>
          </div>
          
          <div class="card-footer text-center">
            <button type="button" class="btn btn-primary w-60" @click="submitConfigurations" :disabled="Object.keys(savedConfigurations).length === 0">
              Run All {{ Object.keys(savedConfigurations).length }} Configurations
            </button>
          </div>
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

export default {
  components: {
    Multiselect,
  },
  data() {
    return {
      baseURL: process.env.VUE_APP_API_BASE,
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
      console.log("bulk settings:", this.bulkSettings);
      
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
              
              acc[formattedCategory] = values.map(value => ({
                id: value,
                label: `${formattedCategory}: ${value}`, // format label for display
                type: category,
              }));
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
        const replaceModal = Modal(document.getElementById("replaceConfigModal"));
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
          console.log("compressor config:", Object.values(this.compare_data).map(d => d["compressor_config"]));
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

  },
};
</script>

<style src="vue-multiselect/dist/vue-multiselect.min.css"></style>