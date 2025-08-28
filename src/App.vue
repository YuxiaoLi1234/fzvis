<script>
import AppHeader from './components/AppHeader.vue'
// import CustomizeCompressor from './components/CustomizeCompressor.vue'
import HelloVtk from './components/HelloVtk.vue'
import MetricVis from './components/MetricVis.vue'
import AppFooter from './components/AppFooter.vue'
import PipelineView from './components/PipelineView.vue'
import { Splitpanes, Pane } from 'splitpanes'

export default {
  name: 'App',
  components: {
    AppHeader,
    PipelineView,
    // CustomizeCompressor,
    HelloVtk,
    MetricVis,
    AppFooter,
    Splitpanes,
    Pane,
  },

  data() {
    return {
      showServerModal: false,
      serverAddress: "http://localhost:5003",
      isChecking: false,
      connectionError: "",
      // For Properties pane
      selectedModule: null,
      selectedModuleOptions: [],
    };
  },

  created() {
    // Try to load from localStorage or config file
    const savedAddress = localStorage.getItem("fzvis_server_address");
    if (savedAddress) {
      this.serverAddress = savedAddress;
      this.checkConnection(true);
    } else {
      this.showServerModal = true;
    }
  },

  methods: {
    async checkConnection() {
      this.isChecking = true;
      this.connectionError = "";
      this.$store.commit('setStatus', { type: 'info', message: 'Checking server connection…' });
      try {
        const response = await fetch(`${this.serverAddress}/listDatasets`);
        if (!response.ok) throw new Error("Server not reachable");
        localStorage.setItem("fzvis_server_address", this.serverAddress);
        this.showServerModal = false;
        this.$store.commit('setStatus', { type: 'success', message: `Connected to ${this.serverAddress}` });
        this.$store.commit('addHistory', { kind: 'connection', text: `Connected to ${this.serverAddress}`, timestamp: Date.now() });
      } catch (err) {
        const msg = err.message || err.toString() || "Unknown error";
        this.connectionError = `Failed to connect: ${msg}. Please check the address and try again.`;
        this.showServerModal = true;
        console.log("Connection error:", this.connectionError);
        this.$store.commit('setStatus', { type: 'danger', message: this.connectionError });
        this.$store.commit('addHistory', { kind: 'connection', text: `Connection failed: ${msg}`, timestamp: Date.now() });
      } finally {
        this.isChecking = false;
      }
    },
    
    // Handle PipelineView selection to populate Properties pane
    onModuleSelected(payload) {
      // Deselect if payload is null
      if (!payload) {
        this.selectedModule = null;
        this.selectedModuleOptions = [];
        return;
      }
      this.selectedModule = { id: payload.id, label: payload.label };
      this.selectedModuleOptions = payload.options || [];
    },
    // Make option draggable for dropping onto modules in PipelineView
    onOptionDragStart(option, e) {
      if (!this.selectedModule) return;
      e.dataTransfer.setData('text/plain', option);
      e.dataTransfer.setData('module-id', this.selectedModule.id);
    },
    
    resetServerAddress() {
      localStorage.removeItem("fzvis_server_address");
      this.serverAddress = "";
      this.showServerModal = true;
      this.$store.commit('setStatus', { type: 'warning', message: 'Server address cleared.' });
      this.$store.commit('addHistory', { kind: 'connection', text: 'Server address cleared', timestamp: Date.now() });
    },

    onSplitResize() {
      window.dispatchEvent(new Event('resize'));
    },
  }
}
</script>

