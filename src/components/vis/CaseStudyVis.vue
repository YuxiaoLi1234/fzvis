<template>
  <div class="case-study-vis h-100 overflow-auto p-3">
    <div class="d-flex justify-content-between align-items-start flex-wrap gap-3 mb-3">
      <div>
        <h4 class="mb-1">SZ3 Case Study</h4>
        <p class="text-muted mb-0">
          Load an SZ3 case-study export and inspect residuals, quantization, spatial slices, and runtime tradeoffs.
        </p>
      </div>
      <!-- <span class="badge text-bg-light border">Safe root: <code>{{ caseStudyBaseDir || '~/.fzvis/case_studies' }}</code></span> -->
    </div>

    <div class="card shadow-sm mb-3">
      <div class="card-body">
        <div class="row g-3 align-items-end">
          <div class="col-xl-4">
            <label class="form-label">Available case studies</label>
            <select v-model="serverStudyPath" class="form-select">
              <option value="">Select from folder...</option>
              <option v-for="path in availablePaths" :key="path" :value="path">{{ $maskDisplayPath(path) }}</option>
            </select>
          </div>
          <div class="col-xl-3">
            <label class="form-label">Display name</label>
            <input v-model.trim="uploadStudyName" type="text" class="form-control" placeholder="Optional">
          </div>
          <div class="col-xl-3 d-grid">
            <button class="btn btn-success" :disabled="!serverStudyPath || busy" @click="registerServerPath">
              <span v-if="registeringServerPath" class="spinner-border spinner-border-sm me-2"></span>
              Register
            </button>
          </div>
          <div class="col-xl-2 d-grid">
            <button class="btn btn-outline-secondary" :disabled="busy" @click="loadCaseStudies(); loadAvailablePaths()">Refresh</button>
          </div>
        </div>

        <hr class="my-3">

        <div class="row g-3 align-items-end">
          <div class="col-lg-6">
            <label class="form-label">Upload new case</label>
            <input
              ref="folderInput"
              type="file"
              class="form-control"
              webkitdirectory
              directory
              multiple
              @change="handleFolderChange"
            >
            <div class="form-text">Use this when the study is not already present on the server.</div>
          </div>
          <div class="col-lg-3">
            <div v-if="folderSummary" class="small text-muted">
              Ready to upload <strong>{{ folderSummary.root }}</strong> ({{ folderSummary.fileCount }} files)
            </div>
          </div>
          <div class="col-lg-3 d-grid">
            <button class="btn btn-primary" :disabled="!folderFiles.length || busy" @click="uploadFolder">
              <span v-if="uploading" class="spinner-border spinner-border-sm me-2"></span>
              Upload folder
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="card shadow-sm mb-3">
      <div class="card-body">
        <div class="row g-3 align-items-end">
          <div class="col-lg-4">
            <label class="form-label">Loaded studies</label>
            <select v-model="selectedStudyId" class="form-select" @change="handleStudyChange">
              <option value="">Select a case study</option>
              <option v-for="study in caseStudyList" :key="study.id" :value="study.id">
                {{ study.name }} ({{ study.run_count }} runs)
              </option>
            </select>
          </div>
          <div v-if="studyManifest" class="col-lg-8">
            <div class="small text-muted mb-1">Dataset</div>
            <div class="fw-semibold text-break">{{ studyManifest.dataset || 'Unknown dataset' }}</div>
            <div class="small text-muted">{{ formatDims(studyManifest.dims) }} · {{ studyManifest.data_type }}</div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="studyManifest" class="row g-3 mb-3">
      <div class="col-md-3 col-sm-6"><div class="card h-100 shadow-sm"><div class="card-body"><div class="text-muted small">Runs</div><div class="fs-4 fw-semibold">{{ studyRuns.length }}</div></div></div></div>
      <div class="col-md-3 col-sm-6"><div class="card h-100 shadow-sm"><div class="card-body"><div class="text-muted small">Dimensions</div><div class="fw-semibold">{{ formatDims(studyManifest.dims) }}</div></div></div></div>
      <div class="col-md-3 col-sm-6"><div class="card h-100 shadow-sm"><div class="card-body"><div class="text-muted small">Quantizer</div><div class="fw-semibold text-truncate">{{ studyManifest.fixed_modules?.quantizer || '—' }}</div></div></div></div>
      <div class="col-md-3 col-sm-6"><div class="card h-100 shadow-sm"><div class="card-body"><div class="text-muted small">Abs Error Bound</div><div class="fw-semibold">{{ formatMetric(studyManifest.fixed_modules?.abs_error_bound) }}</div></div></div></div>
    </div>

    <div v-if="studyManifest" class="card shadow-sm mb-3">
      <div class="card-header bg-white fw-semibold">Predictor Runs</div>
      <div class="card-body">
        <div class="d-flex flex-wrap gap-2">
          <button
            v-for="run in studyRuns"
            :key="run.id"
            type="button"
            class="btn btn-sm"
            :class="selectedRunIds.includes(run.id) ? 'btn-primary' : 'btn-outline-primary'"
            @click="toggleRunSelection(run.id)"
          >
            {{ run.id }}
          </button>
        </div>
        <div class="form-text mt-2">The selected runs drive the comparison charts. The first selected run is the spatial baseline.</div>
      </div>
    </div>

    <div v-if="studyManifest" class="card shadow-sm mb-3">
      <div class="card-header bg-white fw-semibold">Plot Settings</div>
      <div class="card-body">
        <div class="row g-3 align-items-center">
          <div class="col-auto">
            <label class="form-label mb-0">Chart Height (px)</label>
          </div>
          <div class="col-auto">
            <input
              v-model.number="chartHeight"
              type="number"
              class="form-control"
              style="width: 100px"
              min="200"
              max="1000"
              step="50"
              @change="refreshVisualizations"
            >
          </div>
        </div>
      </div>
    </div>

    <div v-if="selectedRuns.length" class="card shadow-sm mb-3">
      <div class="card-header bg-white fw-semibold">Run Summary</div>
      <div class="card-body p-0">
        <div class="table-responsive">
          <table class="table table-sm align-middle mb-0">
            <thead class="table-light">
              <tr>
                <th>Run</th>
                <th>Predictor</th>
                <th>Compression Ratio</th>
                <th>Bits / Value</th>
                <th>Total Time (s)</th>
                <th>Prediction Time (s)</th>
                <th>Throughput</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="run in selectedRuns" :key="run.id">
                <td>{{ run.id }}</td>
                <td>{{ run.predictor || run.id }}</td>
                <td>{{ formatMetric(metricsByRun[run.id]?.compression_ratio) }}</td>
                <td>{{ formatMetric(metricsByRun[run.id]?.bits_per_value) }}</td>
                <td>{{ formatMetric(metricsByRun[run.id]?.stage_time_seconds?.total) }}</td>
                <td>{{ formatMetric(metricsByRun[run.id]?.stage_time_seconds?.prediction) }}</td>
                <td>{{ formatScientific(metricsByRun[run.id]?.values_per_second) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div v-if="selectedRuns.length" class="card shadow-sm mb-3">
      <div class="card-header bg-white d-flex justify-content-between align-items-center gap-2 flex-wrap">
        <span class="fw-semibold">Residual Distribution</span>
        <div class="d-flex gap-2 flex-wrap align-items-center">
          <select v-model="residualMode" class="form-select form-select-sm control-select" @change="scheduleRefresh">
            <option value="signed">Signed residual</option>
            <option value="absolute">Absolute residual</option>
          </select>
          <select v-model="residualHistnorm" class="form-select form-select-sm control-select" @change="drawResidualCharts">
            <option value="probability density">Density</option>
            <option value="">Count</option>
          </select>
          <input v-model.number="residualClipMultiplier" type="number" min="1" step="1" class="form-control form-control-sm control-number" @change="scheduleRefresh">
        </div>
      </div>
      <div class="card-body">
        <div v-if="loadingResiduals" class="small text-muted mb-2">Loading residual summaries...</div>
        <div ref="residualHistogram" class="plot"></div>
        <div ref="residualCdf" class="plot mt-3"></div>
      </div>
    </div>

    <div v-if="selectedRuns.length" class="card shadow-sm mb-3">
      <div class="card-header bg-white d-flex justify-content-between align-items-center gap-2 flex-wrap">
        <span class="fw-semibold">Spatial Residual Map</span>
        <div class="d-flex gap-2 flex-wrap align-items-center">
          <select v-model="spatialPrimaryRunId" class="form-select form-select-sm control-select" @change="scheduleRefresh">
            <option v-for="run in selectedRuns" :key="`sp-${run.id}`" :value="run.id">{{ run.id }}</option>
          </select>
          <select v-model="spatialMode" class="form-select form-select-sm control-select" @change="scheduleRefresh">
            <option value="absolute">Absolute</option>
            <option value="signed">Signed</option>
            <option value="delta" :disabled="selectedRuns.length < 2">Delta</option>
            <option value="fallback">Fallback mask</option>
          </select>
          <select v-if="spatialMode === 'delta'" v-model="spatialCompareRunId" class="form-select form-select-sm control-select" @change="scheduleRefresh">
            <option v-for="run in selectedRuns" :key="`cmp-${run.id}`" :value="run.id">{{ run.id }}</option>
          </select>
        </div>
      </div>
      <div class="card-body">
        <div v-if="sliceControl.visible" class="mb-2 d-flex gap-2 align-items-center">
          <input v-model.number="spatialSliceIndex" :min="0" :max="sliceControl.max" type="range" class="form-range slice-range" @input="scheduleRefresh">
          <span class="small text-muted">Slice {{ spatialSliceIndex }} / {{ sliceControl.max }}</span>
        </div>
        <div v-if="loadingSpatial" class="small text-muted mb-2">Loading spatial slice...</div>
        <div ref="spatialChart" class="plot tall"></div>
        <div class="form-text mt-2">Slices are coarse inspection only because SZ3 exports traversal order, not guaranteed exact row-major layout.</div>
      </div>
    </div>

    <div v-if="selectedRuns.length" class="card shadow-sm mb-3">
      <div class="card-header bg-white d-flex justify-content-between align-items-center gap-2 flex-wrap">
        <span class="fw-semibold">Quantization Distribution</span>
        <div class="d-flex gap-2 align-items-center flex-wrap">
          <label class="small text-muted mb-0">Clip</label>
          <select v-model="quantClipMode" class="form-select form-select-sm control-select" @change="scheduleRefresh">
            <option value="p99">p99</option>
            <option value="none">None</option>
          </select>
        </div>
      </div>
      <div class="card-body">
        <div v-if="loadingQuant" class="small text-muted mb-2">Loading quantization summaries...</div>
        <div ref="quantHistogram" class="plot"></div>
        <div ref="quantShares" class="plot mt-3"></div>
      </div>
    </div>

    <div v-if="selectedRuns.length" class="card shadow-sm mb-3">
      <div class="card-header bg-white fw-semibold">Stage-Wise Runtime Breakdown</div>
      <div class="card-body">
        <div ref="runtimeChart" class="plot tall"></div>
      </div>
    </div>

    <div v-if="selectedRuns.length >= 2" class="card shadow-sm mb-3">
      <div class="card-header bg-white fw-semibold">Pairwise Delta</div>
      <div class="card-body">
        <div v-if="loadingPairwise" class="small text-muted mb-2">Loading pairwise summary...</div>
        <div class="row g-3">
          <div v-for="delta in pairwiseDeltas" :key="delta.label" class="col-md-4">
            <div class="border rounded p-3 h-100 bg-light-subtle">
              <div class="text-muted small">{{ delta.label }}</div>
              <div class="fw-semibold">{{ delta.value }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="studyManifest && !selectedRuns.length" class="alert alert-info">
      Select at least one run to render the visualizations.
    </div>
  </div>
</template>

<script>
import axios from 'axios'
import Plotly from 'plotly.js-dist-min'

export default {
  name: 'CaseStudyVis',

  data() {
    return {
      baseURL: '/api',
      caseStudyBaseDir: '',
      caseStudies: {},
      selectedStudyId: '',
      studyManifest: null,
      selectedRunIds: [],
      metricsByRun: {},
      residualSummary: null,
      quantSummary: null,
      spatialSliceData: null,
      pairwiseSummary: null,
      uploadStudyName: '',
      serverStudyPath: '',
      availablePaths: [],
      folderFiles: [],
      folderSummary: null,
      uploading: false,
      registeringServerPath: false,
      loadingResiduals: false,
      loadingSpatial: false,
      loadingQuant: false,
      loadingPairwise: false,
      residualMode: 'signed',
      residualHistnorm: 'probability density',
      residualClipMultiplier: 20,
      spatialMode: 'absolute',
      spatialPrimaryRunId: '',
      spatialCompareRunId: '',
      spatialSliceIndex: 0,
      quantClipMode: 'p99',
      chartHeight: 400,
      resizeHandler: null,
      tabShownHandler: null,
    }
  },

  computed: {
    busy() {
      return this.uploading || this.registeringServerPath
    },
    caseStudyList() {
      return Object.values(this.caseStudies || {}).sort((a, b) => String(a.name || a.id).localeCompare(String(b.name || b.id)))
    },
    studyRuns() {
      return this.studyManifest?.runs || []
    },
    selectedRuns() {
      const runMap = new Map(this.studyRuns.map((run) => [run.id, run]))
      return this.selectedRunIds.map((runId) => runMap.get(runId)).filter(Boolean)
    },
    sliceControl() {
      const dims = (this.studyManifest?.dims || []).map((value) => Number(value))
      if (dims.length < 3) return { visible: false, max: 0 }
      const count = dims.slice(0, -2).reduce((acc, value) => acc * Math.max(1, Number(value || 1)), 1)
      return { visible: true, max: Math.max(0, count - 1) }
    },
    pairwiseDeltas() {
      if (!this.pairwiseSummary) return []
      return [
        { label: `Δ compression ratio (${this.pairwiseSummary.run_b} - ${this.pairwiseSummary.run_a})`, value: this.formatSignedDelta(this.pairwiseSummary.delta_compression_ratio, 0) },
        { label: `Δ p95 |residual| (${this.pairwiseSummary.run_b} - ${this.pairwiseSummary.run_a})`, value: this.formatSignedDelta(this.pairwiseSummary.delta_p95_abs_residual, 0) },
        { label: `Δ p99 |residual| (${this.pairwiseSummary.run_b} - ${this.pairwiseSummary.run_a})`, value: this.formatSignedDelta(this.pairwiseSummary.delta_p99_abs_residual, 0) },
        { label: `Δ medium-index share (${this.pairwiseSummary.run_b} - ${this.pairwiseSummary.run_a})`, value: this.formatSignedDelta(this.pairwiseSummary.delta_medium_share, 0, true) },
        { label: `Δ large-index share (${this.pairwiseSummary.run_b} - ${this.pairwiseSummary.run_a})`, value: this.formatSignedDelta(this.pairwiseSummary.delta_large_share, 0, true) },
        { label: `Δ prediction time (${this.pairwiseSummary.run_b} - ${this.pairwiseSummary.run_a})`, value: this.formatSignedDelta(this.pairwiseSummary.delta_prediction_time, 0) },
      ]
    },
  },

  async mounted() {
    this.resizeHandler = () => this.resizePlots()
    this.tabShownHandler = (event) => {
      if (event?.target?.id === 'case-study-tab') {
        this.$nextTick(() => this.refreshVisualizations())
      }
    }
    window.addEventListener('resize', this.resizeHandler)
    document.addEventListener('shown.bs.tab', this.tabShownHandler)
    await Promise.all([this.loadCaseStudies(), this.loadAvailablePaths()])
  },

  beforeUnmount() {
    window.removeEventListener('resize', this.resizeHandler)
    document.removeEventListener('shown.bs.tab', this.tabShownHandler)
    this.purgePlots()
  },

  methods: {
    async loadCaseStudies() {
      try {
        const response = await axios.get(`${this.baseURL}/caseStudies`)
        this.caseStudies = response.data.case_studies || {}
        this.caseStudyBaseDir = response.data.base_dir || this.caseStudyBaseDir
      } catch (error) {
        this.notifyError('Failed to load case studies', error)
      }
    },

    async loadAvailablePaths() {
      try {
        const response = await axios.get(`${this.baseURL}/caseStudy/availablePaths`)
        this.availablePaths = response.data.available_paths || []
        this.caseStudyBaseDir = response.data.base_dir || this.caseStudyBaseDir
      } catch (error) {
        this.notifyError('Failed to load available case study paths', error)
      }
    },

    handleFolderChange(event) {
      const files = Array.from(event.target.files || [])
      this.folderFiles = files
      if (!files.length) {
        this.folderSummary = null
        return
      }
      const root = (files[0].webkitRelativePath || files[0].name).split('/')[0]
      this.folderSummary = { root, fileCount: files.length }
      if (!this.uploadStudyName) this.uploadStudyName = root
    },

    async uploadFolder() {
      if (!this.folderFiles.length) return
      this.uploading = true
      const formData = new FormData()
      this.folderFiles.forEach((file) => {
        formData.append('files', file)
        formData.append('relative_paths', file.webkitRelativePath || file.name)
      })
      if (this.uploadStudyName) formData.append('study_name', this.uploadStudyName)
      try {
        this.$store.commit('setStatus', { type: 'info', message: 'Uploading case study folder...' })
        const response = await axios.post(`${this.baseURL}/caseStudy/upload`, formData)
        await this.applyLoadedStudy(response.data.case_study, response.data.manifest)
        this.$store.commit('setStatus', { type: 'success', message: 'Case study uploaded successfully.' })
      } catch (error) {
        this.notifyError('Case study upload failed', error)
      } finally {
        this.uploading = false
      }
    },

    async registerServerPath() {
      if (!this.serverStudyPath) return
      this.registeringServerPath = true
      try {
        this.$store.commit('setStatus', { type: 'info', message: 'Registering case study from server path...' })
        const response = await axios.post(`${this.baseURL}/caseStudy/register`, {
          path: this.serverStudyPath,
          study_name: this.uploadStudyName || undefined,
        })
        this.caseStudyBaseDir = response.data.base_dir || this.caseStudyBaseDir
        await this.applyLoadedStudy(response.data.case_study, response.data.manifest)
        this.$store.commit('setStatus', { type: 'success', message: 'Case study registered successfully.' })
      } catch (error) {
        this.notifyError('Case study registration failed', error)
      } finally {
        this.registeringServerPath = false
      }
    },

    async handleStudyChange() {
      if (!this.selectedStudyId) {
        this.clearStudyState()
        return
      }
      try {
        const response = await axios.get(`${this.baseURL}/caseStudy/manifest`, { params: { studyId: this.selectedStudyId } })
        await this.applyLoadedStudy(response.data.case_study, response.data.manifest)
      } catch (error) {
        this.notifyError('Failed to load case study manifest', error)
      }
    },

    clearStudyState() {
      this.studyManifest = null
      this.selectedRunIds = []
      this.metricsByRun = {}
      this.residualSummary = null
      this.quantSummary = null
      this.spatialSliceData = null
      this.pairwiseSummary = null
      this.purgePlots()
    },

    async applyLoadedStudy(study, manifest) {
      this.caseStudies = { ...this.caseStudies, [study.id]: study }
      this.selectedStudyId = study.id
      this.studyManifest = manifest
      this.selectedRunIds = (manifest?.runs || []).slice(0, 2).map((run) => run.id)
      this.metricsByRun = {}
      this.residualSummary = null
      this.quantSummary = null
      this.spatialSliceData = null
      this.pairwiseSummary = null
      this.spatialSliceIndex = 0
      this.spatialPrimaryRunId = this.selectedRunIds[0] || ''
      this.spatialCompareRunId = this.selectedRunIds[1] || this.selectedRunIds[0] || ''
      await this.loadMetricsForSelectedRuns(true)
      await this.$nextTick()
      this.drawRuntimeChart()
      await this.refreshVisualizations()
    },

    toggleRunSelection(runId) {
      const selected = [...this.selectedRunIds]
      const index = selected.indexOf(runId)
      if (index >= 0) selected.splice(index, 1)
      else selected.push(runId)
      this.selectedRunIds = selected
      if (!this.selectedRunIds.includes(this.spatialPrimaryRunId)) {
        this.spatialPrimaryRunId = this.selectedRunIds[0] || ''
      }
      if (!this.selectedRunIds.includes(this.spatialCompareRunId)) {
        this.spatialCompareRunId = this.selectedRunIds[1] || this.selectedRunIds[0] || ''
      }
      this.scheduleRefresh()
    },

    scheduleRefresh() {
      this.$nextTick(() => this.refreshVisualizations())
    },

    async loadMetricsForSelectedRuns(loadAll = false) {
      const runIds = loadAll ? this.studyRuns.map((run) => run.id) : this.selectedRunIds
      await Promise.all(runIds.map((runId) => this.ensureMetrics(runId)))
    },

    async ensureMetrics(runId) {
      if (!runId || this.metricsByRun[runId]) return this.metricsByRun[runId]
      const response = await axios.get(`${this.baseURL}/caseStudy/metrics`, {
        params: { studyId: this.selectedStudyId, runId },
      })
      this.metricsByRun = { ...this.metricsByRun, [runId]: response.data.metrics }
      return response.data.metrics
    },

    async refreshVisualizations() {
      if (!this.studyManifest || !this.selectedRunIds.length) {
        this.purgePlots()
        return
      }
      await this.loadMetricsForSelectedRuns()
      this.drawRuntimeChart()
      if (!this.isVisible()) return
      await Promise.all([
        this.refreshResidualSection(),
        this.refreshSpatialSection(),
        this.refreshQuantSection(),
        this.refreshPairwiseSection(),
      ])
      this.resizePlots()
    },

    async refreshResidualSection() {
      this.loadingResiduals = true
      try {
        const response = await axios.get(`${this.baseURL}/caseStudy/residualSummary`, {
          params: {
            studyId: this.selectedStudyId,
            runIds: this.selectedRunIds.join(','),
            mode: this.residualMode,
            clipMultiplier: this.residualClipMultiplier,
            bins: 80,
            histnorm: this.residualHistnorm,
          },
        })
        this.residualSummary = response.data
        this.drawResidualCharts()
      } catch (error) {
        this.notifyError('Failed to load residual summaries', error)
      } finally {
        this.loadingResiduals = false
      }
    },

    async refreshSpatialSection() {
      this.loadingSpatial = true
      try {
        const params = {
          studyId: this.selectedStudyId,
          runId: this.spatialPrimaryRunId,
          mode: this.spatialMode,
          sliceIndex: this.spatialSliceIndex,
        }
        if (this.spatialMode === 'delta' && this.spatialCompareRunId) {
          params.compareRunId = this.spatialCompareRunId
        }
        const response = await axios.get(`${this.baseURL}/caseStudy/spatialSlice`, { params })
        this.spatialSliceData = response.data
        this.drawSpatialChart()
      } catch (error) {
        this.notifyError('Failed to load spatial slice', error)
      } finally {
        this.loadingSpatial = false
      }
    },

    async refreshQuantSection() {
      this.loadingQuant = true
      try {
        const response = await axios.get(`${this.baseURL}/caseStudy/quantSummary`, {
          params: {
            studyId: this.selectedStudyId,
            runIds: this.selectedRunIds.join(','),
            clip: this.quantClipMode,
            bins: 70,
          },
        })
        this.quantSummary = response.data
        this.drawQuantCharts()
      } catch (error) {
        this.notifyError('Failed to load quantization summaries', error)
      } finally {
        this.loadingQuant = false
      }
    },

    async refreshPairwiseSection() {
      if (this.selectedRunIds.length < 2) {
        this.pairwiseSummary = null
        return
      }
      this.loadingPairwise = true
      try {
        const response = await axios.get(`${this.baseURL}/caseStudy/pairwiseDelta`, {
          params: {
            studyId: this.selectedStudyId,
            runA: this.selectedRunIds[0],
            runB: this.selectedRunIds[1],
          },
        })
        this.pairwiseSummary = response.data
      } catch (error) {
        this.notifyError('Failed to load pairwise summary', error)
      } finally {
        this.loadingPairwise = false
      }
    },

    drawResidualCharts() {
      const histogramEl = this.$refs.residualHistogram
      const cdfEl = this.$refs.residualCdf
      if (!histogramEl || !cdfEl || !this.residualSummary?.runs) return

      const histTraces = this.selectedRunIds
        .map((runId) => {
          const run = this.residualSummary.runs[runId]
          if (!run?.histogram?.x?.length) return null
          return {
            type: 'bar',
            name: runId,
            x: run.histogram.x,
            y: run.histogram.y,
            opacity: 0.7,
            hovertemplate: '<b>%{fullData.name}</b><br>x: %{x:.3e}<br>y: %{y:.3e}<extra></extra>',
          }
        })
        .filter(Boolean)

      const cdfTraces = this.selectedRunIds
        .map((runId) => {
          const run = this.residualSummary.runs[runId]
          if (!run?.cdf?.x?.length) return null
          return {
            type: 'scatter',
            mode: 'lines',
            name: runId,
            x: run.cdf.x,
            y: run.cdf.y,
            line: { width: 3 },
            hovertemplate: '<b>%{fullData.name}</b><br>|residual|: %{x:.3e}<br>CDF: %{y:.3f}<extra></extra>',
          }
        })
        .filter(Boolean)

      Plotly.react(histogramEl, histTraces, {
        height: this.chartHeight,
        margin: { l: 110, r: 40, t: 40, b: 60 },
        barmode: 'overlay',
        legend: { font: { size: 15, weight: 500 }, x: 1.02, xanchor: 'left', y: 1 },
        xaxis: {
          title: { text: this.residualMode === 'absolute' ? '|Residual|' : 'Residual', font: { size: 24, weight: 600 } },
          tickfont: { size: 20, weight: 500 },
          linewidth: 2.5,
          gridcolor: '#e0e0e0'
        },
        yaxis: {
          title: { text: this.residualHistnorm ? 'Density' : 'Count', font: { size: 24, weight: 600 } },
          tickfont: { size: 20, weight: 500 },
          linewidth: 2.5,
          gridcolor: '#e0e0e0'
        },
        plot_bgcolor: 'white',
        paper_bgcolor: 'white',
      }, { responsive: true, displaylogo: false })

      Plotly.react(cdfEl, cdfTraces, {
        height: this.chartHeight,
        margin: { l: 110, r: 40, t: 40, b: 60 },
        legend: { font: { size: 15, weight: 500 }, x: 1.02, xanchor: 'left', y: 1 },
        xaxis: {
          title: { text: '|Residual|', font: { size: 24, weight: 600 } },
          tickfont: { size: 20, weight: 500 },
          linewidth: 2.5,
          gridcolor: '#e0e0e0'
        },
        yaxis: {
          title: { text: 'CDF', font: { size: 24, weight: 600 } },
          range: [0, 1],
          tickfont: { size: 20, weight: 500 },
          linewidth: 2.5,
          gridcolor: '#e0e0e0'
        },
        plot_bgcolor: 'white',
        paper_bgcolor: 'white',
      }, { responsive: true, displaylogo: false })
    },

    drawSpatialChart() {
      const spatialEl = this.$refs.spatialChart
      const data = this.spatialSliceData?.data
      if (!spatialEl || data == null) return

      if (!Array.isArray(data[0])) {
        const lineValues = Array.isArray(data) ? data : []
        Plotly.react(spatialEl, [{ type: 'scatter', mode: 'lines', x: lineValues.map((_, index) => index), y: lineValues, name: this.spatialPrimaryRunId, line: { width: 3 } }], {
          height: this.chartHeight,
          margin: { l: 110, r: 40, t: 40, b: 60 },
          xaxis: {
            title: { text: 'Index', font: { size: 24, weight: 600 } },
            tickfont: { size: 20, weight: 500 },
            linewidth: 2.5,
            gridcolor: '#e0e0e0'
          },
          yaxis: {
            title: { text: this.getSpatialValueLabel(), font: { size: 24, weight: 600 } },
            tickfont: { size: 20, weight: 500 },
            linewidth: 2.5,
            gridcolor: '#e0e0e0'
          },
          plot_bgcolor: 'white',
          paper_bgcolor: 'white',
        }, { responsive: true, displaylogo: false })
        return
      }

      Plotly.react(spatialEl, [{
        type: 'heatmap',
        z: data,
        colorscale: this.spatialMode === 'delta' ? 'RdBu' : 'Viridis',
        zmid: this.spatialMode === 'delta' ? 0 : undefined,
        colorbar: {
          title: { text: this.getSpatialValueLabel(), font: { size: 18, weight: 600 } },
          tickfont: { size: 16, weight: 500 }
        },
      }], {
        height: this.chartHeight,
        margin: { l: 110, r: 120, t: 40, b: 60 },
        xaxis: {
          title: { text: 'X', font: { size: 24, weight: 600 } },
          tickfont: { size: 20, weight: 500 },
          linewidth: 2.5,
          gridcolor: '#e0e0e0'
        },
        yaxis: {
          title: { text: 'Y', font: { size: 24, weight: 600 } },
          tickfont: { size: 20, weight: 500 },
          linewidth: 2.5,
          gridcolor: '#e0e0e0',
          automargin: true
        },
        plot_bgcolor: 'white',
        paper_bgcolor: 'white',
      }, { responsive: true, displaylogo: false })
    },

    drawQuantCharts() {
      const histEl = this.$refs.quantHistogram
      const sharesEl = this.$refs.quantShares
      if (!histEl || !sharesEl || !this.quantSummary?.runs) return

      const histTraces = this.selectedRunIds
        .map((runId) => {
          const run = this.quantSummary.runs[runId]
          if (!run?.histogram?.x?.length) return null
          const xValues = run.histogram.x.map((value) => Number(value))
          const yValues = run.histogram.y.map((value) => Number(value))
          const total = yValues.reduce((sum, value) => sum + (Number.isFinite(value) ? value : 0), 0)
          const percentages = total > 0 ? yValues.map((value) => value / total) : yValues.map(() => 0)
          return {
            type: 'bar',
            name: runId,
            x: xValues,
            y: percentages,
            opacity: 0.65,
            marker: {
              line: { width: 0 },
            },
            hovertemplate: '<b>%{fullData.name}</b><br>bin index: %{x}<br>percentage: %{y:.2%}<extra></extra>',
          }
        })
        .filter(Boolean)

      const labels = ['Unpred', 'Small', 'Medium', 'Large']
      const keys = ['unpred', 'small', 'medium', 'large']
      const shareTraces = this.selectedRunIds
        .map((runId) => {
          const shares = this.quantSummary.runs[runId]?.shares
          if (!shares) return null
          return {
            type: 'bar',
            name: runId,
            x: labels,
            y: keys.map((key) => shares[key]),
          }
        })
        .filter(Boolean)

      Plotly.react(histEl, histTraces, {
        height: this.chartHeight,
        margin: { l: 110, r: 40, t: 40, b: 60 },
        barmode: 'overlay',
        legend: { font: { size: 15, weight: 500 }, x: 1.02, xanchor: 'left', y: 1 },
        xaxis: {
          title: { text: 'Bin Index', font: { size: 24, weight: 600 } },
          zeroline: true,
          zerolinewidth: 2,
          zerolinecolor: '#6c757d',
          tickfont: { size: 20, weight: 500 },
          linewidth: 2.5,
          gridcolor: '#e0e0e0'
        },
        yaxis: {
          title: { text: 'Percentage', font: { size: 24, weight: 600 } },
          tickformat: '.0%',
          tickfont: { size: 20, weight: 500 },
          linewidth: 2.5,
          gridcolor: '#e0e0e0'
        },
        plot_bgcolor: 'white',
        paper_bgcolor: 'white',
      }, { responsive: true, displaylogo: false })

      Plotly.react(sharesEl, shareTraces, {
        height: this.chartHeight,
        margin: { l: 110, r: 40, t: 40, b: 60 },
        barmode: 'group',
        legend: { font: { size: 15, weight: 500 }, x: 1.02, xanchor: 'left', y: 1 },
        xaxis: {
          title: { text: 'Category', font: { size: 24, weight: 600 } },
          tickfont: { size: 20, weight: 500 },
          linewidth: 2.5,
          gridcolor: '#e0e0e0'
        },
        yaxis: {
          title: { text: 'Share', font: { size: 24, weight: 600 } },
          tickformat: '.0%',
          tickfont: { size: 20, weight: 500 },
          linewidth: 2.5,
          gridcolor: '#e0e0e0'
        },
        plot_bgcolor: 'white',
        paper_bgcolor: 'white',
      }, { responsive: true, displaylogo: false })
    },

    drawRuntimeChart() {
      const runtimeEl = this.$refs.runtimeChart
      if (!runtimeEl || !this.selectedRunIds.length) return
      const stages = [
        { key: 'prediction', label: 'prediction' },
        { key: 'quantization', label: 'quantization' },
        { key: 'encoder', label: 'encoder', value: (runId) => {
          const times = this.metricsByRun[runId]?.stage_time_seconds || {}
          return Number(times.encoder_setup || 0) + Number(times.encoder_encode || 0)
        } },
        { key: 'lossless', label: 'lossless' },
      ]
      const traces = stages.map((stage) => ({
        type: 'bar',
        name: stage.label,
        x: this.selectedRunIds,
        y: this.selectedRunIds.map((runId) => (typeof stage.value === 'function'
          ? stage.value(runId)
          : Number(this.metricsByRun[runId]?.stage_time_seconds?.[stage.key] || 0))),
      }))
      Plotly.react(runtimeEl, traces, {
        height: this.chartHeight,
        margin: { l: 110, r: 40, t: 40, b: 60 },
        barmode: 'stack',
        legend: { font: { size: 15, weight: 500 }, x: 1.02, xanchor: 'left', y: 1 },
        xaxis: {
          title: { text: 'Predictor', font: { size: 24, weight: 600 } },
          tickfont: { size: 20, weight: 500 },
          linewidth: 2.5,
          gridcolor: '#e0e0e0'
        },
        yaxis: {
          title: { text: 'Seconds', font: { size: 24, weight: 600 } },
          tickfont: { size: 20, weight: 500 },
          linewidth: 2.5,
          gridcolor: '#e0e0e0'
        },
        plot_bgcolor: 'white',
        paper_bgcolor: 'white',
      }, { responsive: true, displaylogo: false })
    },

    getSpatialValueLabel() {
      if (this.spatialMode === 'fallback') return 'Fallback'
      if (this.spatialMode === 'delta') return 'Δ |Residual|'
      if (this.spatialMode === 'signed') return 'Residual'
      return '|Residual|'
    },

    isVisible() {
      const pane = document.getElementById('case-study')
      return Boolean(pane && pane.classList.contains('active') && pane.classList.contains('show'))
    },

    resizePlots() {
      ['residualHistogram', 'residualCdf', 'spatialChart', 'quantHistogram', 'quantShares', 'runtimeChart'].forEach((refName) => {
        const element = this.$refs[refName]
        if (element) {
          try { Plotly.Plots.resize(element) } catch (_) { /* noop */ }
        }
      })
    },

    purgePlots() {
      ['residualHistogram', 'residualCdf', 'spatialChart', 'quantHistogram', 'quantShares', 'runtimeChart'].forEach((refName) => {
        const element = this.$refs[refName]
        if (element) {
          try { Plotly.purge(element) } catch (_) { /* noop */ }
        }
      })
    },

    formatDims(dims) {
      return Array.isArray(dims) && dims.length ? dims.join(' × ') : '—'
    },

    formatMetric(value) {
      if (value == null || Number.isNaN(Number(value))) return '—'
      const numeric = Number(value)
      if (Math.abs(numeric) >= 1000 || (Math.abs(numeric) > 0 && Math.abs(numeric) < 0.001)) return numeric.toExponential(3)
      return numeric.toFixed(4)
    },

    formatScientific(value) {
      if (value == null || Number.isNaN(Number(value))) return '—'
      return Number(value).toExponential(3)
    },

    formatSignedDelta(nextValue, prevValue, percent = false) {
      if (nextValue == null || prevValue == null || Number.isNaN(Number(nextValue)) || Number.isNaN(Number(prevValue))) return '—'
      const delta = Number(nextValue) - Number(prevValue)
      if (percent) return `${delta >= 0 ? '+' : ''}${(delta * 100).toFixed(2)}%`
      const numeric = Math.abs(delta) >= 1000 || (Math.abs(delta) > 0 && Math.abs(delta) < 0.001)
        ? delta.toExponential(3)
        : delta.toFixed(4)
      return delta >= 0 ? `+${numeric}` : numeric
    },


    notifyError(prefix, error) {
      const message = error?.response?.data?.error || error?.message || String(error)
      this.$store.commit('setStatus', {
        type: 'danger',
        message: `${prefix}. ${this.$maskDisplayPath(message)}`
      })
    },
  },
}
</script>

<style scoped>
.case-study-vis {
  background: #f8f9fb;
}

.plot {
  min-height: 290px;
}

.plot.tall {
  min-height: 430px;
}

.control-select {
  min-width: 132px;
}

.control-number {
  width: 88px;
}

.slice-range {
  width: 200px;
}
</style>
