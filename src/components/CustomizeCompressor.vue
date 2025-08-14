<script>
import axios from 'axios';
import { Modal } from 'bootstrap';
import Multiselect from 'vue-multiselect';
import ConfigGraph from './ConfigGraph.vue';

export default {
  components: {
    Multiselect,
    ConfigGraph,
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
      compare_data: {},
      formData: new FormData(),
      showConfigPanel: true, // Add toggle for config panel
    };
  },

  computed: {
    isConfigValid() {
      const options = this.compressorOptions[this.selectedCompressor]["Detail"];
      if (!options) return false;

      return Object.values(this.configuredValues["Detail"]).every((item) => {
        // handle error bound: must have a value
        if (item?.label?.startsWith("Error Bound")) {
          return item?.value !== undefined && item.value !== "";
        }

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

  mounted: function () {
    this.getAvailableCompressors();
    // Add event listener for modal shown to focus input
    const saveConfigModal = document.getElementById('saveConfigModal');
    if (saveConfigModal) {
      saveConfigModal.addEventListener('shown.bs.modal', () => {
        const input = document.getElementById('floatingConfigName');
        if (input) input.focus();
      });
    }
  },

  methods: {
    formatConfig(compressorConfig) {
      if (!compressorConfig) return {};

      return Object.fromEntries(
        Object.entries(compressorConfig).map(
          ([key, value]) => [this.getFormattedKey(key), value]
        )
      );
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
          
          // Manually add error bound option if missing (absolute error bound)
          const hasErrorBound = Object.keys(formattedOptions["Detail"]).some(category => category.toLowerCase().includes("error bound"));
          if (!hasErrorBound) {
            formattedOptions["Detail"]["Error Bound"] = [{
              id: "pressio:abs",
              label: "Error Bound: ABS",
              type: "error bound",
            }];
          }

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
          // console.log("formattedOptions", JSON.stringify(formattedOptions, null, 2));
          this.compressorOptions[this.selectedCompressor] = formattedOptions;
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
        // .replace(/_mode$/, "")              // remove `_mode` suffix
        .replace(/_algo$/, "")              // remove `_algo` suffix
        .replace("_error_bound", " Error Bound") // special handling
        .replace(/_/g, " ")                 // underscores to spaces
        .replace(/\b\w/g, c => c.toUpperCase()); // capitalize words
    },

    handleErrorBoundGeneration({ baseConfigName, parameter, values }) {
      if (!this.derivedConfigurations[baseConfigName]) {
        this.derivedConfigurations[baseConfigName] = {};
      }
      values.forEach((val) => {
        const baseConfig = this.baseConfigurations[baseConfigName];
        if (!baseConfig) return;
        // Deep copy base config
        const newConfig = JSON.parse(JSON.stringify(baseConfig));
        if (!newConfig.compressor_config) newConfig.compressor_config = {};
        newConfig.compressor_config[parameter] = val;
        const derivedName = `${baseConfigName}_error_bound_${val}`;
        this.derivedConfigurations[baseConfigName][derivedName] = newConfig;
        this.savedConfigurations[derivedName] = newConfig;
      });
    },

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
      const config = { "compressor_config":{} };
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
        else if (item.label.startsWith("Error Bound")) {
          if (item.type.split(":")[0] != this.selectedCompressor) {
            config["compressor_config"][item.id] = item.value
          }
          else {
            if (item.type.includes("mode")) {
              config["compressor_config"][item.type] = item.id;
            }
            const errorBoundEntries = this.handleErrorBoundMode(item);
            Object.entries(errorBoundEntries).forEach(([key, value]) => {
              config["compressor_config"][key] = value;
            });
          }
        }
        else if (!item.label.startsWith("Compressor:")) {
          config["compressor_config"][item.type] = item.id;
        }
      });

      // Save current configuration
      // corrected config format:
      // savedConfig {"compressor_config":{"sz3:algorithm_str":"ALGO_INTERP","sz3:abs_error_bound":0.001,"sz3:intrep_algo_str":"INTERP_ALGO_CUBIC","sz3:metric":"composite"},"compressor_id":"sz3"}
      this.baseConfigurations[this.currentConfigName] = config;
      this.derivedConfigurations[this.currentConfigName] = {};
      this.savedConfigurations[this.currentConfigName] = config;
      // console.log("baseConfigurations", JSON.stringify(this.baseConfigurations));
      // console.log("savedConfigurations", JSON.stringify(this.savedConfigurations));
      this.currentConfigName = "";
    },

    // errorBoundItem should contain id, label, type, and value
    handleErrorBoundMode(errorBoundItem) {
      if (!errorBoundItem.type.includes("mode")) return;
      const prefix = errorBoundItem.type.split(":")[0];
      const errorMode = errorBoundItem.label.split(": ")[1].toLowerCase();
      let res = [];
      if (errorMode.includes("abs")) {
        res[`${prefix}:abs_error_bound`] = errorBoundItem.value;
      }
      if (errorMode.includes("rel")) {
        res[`${prefix}:rel_error_bound`] = errorBoundItem.value;
      } else if (errorMode.includes("psnr")) {
        res[`${prefix}:psnr_error_bound`] = errorBoundItem.value;
      } else if (errorMode.includes("norm")) {
        res[`${prefix}:l2_norm_error_bound`] = errorBoundItem.value;
      } else {
        res[`${prefix}:${errorMode.toLowerCase()}_error_bound`] = errorBoundItem.value;
      }
      return res;
    },

    // Handle Enter key in configuration name input field
    onEnterConfigName() {
      this.handleConfigurationCheck();
      setTimeout(() => {
        const modal = document.getElementById('saveConfigModal');
        if (modal) {
          Modal.getOrCreateInstance(modal).hide();
          document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
        }
      }, 100);
    },

    handleParameterGeneration({ baseNodeId, parameter, values }) {
      if (!this.derivedConfigurations[baseNodeId]) {
        this.derivedConfigurations[baseNodeId] = {};
      }
      const baseConfig = this.baseConfigurations[baseNodeId];
      if (!baseConfig) return;

      values.forEach(valObj => {
        let newConfig = JSON.parse(JSON.stringify(baseConfig));
        if (!newConfig.compressor_config) newConfig.compressor_config = {};

        // Handle error bound mode propagation
        if (parameter.toLowerCase().includes('error bound mode')) {
          const compressorId = newConfig.compressor_id || baseConfig.compressor_id || '';
          newConfig.compressor_config[`${compressorId}:error_bound_mode`] = valObj.id;
          const boundObj = this.handleErrorBoundMode(valObj);
          Object.entries(boundObj).forEach(([key, value]) => {
            newConfig.compressor_config[key] = value;
          });
        } else {
          newConfig.compressor_config[valObj.type] = valObj?.id;
        }

        const derivedName = `${baseNodeId}_${valObj?.id}`;
        this.derivedConfigurations[baseNodeId][derivedName] = newConfig;
        this.savedConfigurations[derivedName] = newConfig;
      });
    },

    // Randomly pick option values for the selected compressor
    randomlyPickOptions() {
      const detailOptions = this.compressorOptions[this.selectedCompressor]['Detail'];
      Object.keys(detailOptions).forEach(optionName => {
        const optionList = detailOptions[optionName];
        if (optionName === 'Metric') {
          // For Metrics, use ["time", "size", "error_stat"] as default
          this.configuredValues['Detail'][optionName] = detailOptions['Metric'].filter(item => 
            ['time', 'size', 'error_stat'].includes(item.id)
          );
        }
        else {
          // For single selection options, pick one random option
          const randomIndex = Math.floor(Math.random() * optionList.length);
          this.configuredValues['Detail'][optionName] = optionList[randomIndex];
          // check if the option is an error bound
          if (optionName.toLowerCase().includes("error bound")) {
            // Only generate random exponent between 1e-7 and 1e-2
            const randomExponent = Math.floor(Math.random() * 6) + 2; 
            this.configuredValues['Detail'][optionName].value = Math.pow(10, -randomExponent);
          }
        }
      });
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


  }
};
</script>

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
          <!-- <span class="text-warning text-align-center">
            <i class="bi bi-exclamation-triangle-fill me-1"></i>
            Not all compressors are fully supported or tested.
          </span> -->
        </div>
        
        <div v-if="selectedCompressor" class="p-2">
          <div class="card">
            <div class="card-body" v-if="selectedCompressor in this.compressorOptions">
              <h5 class="card-title d-flex align-items-center" style="gap: 0.5rem;">
                {{ selectedCompressor }}
                <button
                  class="btn btn-sm btn-outline-secondary"
                  type="button"
                  :aria-label="showConfigPanel ? 'Hide configuration panel' : 'Show configuration panel'"
                  :title="showConfigPanel ? 'Hide configuration panel' : 'Show configuration panel'"
                  @click="showConfigPanel = !showConfigPanel"
                >
                  <span v-if="showConfigPanel" class="bi bi-chevron-up"></span>
                  <span v-else class="bi bi-chevron-down"></span>
                </button>
              </h5>
              <div v-show="showConfigPanel">
                <p class="card-text" v-show="compressorOptions[selectedCompressor]['Highlevel'].length > 0">High-level options are listed here.</p>
                <div class="d-flex flex-wrap mb-2" v-show="compressorOptions[selectedCompressor]['Highlevel'].length > 0">
                  <div
                    class="me-2 mb-2"
                    v-for="option in compressorOptions[selectedCompressor]['Highlevel'].filter(opt => opt.label === 'Nthreads')"
                    :key="option.id"
                  >
                    <div class="form-floating">
                      <input
                        type="number"
                        class="form-control"
                        style="width:120px;"
                        title="Number of threads to use"
                        :id="option.id"
                        :placeholder="option.label"
                        min="1"
                        step="1"
                        v-model="configuredValues['Highlevel'][option.id]"
                      >
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
                  <div class="mb-2 me-2" v-for="(optionList, optionName) in compressorOptions[selectedCompressor]['Detail']" :key="optionName">
                    <div v-if="optionName.toLowerCase().includes('error bound') && configuredValues['Detail'][optionName]" class="row g-2">
                      <div class="col-8">
                        <multiselect v-model="configuredValues['Detail'][optionName]" :options="optionList" :searchable="true" :multiple="optionName === 'Metric'" :close-on-select="optionName !== 'Metric'" :clear-on-select="false" :placeholder="`Select ${optionName}`" label="label" show-label="false" track-by="id" :title="optionDocs[optionList[0].type] || 'No documentation available'" aria-label="optionName">
                        </multiselect>
                      </div>
                      <div class="col-4" style="min-width: 100px;">
                        <input
                          type="number"
                          class="form-control"
                          placeholder="Enter bound value"
                          min="0"
                          step="0.001"
                          v-model="configuredValues['Detail'][optionName].value"
                        />
                      </div>
                    </div>
                    <div v-else class="d-flex align-items-center" style="gap: 0.25rem;">
                      <multiselect v-model="configuredValues['Detail'][optionName]" :options="optionList" :searchable="true" :multiple="optionName === 'Metric'" :close-on-select="optionName !== 'Metric'" :clear-on-select="false" :placeholder="`Select ${optionName}`" label="label" show-label="false" track-by="id" :title="optionDocs[optionList[0].type] || 'No documentation available'" aria-label="optionName">
                      </multiselect>
                    </div>
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
      </div>

      <!-- Save configuration modal -->
      <div id="saveConfigModal" class="modal fade" tabindex="-1" aria-labelledby="saveConfigModalLabel" data-bs-keyboard="false" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h1 class="modal-title fs-5" id="saveConfigModalLabel">Save current configuration</h1>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
              <div class="form-floating">
                <input type="text" class="form-control" id="floatingConfigName" placeholder="Configuration name" v-model="currentConfigName" @keyup.enter="onEnterConfigName">
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

      <!-- Configuration Graph Card Panel -->
      <ConfigGraph
        :baseConfigurations="baseConfigurations"
        :derivedConfigurations="derivedConfigurations"
        :savedConfigurations="savedConfigurations"
        :compressorOptions="compressorOptions"
        @error-bound-bulk-generation="handleErrorBoundGeneration"
        @propagate-parameter="handleParameterGeneration"
      />
    </div>
</template>

<style src="vue-multiselect/dist/vue-multiselect.min.css"></style>
