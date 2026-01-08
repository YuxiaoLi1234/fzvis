<template>
  <div class="pipeline-browser-page container-fluid py-3">
    <div class="row g-3">
        <!-- Pipeline Node List -->
      <div class="col-12">
        <div class="card shadow-sm">
          <div class="card-header d-flex align-items-center justify-content-between">
            <span class="fw-semibold">Pipeline Browser</span>
            <button
              type="button"
              class="btn btn-sm btn-outline-danger"
              @click="clearFilters"
              :disabled="!filterNodes.length"
            >
              <i class="bi bi-trash me-1"></i>
              Clear composition
            </button>
          </div>
          <div class="list-group list-group-flush pipeline-node-list">
            <button
              v-for="node in pipelineList"
              :key="node.id"
              type="button"
              class="list-group-item list-group-item-action"
              :class="{ active: node.id === selectedNodeId }"
              @click="selectNode(node.id)"
              @dblclick.prevent.stop="openNodeDetails(node.id)"
            >
              <div class="d-flex align-items-start justify-content-between">
                <div class="d-flex align-items-center gap-2">
                  <i
                    class="bi bi-circle-fill fs-6"
                    :class="getStatusIconClass(node.status)"
                    aria-hidden="true"
                  ></i>
                  <div>
                    <div class="d-flex align-items-center gap-2">
                      <i v-if="node.icon" :class="['bi', node.icon]"></i>
                      <span class="fw-semibold">{{ node.label }}</span>
                    </div>
                    <div class="text-muted small">{{ node.statusMessage || getStatusLabel(node.status) }}</div>
                  </div>
                </div>
                <button
                  v-if="node.type !== 'source'"
                  type="button"
                  class="btn btn-sm btn-outline-danger"
                  title="Delete item"
                  @click.stop="removeNode(node.id)"
                >
                  <i class="bi bi-trash"></i>
                </button>
              </div>
            </button>
          </div>
        </div>
      </div>
      <!-- Global operation toolbar -->
      <div class="col-12">
        <div class="d-flex justify-content-between align-items-center">
          <div class="btn-group">
            <button
              type="button"
              class="btn btn-primary btn rounded-pill shadow-sm d-flex align-items-center gap-2"
              :disabled="!datasetLoaded"
              @click="openOperationModal"
              title="Add a new operation"
            >
              <i class="bi bi-plus-lg"></i>
              <span class="text-truncate">Add Operation</span>
            </button>
            <button
              type="button"
              class="btn btn-outline-danger btn rounded-pill shadow-sm d-flex align-items-center gap-2 ms-2"
              :disabled="!canDeleteSelected"
              @click="deleteSelectedNode"
              title="Delete selected item"
            >
              <i class="bi bi-trash"></i>
              <span class="text-truncate">Delete</span>
            </button>
          </div>
        </div>
        <p v-if="!datasetLoaded" class="text-muted small mt-2 mb-0">
          Load a dataset to enable further operations.
        </p>
      </div>

      <!-- Add Operation Modal -->
      <div v-if="showOperationModal" style="display: contents;">
        <div class="modal fade show operation-modal" tabindex="-1" role="dialog" style="display: block;">
          <div class="modal-dialog modal-lg modal-dialog-centered" role="document">
            <div class="modal-content">
              <div class="modal-header align-items-center justify-content-between">
                <div class="d-flex align-items-center gap-2">
                  <h5 class="modal-title mb-0">Select Operation</h5>
                  <div class="input-group input-group-sm" style="max-width: 250px;">
                    <span class="input-group-text"><i class="bi bi-search"></i></span>
                    <input
                      type="text"
                      class="form-control"
                      v-model.trim="operationSearch"
                      placeholder="Search operation"
                      aria-label="Search operation"
                    />
                    <button class="btn btn-outline-secondary" type="button" @click="operationSearch = ''" :disabled="!operationSearch">Clear</button>
                  </div>
                </div>
                <button type="button" class="btn-close" @click="closeOperationModal" aria-label="Close"></button>
              </div>
              <div class="modal-body">
                <div class="row g-4">
                  <!-- Left vertical category nav -->
                  <div class="col-4">
                    <!-- Category navigation with match counts -->
                    <div class="list-group">
                      <button
                        type="button"
                        class="list-group-item list-group-item-action d-flex justify-content-between align-items-center"
                        :class="{ active: modalActiveCategory === 'filters' }"
                        @click="modalActiveCategory = 'filters'"
                      >
                        <span>Data filters</span>
                        <span class="badge bg-secondary">{{ filteredFilters.length }}</span>
                      </button>
                      <button
                        type="button"
                        class="list-group-item list-group-item-action d-flex justify-content-between align-items-center"
                        :class="{ active: modalActiveCategory === 'modules' }"
                        @click="modalActiveCategory = 'modules'"
                      >
                        <span>Compression modules</span>
                        <span class="badge bg-secondary">{{ filteredModules.length }}</span>
                      </button>
                      <button
                        type="button"
                        class="list-group-item list-group-item-action d-flex justify-content-between align-items-center"
                        :class="{ active: modalActiveCategory === 'configs' }"
                        @click="modalActiveCategory = 'configs'"
                      >
                        <span>Compressor configs</span>
                        <span class="badge bg-secondary">{{ filteredCompressors.length }}</span>
                      </button>
                    </div>
                  </div>

                  <!-- Right content panel -->
                  <div class="col-8">
                    <!-- Filters content -->
                    <div v-if="modalActiveCategory === 'filters'">
                      <h6 class="fw-bold mb-1">Data filters</h6>
                      <p class="text-muted small mb-2">Filters are used to select a subset of the data.</p>
                      <div v-if="filteredFilters.length" class="list-group">
                        <div v-for="filter in filteredFilters" :key="`mf-${filter.id}`" class="list-group-item d-flex justify-content-between align-items-center">
                          <div>
                            <div class="fw-semibold">{{ filter.label }}</div>
                            <div class="text-muted small">{{ filter.description }}</div>
                          </div>
                          <button type="button" class="btn btn-sm btn-outline-primary" @click="addFilter(filter.id); closeOperationModal();">Add</button>
                        </div>
                      </div>
                      <p v-else-if="availableFilters.length" class="text-muted small mb-0">No matching filters.</p>
                      <p v-else class="text-muted small mb-0">No filters available.</p>
                    </div>

                    <!-- Modules content -->
                    <div v-else-if="modalActiveCategory === 'modules'">
                      <h6 class="fw-bold mb-1">Compression modules</h6>
                      <p class="text-muted small mb-2">Modules are individual components to compose a compressor.</p>
                      <div v-if="filteredModules.length" class="list-group">
                        <div v-for="mod in filteredModules" :key="`mm-${mod.id}`" class="list-group-item d-flex justify-content-between align-items-center">
                          <div>
                            <div class="fw-semibold">{{ mod.label }}</div>
                            <div class="text-muted small">{{ mod.description }}</div>
                          </div>
                          <button type="button" class="btn btn-sm btn-outline-primary" @click="addModule(mod.id); closeOperationModal();">Add</button>
                        </div>
                      </div>
                      <p v-else-if="moduleDefinitions.length" class="text-muted small mb-0">No matching modules.</p>
                      <p v-else class="text-muted small mb-0">No modules available.</p>
                    </div>

                    <!-- Configs content -->
                    <div v-else>
                      <h6 class="fw-bold mb-1">Compressor configs</h6>
                      <p class="text-muted small mb-2">Existing compressor pipelines can be imported.</p>
                      <div v-if="filteredCompressors.length" class="list-group">
                        <div v-for="comp in filteredCompressors" :key="`mc-${comp.id}`" class="list-group-item d-flex justify-content-between align-items-center">
                          <div>
                            <div class="fw-semibold">{{ comp.label }}</div>
                            <div class="text-muted small">{{ comp.description }}</div>
                          </div>
                          <button type="button" class="btn btn-sm btn-outline-primary" @click="addCompressor(comp.id); closeOperationModal();">Add</button>
                        </div>
                      </div>
                      <p v-else-if="availableCompressors.length" class="text-muted small mb-0">No matching compressors.</p>
                      <p v-else class="text-muted small mb-0">No compressors available.</p>
                    </div>
                  </div>
                </div>
              </div>
              <div class="modal-footer">
                <button type="button" class="btn btn-secondary" @click="closeOperationModal">Close</button>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-backdrop fade show"></div>
      </div>
      <!-- Node Details Panel -->
      <div class="col-12" v-if="selectedNode">
        <div class="card shadow-sm">
          <div class="card-header d-flex align-items-center justify-content-between">
            <div class="d-flex align-items-center gap-2">
              <i v-if="selectedNode.icon" :class="['bi', selectedNode.icon]"></i>
              <span class="fw-semibold">{{ selectedNode.label }}</span>
              <span class="badge rounded-pill" :class="getStatusBadgeClass(selectedNode.status)">
                {{ getStatusLabel(selectedNode.status) }}
              </span>
            </div>
            <ul class="nav nav-tabs card-header-tabs">
              <li class="nav-item">
                <button class="nav-link" :class="{ active: activeTab === 'info' }" @click="activeTab = 'info'">
                  Info
                </button>
              </li>
              <li class="nav-item">
                <button class="nav-link" :class="{ active: activeTab === 'config' }" @click="activeTab = 'config'">
                  Config
                </button>
              </li>
            </ul>
          </div>
          <div class="card-body">
            <template v-if="activeTab === 'info'">
              <template v-if="selectedNode.type === 'source'">
                <div class="fw-semibold mb-2">Dataset Information</div>
                <div v-if="datasetInfo" class="small">
                  <div v-if="datasetInfo.name">Name: <b>{{ datasetInfo.name }}</b></div>
                  <div>Type: <b>{{ datasetInfo.type || 'Unknown' }}</b></div>
                  <div v-if="datasetInfo.size">Size: <b>{{ datasetInfo.size }}</b></div>
                  <div v-if="datasetInfo.width != null && datasetInfo.height != null && datasetInfo.depth != null">
                    Dimensions: <b>{{ formatDimensions(datasetInfo) }}</b>
                  </div>
                  <div>Precision: <b>{{ formatPrecision(datasetInfo.precision) }}</b></div>
                  <div v-if="datasetInfo.type === 'netcdf' && datasetInfo.vars && datasetInfo.vars.length">
                    Variables:
                    <span v-for="(v, idx) in datasetInfo.vars" :key="v">
                      <span v-if="idx">, </span>{{ v }}
                    </span>
                  </div>
                </div>
                <div v-else class="text-muted small">
                  No dataset loaded. Upload or select data to get started.
                </div>
              </template>

              <template v-else-if="selectedNode.type === 'filter'">
                <div class="fw-semibold mb-2">Filter status</div>
                <div class="small">
                  <div>Status: {{ getStatusLabel(selectedNode.status) }}</div>
                  <div v-if="selectedNode.lastRunAt">Last run: {{ formatTimestamp(selectedNode.lastRunAt) }}</div>
                  <div v-if="selectedNode.lastResult?.dimensions">
                    Output dimensions: {{ selectedNode.lastResult.dimensions.join('×') }}
                  </div>
                  <div v-else>No output yet.</div>
                </div>
                <div v-if="selectedNode.description" class="text-muted small mt-2">{{ selectedNode.description }}</div>
              </template>

              <template v-else-if="selectedNode.type === 'module'">
                <div class="fw-semibold mb-2">Module status</div>
                <div class="small">
                  <div>Status: {{ getStatusLabel(selectedNode.status) }}</div>
                  <div v-if="selectedNode.lastUpdatedAt" class="text-muted mt-2">Last updated: {{ formatTimestamp(selectedNode.lastUpdatedAt) }}</div>
                </div>
                <div v-if="selectedNode.description" class="text-muted small mt-2">{{ selectedNode.description }}</div>
              </template>

              <template v-else-if="selectedNode.type === 'compressor'">
                <div class="fw-semibold mb-2">Compressor status</div>
                <div class="small">
                  <div>Status: {{ getStatusLabel(selectedNode.status) }}</div>
                  <div v-if="Array.isArray(selectedNode.modules) && selectedNode.modules.length">
                    <div class="fw-semibold mt-2">Modules</div>
                    <ul class="list-unstyled mb-0">
                      <li v-for="m in selectedNode.modules" :key="m.id" class="d-flex justify-content-between align-items-center">
                        <span>{{ m.label }}</span>
                        <span class="text-muted">{{ describeModuleSelection(m) }}</span>
                      </li>
                    </ul>
                  </div>
                  <div v-else>No module selections yet.</div>
                  <div v-if="selectedNode.lastUpdatedAt" class="text-muted mt-2">Last updated: {{ formatTimestamp(selectedNode.lastUpdatedAt) }}</div>
                </div>
              </template>

              <template v-else>
                <div class="text-muted small">No summary available.</div>
              </template>
            </template>

            <template v-else>
              <template v-if="selectedNode.type === 'source'">
                <keep-alive>
                  <InputDataset />
                </keep-alive>
              </template>

              <template v-else-if="selectedNode.type === 'filter'">
                <p v-if="selectedNode.description" class="text-muted small mb-3">
                  {{ selectedNode.description }}
                </p>
                <keep-alive>
                  <component
                    :is="selectedNode.component"
                    :key="selectedNode.id"
                    v-bind="selectedNode.props"
                    @filter-start="($event) => handleFilterStart(selectedNode.id, $event)"
                    @filter-success="($event) => handleFilterSuccess(selectedNode.id, $event)"
                    @filter-error="($event) => handleFilterError(selectedNode.id, $event)"
                    @filter-invalid="($event) => handleFilterInvalid(selectedNode.id, $event)"
                    @filter-finish="($event) => handleFilterFinish(selectedNode.id, $event)"
                    @dataset-change="($event) => handleFilterDatasetChange(selectedNode.id, $event)"
                  />
                </keep-alive>
              </template>

              <template v-else-if="selectedNode.type === 'module'">
                <p v-if="selectedNode.description" class="text-muted small mb-3">
                  {{ selectedNode.description }}
                </p>
                <template v-if="selectedNode.component">
                  <keep-alive>
                    <component
                      :is="selectedNode.component"
                      :key="selectedNode.id"
                      v-bind="selectedNode.props"
                      @module-start="() => handleModuleStart(selectedNode.id)"
                      @module-success="($event) => handleModuleSuccess(selectedNode.id, $event)"
                      @module-error="($event) => handleModuleError(selectedNode.id, $event)"
                      @module-invalid="($event) => handleModuleInvalid(selectedNode.id, $event)"
                      @module-finish="() => handleModuleFinish(selectedNode.id)"
                    />
                  </keep-alive>
                </template>
                <p v-else class="text-muted small mb-0">No module UI available.</p>
              </template>

              <template v-else-if="selectedNode.type === 'compressor'">
                <div class="mb-3">
                  <label for="compressorSelection" class="form-label fw-semibold">Compressor</label>
                  <select
                    id="compressorSelection"
                    class="form-select"
                    :value="selectedNode.definitionId"
                    :disabled="availableCompressors.length <= 1"
                    @change="(e) => addCompressor(e.target.value)"
                  >
                    <option v-for="compressor in availableCompressors" :key="compressor.id" :value="compressor.id">
                      {{ compressor.label }}
                    </option>
                  </select>
                  <p class="text-muted small mt-2 mb-0">
                    {{ availableCompressors.find(c => c.id === selectedNode.definitionId)?.description || '' }}
                  </p>
                </div>
                <keep-alive>
                  <component
                    :is="selectedNode.component"
                    :key="`compressor-${selectedNode.renderKey}`"
                    @pipeline-modules-updated="(mods) => { selectedNode.modules = mods; selectedNode.lastUpdatedAt = Date.now(); selectedNode.status = (mods && mods.every(m => m?.value && Object.keys(m.value).length)) ? 'ready' : 'pending'; }"
                  />
                </keep-alive>
                <p class="alert alert-light border small mt-3 mb-0">
                  Drag module options onto each stage. Once every stage has a selection the compressor will be marked as ready.
                </p>
              </template>
              <template v-else>
                <div class="text-muted small">Unsupported node type.</div>
              </template>
            </template>
          </div>
        </div>
      </div>
    </div>

    
  </div>