<template>
  <div class="d-flex flex-column vh-100 overflow-hidden">
    <!-- Bootstrap Modal for Server Address -->
    <div v-if="showServerModal" class="modal show d-block" tabindex="-1" role="dialog">
      <div class="modal-dialog modal-dialog-centered" role="document">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">Enter Remote Server Address</h5>
          </div>
          <div class="modal-body">
            <input
              v-model="serverAddress"
              type="text"
              class="form-control"
            />
            <div v-if="connectionError" class="alert alert-danger mt-2">{{ connectionError }}</div>
          </div>
          <div class="modal-footer">
            <button
              type="button"
              class="btn btn-primary"
              @click="checkConnection"
              :disabled="isChecking"
            >
              Check Connection
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="d-flex flex-column vh-100 overflow-hidden pt-2 px-3 pb-5">
      <AppHeader />

      <div class="d-flex flex-grow-1 overflow-hidden mb-3">
        <Splitpanes class="default-theme w-100 h-100" :dbl-click-splitter="false" @resize="onSplitResize" @resized="onSplitResize">
          <!-- Left: split horizontally (top/bottom) for Pipeline and Properties -->
          <Pane :size="35" min-size="20" class="h-100 overflow-hidden">
            <div class="h-100 p-2 d-flex flex-column overflow-hidden">
              <Splitpanes class="default-theme" horizontal>
                <Pane min-size="20">
                  <div class="h-100 p-2 d-flex flex-column overflow-hidden">
                    <h6 class="text-muted fw-semibold mb-2"><i class="bi bi-diagram-3 me-2"></i>Pipeline</h6>
                    <div class="flex-grow-1 overflow-auto">
                      <PipelineView @moduleSelected="onModuleSelected" />
                    </div>
                  </div>
                </Pane>
                <Pane :size="45" min-size="20">
                  <div class="h-100 p-2 d-flex flex-column overflow-hidden">
                    <h6 class="text-muted fw-semibold mb-2"><i class="bi bi-sliders me-2"></i>Properties</h6>
                    <div class="flex-grow-1 overflow-auto">
                      <div v-if="selectedModule">
                        <div class="d-flex align-items-center mb-2">
                          <span class="me-2 text-muted small">Options for</span>
                          <span class="badge bg-primary">{{ selectedModule.label }}</span>
                        </div>
                        <div class="d-flex flex-row flex-wrap gap-2">
                          <div
                            v-for="option in selectedModuleOptions"
                            :key="option"
                            class="card p-2 px-3 text-center border border-2 border-primary bg-white flex-shrink-0 shadow-sm user-select-none cursor-pointer"
                            draggable="true"
                            @dragstart="onOptionDragStart(option, $event)"
                          >
                            <span class="fw-semibold text-primary">{{ option }}</span>
                          </div>
                        </div>
                      </div>
                      <div v-else class="text-muted small">Select a module in the pipeline to view options here.</div>
                      <!-- <CustomizeCompressor /> -->
                    </div>
                  </div>
                </Pane>
              </Splitpanes>
            </div>
          </Pane>

          <Pane :size="65" min-size="30" class="h-100 overflow-hidden">
            <div class="d-flex flex-column h-100 ms-3">
              <ul class="nav nav-tabs" role="tablist">
                <li class="nav-item" role="presentation">
                  <button class="nav-link active" id="datavis-tab" data-bs-toggle="tab" data-bs-target="#datavis" type="button" role="tab" aria-selected="true"><i class="bi bi-eye me-1"></i>Data Visualization</button>
                </li>
                <li class="nav-item" role="presentation">
                  <button class="nav-link" id="metrics-tab" data-bs-toggle="tab" data-bs-target="#metrics" type="button" role="tab" aria-selected="true">
                    <i class="bi bi-bar-chart-line me-1"></i>Metrics
                  </button>
                </li>
              </ul>
              <div class="tab-content flex-grow-1">
                <div id="datavis" class="tab-pane fade show active h-100" role="tabpanel" aria-labelledby="datavis-tab">
                  <div class="h-100 overflow-auto">
                    <HelloVtk />
                  </div>
                </div>
                <div id="metrics" class="tab-pane fade h-100" role="tabpanel" aria-labelledby="metrics-tab">
                  <div class="h-100 overflow-auto">
                    <MetricVis />
                  </div>
                </div>
              </div>
            </div>
          </Pane>
        </Splitpanes>
      </div>

      <AppFooter />

      <!-- Offcanvas HTML -->
      <div class="offcanvas offcanvas-end m-2 py-0" tabindex="-1" id="showMore" aria-labelledby="showMoreLabel">
        <div class="offcanvas-header">
          <h4 class="offcanvas-title" id="showMoreLabel">About FZ-VIS</h4>
          <button type="button" class="btn-close text-reset" data-bs-dismiss="offcanvas" aria-label="Close"></button>
        </div>
        <div class="offcanvas-body">
          <div>
            FZ-VIS is a web-based visualization tool for the FZ project. The tool allows users to configure, apply, and compare the performance of multiple compression algorithms on the dataset.
          </div>
          <div class="mt-2">
            <h5>Tutorial</h5>
            <div class="mx-2">
              Please check out <a class="text-info" data-bs-toggle="tooltip" data-bs-placement="top" title="To be updated">this page</a> for text tutorial and <a class="text-info" data-bs-toggle="tooltip" data-bs-placement="right" title="To be updated">this video</a> for video tutorial.
            </div>
          </div>
          <div class="mt-2">
            <h5>Contributors</h5>
            <div class="mx-2">
              <p class="fw-bold my-1">The Ohio State University</p>
              <ul class="my-0">
                <li class="fw-bold fst-italic"><a href="https://cse.osu.edu/people/guo.2154" target="_blank">PI: Hanqi Guo</a></li>
                <li><a href="https://github.com/YuxiaoLi1234" target="_blank">Yuxiao Li</a></li>
                <li><a href="https://cse.osu.edu/people/liu.12722" target="_blank">Guoxi Liu</a></li>
                <li><a href="https://github.com/hrithikdevaiah-999" target="_blank">Hrithik Devaiah Bollachettira Ajithkumar</a></li>
              </ul>
              <p class="fw-bold my-1">Argonne National Laboratory</p>
              <ul class="my-0">
                <li><a href="https://www.anl.gov/profile/robert-underwood" target="_blank">Robert Underwood</a></li>
              </ul>
            </div>
          </div>
        </div>
        <div class="offcanvas-footer px-2 pb-5">
          <p class="text-muted">Powered by <a href="https://getbootstrap.com/" target="_blank"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-bootstrap me-1 mb-1" viewBox="0 0 16 16">
            <path d="M5.062 12h3.475c1.804 0 2.888-.908 2.888-2.396 0-1.102-.761-1.916-1.904-2.034v-.1c.832-.14 1.482-.93 1.482-1.816 0-1.3-.955-2.11-2.542-2.11H5.062zm1.313-4.875V4.658h1.78c.973 0 1.542.457 1.542 1.237 0 .802-.604 1.23-1.764 1.23zm0 3.762V8.162h1.822c1.236 0 1.887.463 1.887 1.348 0 .896-.627 1.377-1.811 1.377z"/>
            <path d="M0 4a4 4 0 0 1 4-4h8a4 4 0 0 1 4 4v8a4 4 0 0 1-4 4H4a4 4 0 0 1-4-4zm4-3a3 3 0 0 0-3 3v8a3 3 0 0 0 3 3h8a3 3 0 0 0 3-3V4a3 3 0 0 0-3-3z"/>
          </svg>BootStrap</a> and <a href="https://vuejs.org/" target="_blank"><svg width="16" height="16" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" class="bi me-1 mb-1">
            <path d="M2 4L16 28L30 4H24.5L16 18.5L7.5 4H2Z" fill="#41B883"/>
            <path d="M7.5 4L16 18.5L24.5 4H19.5L16.0653 10.0126L12.5 4H7.5Z" fill="#35495E"/>
          </svg>Vue.js</a>. <br>Licensed MIT.</p>
        </div>
      </div>

    </div>
  </div>
</template>

<style>
.splitpanes.default-theme,
.splitpanes.default-theme .splitpanes__pane {
  background-color: transparent !important;
}
</style>