<script>
import AppHeader from './components/AppHeader.vue'
import InputDataset from './components/InputDataset.vue'
import CustomizeCompressor from './components/CustomizeCompressor.vue'
import HelloVtk from './components/HelloVtk.vue'
import MetricVis from './components/MetricVis.vue'
import AppFooter from './components/AppFooter.vue'
import { Splitpanes, Pane } from 'splitpanes'

export default {
  name: 'App',
  components: {
    AppHeader,
    InputDataset,
    CustomizeCompressor,
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
    this.debouncedResize = this.debounce(this.onSplitResize, 200);
  },

  mounted() {
    const tabToggles = document.querySelectorAll('button[data-bs-toggle="tab"]');
    tabToggles.forEach(tab => {
      tab.addEventListener('shown.bs.tab', this.debouncedResize);
    });
  },

  methods: {
    async checkConnection() {
      this.isChecking = true;
      this.connectionError = "";
      let attempt = 1;
      const maxAttempts = 3;
      let connected = false;
      while (attempt <= maxAttempts && !connected) {
        let countdown = 4;
        // Show countdown in status bar
        const countdownInterval = setInterval(() => {
          this.$store.commit('setStatus', {
            type: 'info',
            message: `Checking server connection… (Attempt ${attempt}/${maxAttempts}, ${countdown}s left)`
          });
          countdown--;
        }, 1000);
        try {
          const controller = new AbortController();
          const timeout = setTimeout(() => controller.abort(), 5000); // 5 seconds time-out
          // Initial status
          this.$store.commit('setStatus', {
            type: 'info',
            message: `Checking server connection… (Attempt ${attempt}/${maxAttempts}, 5s left)`
          });
          const response = await fetch(`${this.serverAddress}/listDatasets`, { signal: controller.signal });
          clearTimeout(timeout);
          clearInterval(countdownInterval);
          if (!response.ok) throw new Error("Server not reachable");
          localStorage.setItem("fzvis_server_address", this.serverAddress);
          this.showServerModal = false;
          this.$store.commit('setStatus', { type: 'success', message: `Connected to ${this.serverAddress}` });
          this.$store.commit('addHistory', { kind: 'connection', text: `Connected to ${this.serverAddress}`, timestamp: Date.now() });
          connected = true;
        } catch (err) {
          clearInterval(countdownInterval);
          let msg = err.message || err.toString() || "Unknown error";
          if (err.name === 'AbortError' || msg.includes('signal is aborted')) {
            msg = "Connection timed out. Server took too long to respond";
          }
          this.connectionError = `Failed to connect: ${msg}. Please check the address and try again.`;
          this.$store.commit('setStatus', { type: 'danger', message: `Attempt ${attempt} failed: ${msg}` });
          this.$store.commit('addHistory', { kind: 'connection', text: `Connection failed: ${msg}`, timestamp: Date.now() });
          attempt++;
          // Wait a short moment before next attempt
          if (attempt <= maxAttempts) {
            await new Promise(resolve => setTimeout(resolve, 1500));
          }
        }
      }
      if (!connected) {
        this.showServerModal = true;
        this.$store.commit('setStatus', { type: 'danger', message: this.connectionError });
      }
      this.isChecking = false;
    },
    
    debounce(func, delay) {
      let timeout;
      return function(...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), delay);
      };
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

    <div v-else class="d-flex flex-column vh-100 overflow-hidden pt-2 px-3">
      <AppHeader />

      <div class="d-flex flex-grow-1 overflow-hidden mb-3">
        <Splitpanes class="default-theme w-100 h-100" :dbl-click-splitter="false" @resized="debouncedResize">
          <Pane :size="30" min-size="25" class="h-100 overflow-auto">
            <div class="p-2 d-flex flex-column">
              <ul class="nav nav-tabs mb-2" role="tablist">
                <li class="nav-item" role="presentation">
                  <button class="nav-link active" id="inputdataset-tab" data-bs-toggle="tab" data-bs-target="#inputdataset-pane" type="button" role="tab" aria-selected="true">
                    <i class="bi bi-upload me-2"></i>Input Data
                  </button>
                </li>
                <li class="nav-item" role="presentation">
                  <button class="nav-link" id="customizecompressor-tab" data-bs-toggle="tab" data-bs-target="#customizecompressor-pane" type="button" role="tab" aria-selected="false">
                    <i class="bi bi-sliders me-2"></i>Compressor
                  </button>
                </li>
              </ul>
              <div class="tab-content flex-grow-1 overflow-auto">
                <div id="inputdataset-pane" class="tab-pane fade show active h-100" role="tabpanel" aria-labelledby="inputdataset-tab">
                  <InputDataset />
                </div>
                <div id="customizecompressor-pane" class="tab-pane fade h-100" role="tabpanel" aria-labelledby="customizecompressor-tab">
                  <CustomizeCompressor />
                </div>
              </div>
            </div>
          </Pane>

          <Pane :size="70" min-size="50" class="h-100 overflow-auto">
            <div class="d-flex flex-column h-100 ms-3 main-right">
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
                  <div class="h-100 overflow-hidden">
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

      <div class="flex-shrink-0" style="height:2.5rem;"></div>
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

<style scoped>
/* Background color for panes in Splitpanes */
:deep(.splitpanes.default-theme .splitpanes__pane) {
  background-color: #f8f9fa; /* Bootstrap bg-light */
}
</style>