</template>

<script>
import { markRaw } from 'vue';
import DataClipping from './filter/DataClipping.vue';
import DataThresholding from './filter/DataThresholding.vue';
import InputDataset from './InputDataset.vue';
import PipelineView from './compressor/SZ3Pipeline.vue';

export default {
  name: 'PipelineBrowser',
  components: {
    DataClipping,
    DataThresholding,
    InputDataset,
    PipelineView,
  },
  data() {
    const filterDefinitions = [
      {
        id: 'clipping',
        label: 'Clip',
        description: 'Trim dataset extents prior to compression.',
        icon: 'bi-crop',
        component: markRaw(DataClipping),
        props: {
          filterName: 'Clip Dataset',
          filterType: 'filter.clipping',
        },
      },
      {
        id: 'thresholding',
        label: 'Threshold',
        description: 'Filter data using lower/upper threshold values.',
        icon: 'bi-sliders',
        component: markRaw(DataThresholding),
        props: {
          filterName: 'Threshold',
          filterType: 'filter.thresholding',
        },
      },
    ];
    const moduleDefinitions = [
      {
        id: 'testing',
        label: 'Testing Module',
        description: 'A simple testing compressor module.',
        icon: 'bi-puzzle',
        // component: markRaw(BaseCompressorModule),
        props: {
          moduleName: 'Testing Module',
          moduleType: 'module.testing',
        },
      },
    ];
    const compressorDefinitions = [
      {
        id: 'sz3',
        label: 'SZ3 Compressor',
        description: 'A Modular Error-bounded Lossy Compression Framework.',
        component: markRaw(PipelineView),
      },
    ];
    const sourceNode = {
      id: 'source',
      type: 'source',
      label: 'Input Data',
      icon: 'bi-database',
      status: 'empty',
      statusMessage: 'Double-click to configure the input dataset.',
      lastRunAt: null,
    };
    return {
      availableFilters: filterDefinitions,
      moduleDefinitions,
      availableCompressors: compressorDefinitions,
      pipelineNodes: [sourceNode],
      selectedNodeId: sourceNode.id,
      filterCounter: 0,
      moduleCounter: 0,
      previousDatasetToken: null,
      modalVisible: false,
      modalNodeId: null,
      detailsVisible: false,
      activeTab: 'info',
      showOperationModal: false,
      modalActiveCategory: 'filters',
      operationSearch: '',
    };
  },
  computed: {
    datasetToken() {
      return this.$store?.state?.dataset?.content || null;
    },
    datasetLoaded() {
      return Boolean(this.datasetToken);
    },
    datasetInfo() {
      const ds = this.$store?.state?.dataset || null;
      if (!ds) return null;
      // Dimensions (optional)
      let width = null, height = null, depth = null;
      const dims = ds.dimensions;
      if (Array.isArray(dims) && dims.length >= 3) {
        [width, height, depth] = dims.map((value) => Number(value));
      }
      // Variables (NetCDF)
      let vars = [];
      if (ds.type === 'netcdf') {
        if (Array.isArray(ds.vars)) {
          vars = ds.vars;
        } else if (ds.vars && typeof ds.vars === 'object') {
          vars = Object.keys(ds.vars);
        }
      }
      return {
        name: ds.name || null,
        type: ds.type || null,
        size: ds.size || null,
        width,
        height,
        depth,
        precision: ds.precision || null,
        vars,
      };
    },
    pipelineList() {
      return [...this.pipelineNodes];
    },
    selectedNode() {
      return this.pipelineList.find((node) => node.id === this.selectedNodeId) || null;
    },
    filterNodes() {
      return this.pipelineNodes.filter((node) => node.type === 'filter');
    },
    isPipelineReady() {
      const filtersReady = this.filterNodes.every((node) => node.status === 'success' || node.status === 'ready');
      return this.datasetLoaded && filtersReady;
    },
    modalNode() {
      return this.modalNodeId ? this.findNode(this.modalNodeId) : null;
    },
    canDeleteSelected() {
      return Boolean(this.selectedNode && this.selectedNode.type !== 'source');
    },
    normalizedSearch() {
      return (this.operationSearch || '').toLowerCase().trim();
    },
    filteredFilters() {
      const term = this.normalizedSearch;
      if (!term) return this.availableFilters;
      return this.availableFilters.filter((f) => {
        const hay = `${f.label || ''} ${f.description || ''} ${f.id || ''}`.toLowerCase();
        return hay.includes(term);
      });
    },
    filteredModules() {
      const term = this.normalizedSearch;
      if (!term) return this.moduleDefinitions;
      return this.moduleDefinitions.filter((m) => {
        const hay = `${m.label || ''} ${m.description || ''} ${m.id || ''}`.toLowerCase();
        return hay.includes(term);
      });
    },
    filteredCompressors() {
      const term = this.normalizedSearch;
      if (!term) return this.availableCompressors;
      return this.availableCompressors.filter((c) => {
        const hay = `${c.label || ''} ${c.description || ''} ${c.id || ''}`.toLowerCase();
        return hay.includes(term);
      });
    },
  },
  watch: {
    datasetLoaded: {
      immediate: true,
      handler(loaded) {
        if (loaded) {
          this.setNodeStatus('source', 'ready', 'Dataset loaded and ready for operations.');
        } else {
          this.setNodeStatus('source', 'empty', 'Double-click to configure the input dataset.');
          this.markAllFiltersAsStale('Dataset unavailable. Re-run after loading new data.');
        }
      },
    },
    datasetToken(next, previous) {
      if (previous && next !== previous) {
        this.markAllFiltersAsStale('Dataset changed. Re-run this filter to refresh its output.');
      }
    },
  },
  methods: {
    deleteSelectedNode() {
      const nodeId = this.selectedNodeId;
      const node = this.findNode(nodeId);
      if (!node || node.type === 'source') return;
      this.removeNode(nodeId);
    },
    removeNode(nodeId) {
      const node = this.findNode(nodeId);
      if (!node || node.type === 'source') return;
      if (node.type === 'filter') {
        this.removeFilter(nodeId);
        return;
      }
      if (node.type === 'module') {
        this.removeModule(nodeId);
        return;
      }
      if (node.type === 'compressor') {
        const index = this.pipelineNodes.findIndex((n) => n.id === nodeId);
        if (index !== -1) {
          const wasSelected = this.selectedNodeId === nodeId;
          this.pipelineNodes.splice(index, 1);
          if (wasSelected) {
            const fallback = this.pipelineNodes[index] || this.pipelineNodes[index - 1] || this.pipelineNodes[0] || null;
            this.selectedNodeId = fallback ? fallback.id : null;
          }
        }
        return;
      }
      // Default: remove unknown node types safely
      const idx = this.pipelineNodes.findIndex((n) => n.id === nodeId);
      if (idx !== -1) this.pipelineNodes.splice(idx, 1);
    },
    openOperationModal() {
      this.modalActiveCategory = 'filters';
      this.showOperationModal = true;
    },
    closeOperationModal() {
      this.showOperationModal = false;
    },
    selectNode(nodeId) {
      this.selectedNodeId = nodeId;
      this.activeTab = 'info';
    },
    openNodeDetails(nodeId) {
      this.selectNode(nodeId);
      this.detailsVisible = true;
      this.activeTab = 'config';
    },
    closeNodeDetails() {
      this.detailsVisible = false;
    },
    findNode(nodeId) {
      return this.pipelineNodes.find((node) => node.id === nodeId) || null;
    },
    setNodeStatus(nodeId, status, message) {
      const node = this.findNode(nodeId);
      if (!node) return;
      node.status = status || 'pending';
      if (message !== undefined) {
        node.statusMessage = message;
      }
      if (status !== 'error') {
        node.lastError = null;
      }
    },
    getStatusLabel(status) {
      const map = {
        ready: 'Ready',
        success: 'Completed',
        running: 'Running',
        error: 'Error',
        pending: 'Pending',
        stale: 'Stale',
        invalid: 'Needs Attention',
        empty: 'No Dataset',
      };
      return map[status] || 'Idle';
    },
    getStatusBadgeClass(status) {
      const map = {
        ready: 'bg-success',
        success: 'bg-success',
        running: 'bg-primary',
        error: 'bg-danger',
        pending: 'bg-warning text-dark',
        invalid: 'bg-warning text-dark',
        stale: 'bg-secondary',
        empty: 'bg-secondary',
        idle: 'bg-secondary',
      };
      return map[status] || 'bg-secondary';
    },
    getStatusIconClass(status) {
      const map = {
        ready: 'text-success',
        success: 'text-success',
        running: 'text-primary',
        error: 'text-danger',
        pending: 'text-warning',
        invalid: 'text-warning',
        stale: 'text-secondary',
        empty: 'text-muted',
        idle: 'text-muted',
      };
      return map[status] || 'text-muted';
    },
    describeModuleSelection(module) {
      if (!module || !module.value || !Object.keys(module.value).length) {
        return 'Not configured';
      }
      const [label] = Object.keys(module.value);
      return label || 'Configured';
    },
    addFilter(filterId) {
      const definition = this.availableFilters.find((item) => item.id === filterId);
      if (!definition || !this.datasetLoaded) return;
      this.filterCounter += 1;
      const nodeId = `filter-${definition.id}-${this.filterCounter}`;
      const newNode = {
        id: nodeId,
        type: 'filter',
        label: definition.label,
        description: definition.description,
        icon: definition.icon || 'bi-funnel',
        definitionId: definition.id,
        component: definition.component,
        props: {
          ...(definition.props || {}),
          filterName: definition.label,
        },
        status: 'pending',
        statusMessage: 'Configure the filter and apply it to generate output.',
        lastResult: null,
        lastRunAt: null,
        lastRunContext: null,
        lastError: null,
      };
      this.pipelineNodes.push(newNode);
      this.selectedNodeId = nodeId;
      this.detailsVisible = true;
    },
    addModule(moduleId) {
      const definition = this.moduleDefinitions.find((item) => item.id === moduleId);
      if (!definition || !this.datasetLoaded) return;
      this.moduleCounter += 1;
      const nodeId = `module-${definition.id}-${this.moduleCounter}`;
      const newNode = {
        id: nodeId,
        type: 'module',
        label: definition.label,
        description: definition.description,
        icon: definition.icon || 'bi-puzzle',
        definitionId: definition.id,
        component: definition.component,
        props: {
          ...(definition.props || {}),
          moduleName: definition.label,
        },
        status: 'pending',
        statusMessage: 'Configure the module and apply settings.',
        lastUpdatedAt: null,
      };
      this.pipelineNodes.push(newNode);
      this.selectedNodeId = nodeId;
      this.detailsVisible = true;
    },
    addCompressor(compressorId) {
      const definition = this.availableCompressors.find((c) => c.id === compressorId);
      if (!definition || !this.datasetLoaded) return;
      // Only one compressor at a time; remove existing compressor nodes
      this.pipelineNodes = this.pipelineNodes.filter((n) => n.type !== 'compressor');
      const nodeId = `compressor-${definition.id}`;
      const newNode = {
        id: nodeId,
        type: 'compressor',
        label: definition.label,
        description: definition.description,
        icon: 'bi-cpu',
        definitionId: definition.id,
        component: definition.component,
        renderKey: 0,
        status: 'pending',
        statusMessage: 'Configure modules for the compressor.',
        modules: [],
        lastUpdatedAt: null,
      };
      this.pipelineNodes.push(newNode);
      this.selectedNodeId = nodeId;
      this.detailsVisible = true;
    },
    removeFilter(nodeId) {
      const index = this.pipelineNodes.findIndex((node) => node.id === nodeId && node.type === 'filter');
      if (index === -1) return;
      const wasSelected = this.selectedNodeId === nodeId;
      this.pipelineNodes.splice(index, 1);
      if (wasSelected) {
        const fallback = this.pipelineNodes[index] || this.pipelineNodes[index - 1] || this.pipelineNodes[0];
        this.selectedNodeId = fallback ? fallback.id : null;
      }
    },
    handleModuleStart(nodeId) {
      this.setNodeStatus(nodeId, 'running', 'Configuring module...');
    },
    handleModuleSuccess(nodeId, payload) {
      const node = this.findNode(nodeId);
      if (!node) return;
      node.lastUpdatedAt = Date.now();
      const message = payload?.message || 'Module configured.';
      this.setNodeStatus(nodeId, 'ready', message);
    },
    handleModuleError(nodeId, payload) {
      const message = payload?.error?.message || 'Module configuration failed.';
      this.setNodeStatus(nodeId, 'error', message);
    },
    handleModuleInvalid(nodeId, payload) {
      const message = payload?.message || 'Parameters invalid. Adjust settings and retry.';
      this.setNodeStatus(nodeId, 'invalid', message);
    },
    handleModuleFinish(nodeId) {
      const node = this.findNode(nodeId);
      if (!node) return;
      if (node.status === 'running') {
        this.setNodeStatus(nodeId, 'pending', 'Review and apply again if needed.');
      }
    },
    removeModule(nodeId) {
      const index = this.pipelineNodes.findIndex((node) => node.id === nodeId && node.type === 'module');
      if (index === -1) return;
      const wasSelected = this.selectedNodeId === nodeId;
      this.pipelineNodes.splice(index, 1);
      if (wasSelected) {
        const fallback = this.pipelineNodes[index] || this.pipelineNodes[index - 1] || this.pipelineNodes[0] || null;
        this.selectedNodeId = fallback ? fallback.id : null;
      }
    },
    clearFilters() {
      if (!this.filterNodes.length) return;
      this.pipelineNodes = this.pipelineNodes.filter((node) => node.type !== 'filter');
      if (this.selectedNode && this.selectedNode.type === 'filter') {
        const source = this.pipelineNodes.find(n => n.type === 'source') || this.pipelineNodes[0] || null;
        this.selectedNodeId = source ? source.id : null;
      }
      if (this.modalNode && this.modalNode.type === 'filter') {
        this.closeNodeModal();
      }
    },
    handleFilterStart(nodeId) {
      this.setNodeStatus(nodeId, 'running', 'Applying filter...');
    },
    handleFilterSuccess(nodeId, payload) {
      const node = this.findNode(nodeId);
      if (!node) return;
      const result = payload?.result || null;
      const context = payload?.context || null;
      node.lastResult = result;
      node.lastRunContext = context;
      node.lastRunAt = Date.now();
      let message = 'Filter applied successfully.';
      if (result?.dimensions && Array.isArray(result.dimensions)) {
        message = `Output dimensions ${result.dimensions.join('×')}.`;
      }
      this.setNodeStatus(nodeId, 'success', message);
    },
    handleFilterError(nodeId, payload) {
      const node = this.findNode(nodeId);
      if (!node) return;
      const error = payload?.error;
      node.lastError = error || null;
      const message = error?.message || 'Filter failed. Check the console for details.';
      this.setNodeStatus(nodeId, 'error', message);
    },
    handleFilterInvalid(nodeId, payload) {
      const message = payload?.message || 'Parameters invalid. Adjust settings and retry.';
      this.setNodeStatus(nodeId, 'invalid', message);
    },
    handleFilterFinish(nodeId) {
      const node = this.findNode(nodeId);
      if (!node) return;
      if (node.status === 'running') {
        this.setNodeStatus(nodeId, 'pending', 'Review the output or run again.');
      }
    },
    handleFilterDatasetChange(nodeId) {
      const node = this.findNode(nodeId);
      if (!node || node.status === 'running') return;
      this.setNodeStatus(nodeId, 'stale', 'Dataset changed. Re-run to refresh results.');
    },
    markAllFiltersAsStale(message) {
      this.filterNodes.forEach((node) => {
        if (['success', 'ready'].includes(node.status)) {
          this.setNodeStatus(node.id, 'stale', message || 'Dataset changed. Re-run to refresh results.');
        }
      });
    },
    openNodeModal() {},
    closeNodeModal() {},
    formatTimestamp(timestamp) {
      if (!timestamp) return '—';
      const date = new Date(timestamp);
      return date.toLocaleString();
    },
    formatDimensions(summary) {
      if (!summary) return '';
      const { width, height, depth } = summary;
      return [width, height, depth]
        .filter((value) => value !== undefined && value !== null)
        .map((value) => (Number.isFinite(value) ? value : '-'))
        .join('×');
    },
    formatPrecision(precision) {
      if (!precision) return 'Unknown';
      if (precision === 'f') return 'float32';
      if (precision === 'd') return 'float64';
      return precision;
    },
  },
};
</script>

<style scoped>
.list-group-item { cursor: pointer; }
.list-group-item.active {
  background-color: var(--bs-primary-bg-subtle, #e7f1ff) !important;
  border-color: var(--bs-primary-border-subtle, #b6d4fe) !important;
  color: var(--bs-body-color, #212529) !important;
}

.operation-modal .modal-dialog {
  width: 800px;
  max-width: 900px;
}
.operation-modal .modal-content {
  height: 500px;
  display: flex;
  flex-direction: column;
}
.operation-modal .modal-header,
.operation-modal .modal-footer {
  flex: 0 0 auto;
}
.operation-modal .modal-body {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.operation-modal .modal-body .row {
  flex: 1 1 auto;
  min-height: 0;
}
.operation-modal .modal-body .col-8 {
  overflow-y: auto;
}
</style>
