
<script>
import { markRaw } from 'vue';
import axios from 'axios';
import InputDataset from '../InputDataset.vue';
import DataClipping from '../filter/DataClipping.vue';
import DataThresholdMask from '../filter/DataThresholdMask.vue';
import DataNormalization from '../filter/DataNormalization.vue';
import SZ3Pipeline from '../compressor/SZ3Pipeline.vue';
import ZFPConfig from '../compressor/ZFPConfig.vue';
import BaseCompressionModule from '../module/BaseCompressionModule.vue';
import CriticalPointsCorrection from '../correction/CriticalPointsCorrection.vue';
import FFCzCorrection from '../correction/FFCzCorrection.vue';
import { Splitpanes, Pane } from 'splitpanes';
import { NodeFactory } from '../../utils/nodeClasses';
import ConfigGraph from '../ConfigGraph.vue';

export default {
  name: 'DataFlowWorkbench',
  components: {
    InputDataset,
    DataClipping,
    DataThresholdMask,
    DataNormalization,
    SZ3Pipeline,
    ZFPConfig,
    BaseCompressionModule,
    CriticalPointsCorrection,
    Splitpanes,
    Pane,
    ConfigGraph
  },

  data() {
    return {
      // Filters imported from PipelineBrowser definitions
      availableFilters: [
        {
          id: 'clipping',
          label: 'Clip',
          description: 'Trim dataset extents prior to compression.',
          icon: 'bi-crop',
        },
        {
          id: 'threshold_mask',
          label: 'Threshold Mask',
          description: 'Mask data by replacing values outside your thresholds.',
          icon: 'bi-sliders',
        },
        {
          id: 'normalization',
          label: 'Normalize',
          description: 'Scale values into a custom range using min-max normalization.',
          icon: 'bi-arrows-expand',
        },
      ],
      // Modules imported from PipelineBrowser definitions
      availableModules: [
        {
          id: 'lorenzo',
          label: 'Lorenzo Predictor',
          description: 'Predictive stage that generates compact code streams and optional outlier paths.',
          icon: 'bi-activity',
          inputCount: 1,
          outputCount: 1,
        },
        {
          id: 'diff',
          label: 'Diff Encoder',
          description: 'Difference-codes a stage output stream for lower-entropy transport.',
          icon: 'bi-distribute-vertical',
          inputCount: 1,
          outputCount: 1,
        },
        {
          id: 'passthrough',
          label: 'Passthrough',
          description: 'Carries auxiliary streams such as outlier errors without transforming values.',
          icon: 'bi-arrow-left-right',
          inputCount: 1,
          outputCount: 1,
        },
      ],
      availableCompressors: [
        {
          id: 'sz3',
          label: 'SZ3 Compressor',
          description: 'A Modular Error-bounded Lossy Compression Framework.',
          icon: 'bi-cpu',
          architecture: 'modular'
        },
        {
          id: 'zfp',
          label: 'ZFP Compressor',
          description: 'Compress floating-point and integer arrays with high throughput.',
          icon: 'bi-cpu',
          architecture: 'parametric'
        },
      ],
      availableCorrections: [
        {
          id: 'morse_smale_correction',
          label: 'Morse-Smale Segmentation Correction',
          description: 'Apply fixes to correct critical points in the compressed data',
          icon: 'bi-bullseye',
        },
        {
          id: 'ffcz_correction',
          label: 'FFCz Frequency Correction',
          description: 'Correct frequency-domain errors with configurable spatial and frequency bounds',
          icon: 'bi-soundwave',
        },
      ],
      nodes: [],
      selectedNodeId: null,
      counters: { source: 0, filter: 0, module: 0, compressor: 0, correction: 0 },
      dragging: { active: false, nodeId: null, offsetX: 0, offsetY: 0 },
      // Map of filter types to component classes for pipeline replay
      filterComponents: new Map([
        ['clipping', DataClipping],
        ['threshold_mask', DataThresholdMask],
        ['normalization', DataNormalization],
      ]),
      paletteState: {
        filters: true,
        modules: true,
        compressors: true,
        corrections: true,
      },
      // Edges between nodes and connection state
      edges: [],
      connecting: {
        active: false,
        sourceNodeId: null,
        sourcePortId: null,
        mouseX: 0,
        mouseY: 0,
      },
      canvasSize: {
        width: 800,
        height: 600,
      },
      deleteConfirmation: {
        nodeId: null,
        nodeLabel: '',
      },
      showConfigGraph: false,
      showExploreModal: false,
      exploreNodeId: null,
      showPropertiesModal: false,
      cachedDataKeys: new Set(),
      cachingDataKeys: new Set(),
      splitResizeRaf: null,
    };
  },

  computed: {
    selectedNode() {
      return this.nodes.find(n => n.id === this.selectedNodeId) || null;
    },
    datasetToken() {
      return this.$store?.state?.dataset?.content || null;
    },
    datasetLoaded() {
      return Boolean(this.datasetToken);
    },
    datasetInfo() {
      const ds = this.$store?.state?.dataset || null;
      if (!ds) return null;
      return {
        name: ds.name || null,
        type: ds.type || null,
      };
    },
    showConfigGraphInPane() {
      return this.$store?.state?.showConfigGraphInPane || false;
    },
    baseConfigurations() {
      return this.$store?.state?.baseConfigurations || {};
    },
    derivedConfigurations() {
      return this.$store?.state?.derivedConfigurations || {};
    },
    savedConfigurations() {
      return this.$store?.state?.savedConfigurations || {};
    },
    compressorOptions() {
      return this.$store?.state?.compressorOptions || {};
    },
    comparisonData() {
      return this.$store?.state?.comparisonData || {};
    },
    exploreBaseConfig() {
      if (!this.exploreNodeId) return null;
      return this.baseConfigurations?.[this.exploreNodeId] || null;
    },
    exploreDerivedConfigs() {
      if (!this.exploreNodeId) return {};
      return this.derivedConfigurations?.[this.exploreNodeId] || {};
    },
    explorePlot() {
      const baseConfig = this.exploreBaseConfig;
      const derivedConfigs = this.exploreDerivedConfigs;
      if (!baseConfig) return null;

      const configs = [baseConfig, ...Object.values(derivedConfigs)];
      if (!configs.length) return null;

      const baseNode = this.nodes.find(n => n.id === this.exploreNodeId);
      const isSZ3 = baseNode?.definitionId === 'sz3';
      const moduleDefs = isSZ3 ? (baseNode?.modules || []) : [];
      const axisKeyMap = new Map();
      if (isSZ3 && moduleDefs.length) {
        moduleDefs.forEach(m => axisKeyMap.set(m.key, m.label || m.id));
      }

      const keys = new Set();
      configs.forEach(c => {
        const cc = c?.compressor_config || {};
        Object.keys(cc).forEach(k => keys.add(k));
      });
      const axes = isSZ3 && moduleDefs.length
        ? moduleDefs.map(m => m.key).filter(k => keys.has(k))
        : Array.from(keys).sort();
      if (!axes.length) return null;

      const valueTable = configs.map(c => {
        const cc = c?.compressor_config || {};
        return axes.map(k => cc[k]);
      });

      const axisMeta = axes.map((k, i) => {
        const values = valueTable.map(row => row[i]).filter(v => v !== undefined && v !== null);
        const allNumeric = values.every(v => typeof v === 'number' && Number.isFinite(v));
        const label = axisKeyMap.get(k) || k;
        const valueLabelMap = {};
        let optionLabels = [];
        let optionValues = [];
        if (isSZ3) {
          const moduleDef = moduleDefs.find(m => m.key === k);
          if (moduleDef) {
            const opts = this.getModuleOptionsForId('sz3', moduleDef.id) || [];
            opts.forEach(opt => {
              valueLabelMap[String(opt.value)] = opt.label;
            });
            optionLabels = opts.map(opt => opt.label);
            optionValues = opts.map(opt => opt.value);
          }
        }
        if (allNumeric) {
          const min = Math.min(...values);
          const max = Math.max(...values);
          return { key: k, label, type: 'number', min, max, valueLabelMap, optionLabels, optionValues };
        }
        const categories = Array.from(new Set(values.map(v => String(v))));
        return { key: k, label, type: 'category', categories, valueLabelMap, optionLabels, optionValues };
      });

      return {
        axes: axisMeta,
        values: valueTable,
      };
    },
  },

  watch: {
    datasetLoaded: {
      immediate: true,
      handler(loaded) {
        this.nodes.filter(n => n.type === 'source').forEach(n => {
          n.status = loaded ? 'ready' : 'empty';
        });
      }
    },
    datasetToken: {
      immediate: true,
      handler() {
        this.$nextTick(() => {
          this.ensureDatasetCached();
        });
      }
    },
    '$store.state.bulkGenerationRequests': {
      handler(requests) {
        if (requests && requests.length > 0) {
          requests.forEach(req => {
            if (req.type === 'error-bound') {
              this.handleErrorBoundBulkGeneration(req.payload);
            } else if (req.type === 'propagate') {
              this.handlePropagateParameter(req.payload);
            }
            this.$store.commit('clearBulkGenerationRequest', req.id);
          });
        }
      },
      deep: true
    },
    comparisonData: {
      deep: true,
      handler(newData) {
        if (!newData) return;
        // Auto-complete compressor nodes if their variants are finished in Config Graph
        this.nodes.forEach(node => {
          if (node.type === 'compressor' && node.status !== 'success' && node.status !== 'running') {
            const finishedConfig = this.getFinishedConfigResultForNode(node, newData);
            if (finishedConfig) {
              node.status = 'success';
              // Promote the first finished config result to be this node's last result
              // This activates downstream components (like correction)
              node.lastResult = {
                ...finishedConfig.result,
                base_name: finishedConfig.baseId
              };
              node.lastRunAt = Date.now();
            }
          }
        });
      }
    }
  },

  mounted() {
    window.addEventListener('mousemove', this.onMouseMove);
    window.addEventListener('mouseup', this.onMouseUp);
    window.addEventListener('resize', this.onWindowResize);
    this.$nextTick(() => {
      this.initializeCanvasSize();
    });
  },

  beforeUnmount() {
    window.removeEventListener('mousemove', this.onMouseMove);
    window.removeEventListener('mouseup', this.onMouseUp);
    window.removeEventListener('resize', this.onWindowResize);
  },

  methods: {
    resolveConfigBaseIdForNode(node) {
      if (!node) return null;

      const baseConfigurations = this.baseConfigurations || {};
      const derivedConfigurations = this.derivedConfigurations || {};
      const comparisonData = this.comparisonData || {};

      if (baseConfigurations[node.id] || derivedConfigurations[node.id]) {
        return node.id;
      }

      const currentResult = node.lastResult || comparisonData[node.id] || null;
      const explicitBase = currentResult?.base_name;
      if (explicitBase && (baseConfigurations[explicitBase] || derivedConfigurations[explicitBase])) {
        return explicitBase;
      }

      const containingBase = Object.keys(derivedConfigurations).find(baseName => derivedConfigurations[baseName]?.[node.id]);
      if (containingBase) return containingBase;

      const prefixedBase = Object.keys(baseConfigurations).find(baseName => node.id.startsWith(`${baseName}-`));
      if (prefixedBase) return prefixedBase;

      if (node.definitionId) {
        const matchingBases = Object.keys(baseConfigurations).filter(baseName => {
          return baseConfigurations[baseName]?.compressor_id === node.definitionId;
        });
        if (matchingBases.length === 1) {
          return matchingBases[0];
        }
      }

      return node.id;
    },
    getFinishedConfigResultForNode(node, resultMap = null) {
      if (!node) return null;

      const data = resultMap || this.comparisonData || {};
      const baseId = this.resolveConfigBaseIdForNode(node);
      if (!baseId) return null;

      const candidates = [baseId, ...Object.keys(this.derivedConfigurations?.[baseId] || {})];
      const finishedId = candidates.find(candidateId => data?.[candidateId] && !data[candidateId]?.error);
      if (!finishedId) return null;

      return {
        baseId,
        resultId: finishedId,
        result: data[finishedId]
      };
    },
    onSplitResize() {
      if (this.splitResizeRaf) return;
      this.splitResizeRaf = window.requestAnimationFrame(() => {
        this.splitResizeRaf = null;
        this.initializeCanvasSize();
        this.updateCanvasSize();
      });
    },

    async ensureDatasetCached() {
      const dataset = this.$store?.state?.dataset || null;
      if (!dataset || !dataset.content) return;
      let dataKey = dataset.data_key;
      if (!dataKey) {
        dataKey = crypto.randomUUID();
        this.$store.commit('setFileData', { dataset: { ...dataset, data_key: dataKey } });
      }
      if (this.cachedDataKeys.has(dataKey) || this.cachingDataKeys.has(dataKey)) return;
      this.cachingDataKeys.add(dataKey);
      const dimensions = dataset.dimensions || [dataset.width, dataset.height, dataset.depth]
        .filter(d => d && d !== '1' && d !== 1)
        .map(Number);
      const metadata = {
        precision: dataset.precision,
        dimensions,
        name: dataset.name,
        type: dataset.type,
      };
      try {
        const formData = new FormData();
        formData.append('data_key', dataKey);
        formData.append('metadata', JSON.stringify(metadata));
        const blob = new Blob([dataset.content], { type: 'application/octet-stream' });
        formData.append('data', blob, dataset.name || 'data.bin');
        await axios.post('/api/cache/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        this.cachedDataKeys.add(dataKey);
      } catch (err) {
        console.error('Failed to cache dataset:', err);
      } finally {
        this.cachingDataKeys.delete(dataKey);
      }
    },

    onWindowResize() {
      // Update canvas size when window is resized
      this.initializeCanvasSize();
      this.updateCanvasSize();
    },

    initializeCanvasSize() {
      // Calculate canvas size based on available pane space
      const paneEl = this.$refs.graphPane?.$el;
      if (!paneEl) return;

      const rect = paneEl.getBoundingClientRect();
      const availableWidth = Math.max(400, rect.width - 15);
      const availableHeight = Math.max(400, rect.height - 60);

      this.canvasSize.width = availableWidth;
      this.canvasSize.height = availableHeight;
    },
    canAddNodeType(type) {
      const nodeClass = NodeFactory.getClassByType(type);
      return nodeClass.canAdd(this.nodes);
    },
    clearSelection() {
      this.selectedNodeId = null;
      this.showPropertiesModal = false;
    },
    onDragStart(event, payload) {
      const type = typeof payload === 'string' ? payload : payload?.type;
      const id = typeof payload === 'string' ? null : payload?.id;
      event.dataTransfer.setData('operation/type', type || '');
      if (id) event.dataTransfer.setData('operation/id', id);
    },
    onCanvasDrop(event) {
      const typeRaw = event.dataTransfer.getData('operation/type');
      if (!typeRaw) return;

      // Validation check using OOP
      const nodeClass = NodeFactory.getClassByType(typeRaw);
      if (!nodeClass.canAdd(this.nodes)) {
        // You could also show a toast or a more subtle UI notification
        console.warn(`Cannot add ${typeRaw} node at this stage.`);
        return;
      }

      const defId = event.dataTransfer.getData('operation/id') || null;
      const rect = this.$refs.canvas?.getBoundingClientRect();
      const x = event.clientX - (rect?.left || 0);
      const y = event.clientY - (rect?.top || 0);
      this.addNode(typeRaw, x, y, defId);
    },
    addNode(type, x = 40, y = 40, defId = null) {
      let label = '';
      let icon = '';
      let description = '';
      let config = {}; // Module-specific configuration

      if (type === 'source') {
        this.counters.source += 1;
        label = 'Data Source';
        icon = 'bi-database';
      } else if (type === 'filter') {
        const def = this.availableFilters.find(f => f.id === defId);
        if (!def) return;
        this.counters.filter += 1;
        label = def.label;
        icon = def.icon || 'bi-funnel';
        description = def.description;
      } else if (type === 'module') {
        const def = this.availableModules.find(m => m.id === defId);
        if (!def) return;
        this.counters.module += 1;
        label = def.label;
        icon = def.icon || 'bi-puzzle';
        description = def.description;
        // Pass module-specific port configuration
        config = {
          inputCount: def.inputCount || 1,
          outputCount: def.outputCount || 1,
        };
      } else if (type === 'compressor') {
        const def = this.availableCompressors.find(c => c.id === defId);
        if (!def) return;
        this.counters.compressor += 1;
        label = def.label;
        icon = def.icon || 'bi-cpu';
        description = def.description;
        config = {
          architecture: def.architecture || 'parametric'
        };
      } else if (type === 'correction') {
        const def = this.availableCorrections.find(c => c.id === defId);
        if (!def) return;
        this.counters.correction += 1;
        label = def.label;
        icon = def.icon || 'bi-gear';
        description = def.description;
      }

  const id = `${defId || type}-${this.counters[type] || Date.now()}`;
      const node = NodeFactory.createNode(type, id, label, icon, defId, config);
      // Attach definition id and initial props to mimic PipelineBrowser config pane
      node.definitionId = defId;
      if (type === 'filter') {
        node.props = {
          filterName: label,
          filterType: `filter.${defId}`,
        };
      }

      // Center the node under the mouse (assuming ~200px width, ~80px height)
      node.x = Math.max(10, Math.round(x - 100));
      node.y = Math.max(10, Math.round(y - 40));
      node.description = description;

      if (type === 'source') {
        node.status = this.datasetLoaded ? 'ready' : 'empty';
        node.editorComponent = markRaw(InputDataset);
      } else if (type === 'filter') {
        if (defId === 'clipping') node.editorComponent = markRaw(DataClipping);
        else if (defId === 'threshold_mask') node.editorComponent = markRaw(DataThresholdMask);
        else if (defId === 'normalization') node.editorComponent = markRaw(DataNormalization);
        else node.editorComponent = null;
        node.status = 'pending';
      } else if (type === 'compressor') {
        if (defId === 'sz3') node.editorComponent = markRaw(SZ3Pipeline);
        else if (defId === 'zfp') node.editorComponent = markRaw(ZFPConfig);
        else node.editorComponent = null;
        node.status = 'pending';
      } else if (type === 'module') {
        node.editorComponent = markRaw(BaseCompressionModule);
        node.status = 'pending';
      } else if (type === 'correction') {
        if (defId === 'morse_smale_correction') node.editorComponent = markRaw(CriticalPointsCorrection);
        else if (defId === 'ffcz_correction') node.editorComponent = markRaw(FFCzCorrection);
        else node.editorComponent = null;
        node.status = 'pending';
      }

      this.nodes.push(node);
      this.selectedNodeId = id;
      this.$nextTick(() => {
        this.autoConnectNewNode(node);
        this.updateCanvasSize();
      });
    },
    promoteToConfigGraph(node) {
      if (node.type !== 'compressor') return;

      const config = {
        compressor_id: node.definitionId,
        compressor_config: {}
      };

      // Extract config from modules
      if (node.modules) {
        node.modules.forEach(m => {
          if (m.value && Object.keys(m.value).length) {
            const [label] = Object.keys(m.value);
            config.compressor_config[m.key] = m.value[label];
          }
        });
      }
      // Pull direct config for compressors like ZFP (no modules)
      if (node.definitionId === 'zfp' && node.config?.compressor_config) {
        config.compressor_config = { ...node.config.compressor_config };
      }
      // Merge node-level config (e.g., SZ3 error bound mode/value emitted by editor)
      if (node.config?.compressor_config) {
        config.compressor_config = {
          ...config.compressor_config,
          ...node.config.compressor_config,
        };
      }

      // Add error bound if present in node config or as defaults
      // For now, use some defaults if not found
      if (node.definitionId === 'sz3') {
        const mode = config.compressor_config['sz3:error_bound_mode_str'];
        if (!mode) {
          config.compressor_config['sz3:error_bound_mode_str'] = 'ABS';
        }
        const finalMode = config.compressor_config['sz3:error_bound_mode_str'];
        if (finalMode === 'REL') {
          delete config.compressor_config['sz3:abs_error_bound'];
          delete config.compressor_config['sz3:psnr_error_bound'];
          if (config.compressor_config['sz3:rel_error_bound'] === undefined) {
            config.compressor_config['sz3:rel_error_bound'] = 1e-3;
          }
        } else if (finalMode === 'PSNR') {
          delete config.compressor_config['sz3:abs_error_bound'];
          delete config.compressor_config['sz3:rel_error_bound'];
          if (config.compressor_config['sz3:psnr_error_bound'] === undefined) {
            config.compressor_config['sz3:psnr_error_bound'] = 1e-3;
          }
        } else {
          delete config.compressor_config['sz3:rel_error_bound'];
          delete config.compressor_config['sz3:psnr_error_bound'];
          if (config.compressor_config['sz3:abs_error_bound'] === undefined) {
            config.compressor_config['sz3:abs_error_bound'] = 1e-3;
          }
        }
      }

      config.early_config = {
        'pressio:metric': 'composite',
        'composite:plugins': ['time', 'size', 'error_stat'],
      };

      // Save to store
      this.$store.commit('addBaseConfiguration', { name: node.id, config });
      this.$store.commit('setShowConfigGraphInPane', true);
      this.$store.commit('setStatus', { type: 'success', message: `Node ${node.id} added to Config Graph.` });
    },

    handleErrorBoundBulkGeneration({ baseConfigName, parameter, values }) {
      const baseNode = this.nodes.find(n => n.id === baseConfigName);
      const baseConfig = this.baseConfigurations?.[baseConfigName];
      if (!baseConfig) {
        this.$store.commit('setStatus', { type: 'danger', message: 'Base configuration not found.' });
        return;
      }

      const baseSlug = String(baseConfigName).replace(/[^a-zA-Z0-9_-]/g, '_');
      const existing = Object.keys(this.derivedConfigurations?.[baseConfigName] || {});

      values.forEach((val, index) => {
        // Store this derived config in the store as well for the ConfigGraph to see
        const derivedConfig = JSON.parse(JSON.stringify(baseConfig));
        if (!derivedConfig.compressor_config) derivedConfig.compressor_config = {};
        this.ensureConfigDatasetFields(derivedConfig);
        derivedConfig.compressor_config[parameter] = val;

        // Format value for filename
        const valStr = this.formatValueForFilename(val);
        let derivedName = `${baseSlug}-eb-${valStr}`;

        // Handle duplicates by adding a counter
        if (existing.includes(derivedName) || values.slice(0, index).some((v) => {
          return this.formatValueForFilename(v) === valStr;
        })) {
          let counter = 2;
          while (existing.includes(`${derivedName}-${counter}`)) {
            counter++;
          }
          derivedName = `${derivedName}-${counter}`;
        }

        this.$store.commit('addDerivedConfiguration', {
          baseName: baseConfigName,
          derivedName,
          config: derivedConfig
        });
      });

      const label = baseNode?.label || baseConfigName;
      this.$store.commit('setStatus', { type: 'success', message: `Generated ${values.length} variants for ${label}.` });
    },
    handleCombinatorialGeneration(payload) {
      if (!this.selectedNode || this.selectedNode.type !== 'compressor') return;
      const baseConfig = payload?.baseConfig || null;
      const configs = Array.isArray(payload?.configs) ? payload.configs : [];
      if (!baseConfig || configs.length === 0) {
        this.$store.commit('setStatus', { type: 'warning', message: 'No configurations generated. Check your selections.' });
        return;
      }
      const basePrefix = this.selectedNode.definitionId || 'compressor';
      const existing = Object.keys(this.baseConfigurations || {}).filter(name => name.startsWith(`${basePrefix}-combo-`));
      let nextIndex = existing
        .map(name => {
          const match = name.match(/-combo-(\d+)$/);
          return match ? Number(match[1]) : -1;
        })
        .reduce((max, v) => Math.max(max, v), -1) + 1;
      configs.forEach((config, index) => {
        const baseName = `${basePrefix}-combo-${nextIndex + index}`;
        this.ensureConfigDatasetFields(config);
        this.$store.commit('addBaseConfiguration', { name: baseName, config });
      });

      this.$store.commit('setShowConfigGraphInPane', true);
      this.$store.commit('setStatus', { type: 'success', message: `Generated ${configs.length} base configurations from ${this.selectedNode.label}.` });
    },
    ensureConfigDatasetFields(config) {
      if (!config) return;
      const dataset = this.$store.state.dataset || {};
      if (!config.data_key) {
        const existingKey = dataset.data_key || dataset.name || null;
        if (existingKey) {
          config.data_key = existingKey;
        } else if (dataset.content) {
          const newKey = crypto.randomUUID();
          config.data_key = newKey;
          this.$store.commit('setFileData', { dataset: { ...dataset, data_key: newKey } });
        }
      }
      const dims = dataset.dimensions || [dataset.width, dataset.height, dataset.depth]
        .filter(d => d && d !== '1' && d !== 1)
        .map(Number);
      if (!config.dataset_meta) {
        config.dataset_meta = {
          name: dataset.name || null,
          dimensions: dims.length ? dims : null,
          precision: dataset.precision || null,
          endianness: dataset.endianness || 'little',
        };
      } else {
        if (!config.dataset_meta.name && dataset.name) config.dataset_meta.name = dataset.name;
        if (!config.dataset_meta.dimensions && dims.length) config.dataset_meta.dimensions = dims;
        if (!config.dataset_meta.precision && dataset.precision) config.dataset_meta.precision = dataset.precision;
        if (!config.dataset_meta.endianness && dataset.endianness) config.dataset_meta.endianness = dataset.endianness;
      }
    },
    openExploreModal(node) {
      if (!node || node.type !== 'compressor') return;
      const hasBase = Boolean(this.baseConfigurations?.[node.id]);
      if (!hasBase) {
        this.$store.commit('setStatus', { type: 'warning', message: 'No saved base configuration for this compressor yet.' });
        return;
      }
      this.exploreNodeId = node.id;
      this.showExploreModal = true;
    },
    closeExploreModal() {
      this.showExploreModal = false;
      this.exploreNodeId = null;
    },
    exploreAxisX(index, width, padding) {
      const count = this.explorePlot?.axes?.length || 1;
      if (count <= 1) return padding;
      const span = width - padding * 2;
      return padding + (span * index) / (count - 1);
    },
    exploreValueY(axis, value, height, padding) {
      if (value === undefined || value === null) return height - padding;
      const span = height - padding * 2;
      if (axis.type === 'number') {
        if (axis.max === axis.min) return padding + span / 2;
        const t = (Number(value) - axis.min) / (axis.max - axis.min);
        return height - padding - t * span;
      }
      const idx = axis.categories.indexOf(String(value));
      if (idx < 0) return height - padding;
      if (axis.categories.length <= 1) return padding + span / 2;
      const t = idx / (axis.categories.length - 1);
      return height - padding - t * span;
    },
    explorePathForRow(row, width, height, padding) {
      const axes = this.explorePlot?.axes || [];
      const points = axes.map((axis, i) => {
        const x = this.exploreAxisX(i, width, padding);
        const y = this.exploreValueY(axis, row[i], height, padding);
        return `${x},${y}`;
      });
      return `M ${points.join(' L ')}`;
    },
    exploreOptionY(axis, index, height, padding) {
      const span = height - padding * 2;
      const count = axis?.optionLabels?.length || 0;
      if (count <= 1) return padding + span / 2;
      const t = index / (count - 1);
      return height - padding - t * span;
    },
    formatExploreValue(axis, value) {
      if (value === undefined || value === null) return '—';
      const mapped = axis?.valueLabelMap?.[String(value)];
      if (mapped) return mapped;
      if (axis?.type === 'number') {
        const num = Number(value);
        if (!Number.isFinite(num)) return String(value);
        const abs = Math.abs(num);
        if (abs > 0 && abs < 1e-3) return num.toExponential(2);
        if (abs >= 1e4) return num.toExponential(2);
        return num.toPrecision(3);
      }
      return String(value);
    },

    formatValueForFilename(value) {
      if (typeof value === 'number') {
        const num = Number(value);
        if (!Number.isFinite(num)) return String(value).replace(/[^a-zA-Z0-9_-]/g, '_');
        const abs = Math.abs(num);
        // Use exponential notation for very small or very large numbers
        if (abs > 0 && abs < 1e-4) {
          return num.toExponential(1).replace(/[+]/g, '');
        }
        if (abs >= 1e4) {
          return num.toExponential(1).replace(/[+]/g, '');
        }
        // For regular numbers, use a reasonable precision
        // Remove trailing zeros and decimal point if not needed
        let str = num.toPrecision(4);
        str = parseFloat(str).toString();
        return str;
      }
      return String(value).replace(/[^a-zA-Z0-9_-]/g, '_');
    },

    handlePropagateParameter({ baseNodeId, parameter, values }) {
      const baseNode = this.nodes.find(n => n.id === baseNodeId);
      const baseConfig = this.baseConfigurations?.[baseNodeId];
      if (!baseConfig) {
        this.$store.commit('setStatus', { type: 'danger', message: 'Base configuration not found.' });
        return;
      }
      const baseSlug = String(baseNodeId).replace(/[^a-zA-Z0-9_-]/g, '_');
      const existing = Object.keys(this.derivedConfigurations?.[baseNodeId] || {});

      // Check if this is an error bound or accuracy parameter
      const isErrorBound = parameter.includes('error_bound') || parameter === 'zfp:accuracy';

      values.forEach((val, index) => {
        const derivedConfig = JSON.parse(JSON.stringify(baseConfig));
        if (!derivedConfig.compressor_config) derivedConfig.compressor_config = {};
        this.ensureConfigDatasetFields(derivedConfig);
        derivedConfig.compressor_config[parameter] = val;

        // Generate name based on whether it's an error bound
        let derivedName;
        if (isErrorBound) {
          // Format value for filename
          const valStr = this.formatValueForFilename(val);
          derivedName = `${baseSlug}-eb-${valStr}`;

          // Handle duplicates by adding a counter
          if (existing.includes(derivedName) || values.slice(0, index).some((v) => {
            return this.formatValueForFilename(v) === valStr;
          })) {
            let counter = 2;
            while (existing.includes(`${derivedName}-${counter}`)) {
              counter++;
            }
            derivedName = `${derivedName}-${counter}`;
          }
        } else {
          // Use parameter-based naming for non-error-bound parameters
          const paramSlug = String(parameter)
            .split(':')
            .pop()
            .replace(/[^a-zA-Z0-9_-]/g, '_')
            .toLowerCase();
          let nextIndex = existing
            .map(name => {
              const match = name.match(/-prop-(\d+)$/);
              return match ? Number(match[1]) : -1;
            })
            .reduce((max, v) => Math.max(max, v), -1) + 1;
          derivedName = `${baseSlug}-${paramSlug}-${nextIndex + index}`;
        }

        this.$store.commit('addDerivedConfiguration', {
          baseName: baseNodeId,
          derivedName,
          config: derivedConfig
        });
      });
      this.$store.commit('setStatus', { type: 'success', message: `Generated ${values.length} variants for ${baseNode?.label || baseNodeId}.` });
    },
    handleExploreStateChanged(nodeId, state) {
      const node = this.nodes.find(n => n.id === nodeId);
      if (!node) return;
      const next = JSON.parse(JSON.stringify(state));
      const prev = node.exploreState ? JSON.stringify(node.exploreState) : null;
      const nextStr = JSON.stringify(next);
      if (prev === nextStr) return;
      node.exploreState = next;
    },
    onNodeConfigChange(payload) {
      if (this.selectedNode) {
        // Sync the component's output back to the node's config
        this.selectedNode.config = { ...this.selectedNode.config, ...payload };
        console.log(`Node ${this.selectedNode.id} config updated:`, this.selectedNode.config);
      }
    },
    getVariantCount(node) {
      if (!node || node.type !== 'compressor') return 0;
      const derived = this.derivedConfigurations?.[node.id] || null;
      return derived ? Object.keys(derived).length : 0;
    },
    getVariantDots(count) {
      const maxDots = 6;
      return Math.min(maxDots, Math.max(0, Number(count || 0)));
    },
    // Status helpers and event handlers to mirror PipelineBrowser behavior
    setNodeStatus(nodeId, status, message) {
      const node = this.nodes.find(n => n.id === nodeId);
      if (!node) return;
      node.status = status || 'pending';
      if (message !== undefined) node.statusMessage = message;
      if (status !== 'error') node.lastError = null;
    },
    handleFilterStart(nodeId) {
      this.setNodeStatus(nodeId, 'running', 'Applying filter...');
    },
    handleFilterSuccess(nodeId, payload) {
      const node = this.nodes.find(n => n.id === nodeId);
      if (!node) return;

      const result = payload?.result || payload || null;
      const context = payload?.context || null;

      node.lastResult = result;
      node.lastRunContext = context;
      node.lastRunAt = Date.now();

      let message = 'Filter applied successfully.';
      if (result?.dimensions && Array.isArray(result.dimensions)) {
        message = `Output dimensions ${result.dimensions.join('×')}.`;
      }
      this.setNodeStatus(nodeId, 'success', message);

      // Propagate reset to downstream nodes since data has changed
      this.resetDownstreamNodes(nodeId);
    },
    flattenNumericField(field) {
      if (field == null) return null;
      if (ArrayBuffer.isView(field)) return Array.from(field).map(v => Number(v));
      if (!Array.isArray(field)) return null;
      return field.flat(Infinity).map(v => Number(v));
    },
    normalizeSegmentation(segmentation, dimensionsHint = null) {
      if (!segmentation || typeof segmentation !== 'object') return null;

      const dims = segmentation.dimensions || {};
      const hinted = Array.isArray(dimensionsHint) ? dimensionsHint.map(Number) : null;
      const width = Number(dims.width || hinted?.[0] || 0);
      const height = Number(dims.height || hinted?.[1] || 0);
      const depth = Number(dims.depth || hinted?.[2] || 1);
      if (!width || !height || !depth) return null;

      const total = width * height * depth;
      const result = {
        dimensions: { width, height, depth },
      };
      ['ascending', 'descending', 'morse_smale'].forEach(key => {
        const flattened = this.flattenNumericField(segmentation[key]);
        if (Array.isArray(flattened) && flattened.length === total) {
          result[key] = flattened;
        }
      });
      if (!result.ascending && !result.descending && !result.morse_smale) {
        return null;
      }
      if (segmentation.metadata && typeof segmentation.metadata === 'object') {
        result.metadata = segmentation.metadata;
      }
      return result;
    },
    extractDimensionsFromResult(result) {
      if (!result) return null;
      if (Array.isArray(result.dimensions)) return result.dimensions;
      if (Array.isArray(result.meta?.dimensions)) return result.meta.dimensions;
      const ds = this.$store?.state?.dataset;
      if (ds?.width && ds?.height) {
        return [Number(ds.width), Number(ds.height), Number(ds.depth || 1)];
      }
      return null;
    },
    hasManifoldData(result) {
      const seg = result?.segmentation;
      if (!seg) return false;
      return ['ascending', 'descending', 'morse_smale'].some(k => Array.isArray(seg[k]) && seg[k].length > 0);
    },
    handleCorrectionSuccess(payload) {
      const nodeId = payload?.nodeId || this.selectedNode?.id;
      if (!nodeId) return;

      const sourceEdge = this.edges.find(e => e.to.nodeId === nodeId && e.to.portId === 'in-0');
      const sourceNodeId = sourceEdge?.from?.nodeId || null;
      const baseKey = sourceNodeId ? `${sourceNodeId}-corrected` : `${nodeId}-corrected`;
      const node = this.nodes.find(n => n.id === nodeId);
      let correctedKey = node?.correctedKey || baseKey;
      if (node && node.correctedKey && node.correctedKey !== baseKey) {
        this.$store.commit('removeComparisonData', node.correctedKey);
        correctedKey = baseKey;
      }

      const rawResult = payload?.result || null;
      if (!rawResult) {
        this.handleFilterSuccess(nodeId, payload);
        return;
      }

      const dims = this.extractDimensionsFromResult(rawResult);
      const normalizedSegmentation = this.normalizeSegmentation(
        rawResult.segmentation || rawResult.critical_points?.segmentation,
        dims
      );

      const result = { ...rawResult };
      if (normalizedSegmentation) {
        result.segmentation = normalizedSegmentation;
        this.$store.commit('setSegmentation', { source: correctedKey, data: normalizedSegmentation });
      }

      const cpPayload = rawResult.critical_points || (rawResult.type === 'critical_points' ? rawResult : null);
      if (cpPayload) {
        this.$store.commit('setCriticalPoints', { source: correctedKey, data: cpPayload });
      }

      this.handleFilterSuccess(nodeId, { ...payload, result });
      if (node) node.correctedKey = correctedKey;
      result.corrected_from = sourceNodeId;
      this.$store.commit('setComparisonData', { [correctedKey]: result });
    },
    handleFilterError(nodeId, payload) {
      const node = this.nodes.find(n => n.id === nodeId);
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
      const node = this.nodes.find(n => n.id === nodeId);
      if (!node) return;
      if (node.status === 'running') {
        this.setNodeStatus(nodeId, 'pending', 'Review the output or run again.');
      }
    },
    handleFilterDatasetChange(nodeId) {
      const node = this.nodes.find(n => n.id === nodeId);
      if (!node || node.status === 'running') return;
      this.setNodeStatus(nodeId, 'stale', 'Dataset changed. Re-run to refresh results.');
    },
    /**
     * Example method to validate a connection between two nodes.
     * This would be called when a user tries to draw an edge.
     */
    validateConnection(sourceNodeId, targetNodeId) {
      const source = this.nodes.find(n => n.id === sourceNodeId);
      const target = this.nodes.find(n => n.id === targetNodeId);
      if (!source || !target) return false;

      // Prevent self-connections
      if (sourceNodeId === targetNodeId) return false;

      return source.canConnectTo(target);
    },
    selectNode(nodeId) {
      this.selectedNodeId = nodeId;
    },
    openPropertiesModal(nodeId) {
      this.selectedNodeId = nodeId;
      this.showPropertiesModal = true;
    },
    closePropertiesModal() {
      this.showPropertiesModal = false;
    },
    resetDownstreamNodes(nodeId) {
      // Find all nodes that depend on this node (directly or indirectly)
      const directDownstreamIds = this.edges
        .filter(e => e.from.nodeId === nodeId)
        .map(e => e.to.nodeId);

      directDownstreamIds.forEach(childId => {
        const childNode = this.nodes.find(n => n.id === childId);
        if (childNode) {
          childNode.status = 'pending';
          childNode.lastResult = null;
          childNode.lastError = null;
          if (this.$store) {
            this.$store.commit('removeComparisonData', childId);
          }
          this.resetDownstreamNodes(childId); // Recursive reset
        }
      });
    },
    removeNode(nodeId) {
      const idx = this.nodes.findIndex(n => n.id === nodeId);
      if (idx === -1) return;
      const node = this.nodes[idx];

      // Show confirmation modal
      this.deleteConfirmation.nodeId = nodeId;
      this.deleteConfirmation.nodeLabel = node.label;
      this.deleteConfirmation.show = true;
    },
    confirmRemoveNode() {
      const nodeId = this.deleteConfirmation.nodeId;
      if (!nodeId) return;

      const idx = this.nodes.findIndex(n => n.id === nodeId);
      if (idx === -1) {
        this.deleteConfirmation.show = false;
        return;
      }
      const node = this.nodes[idx];

      const configBaseId = node.type === 'compressor'
        ? this.resolveConfigBaseIdForNode(node)
        : null;

      // Perform node-specific cleanup/reverse operations
      node.onDestroy({
        store: this.$store,
        filterComponents: this.filterComponents,
      });

      if (configBaseId && (this.baseConfigurations?.[configBaseId] || this.derivedConfigurations?.[configBaseId])) {
        this.$store.commit('removeConfigurationBranch', configBaseId);
      }

      // Invalidate and reset all downstream nodes before removing edges
      this.resetDownstreamNodes(nodeId);

      const wasSelected = this.selectedNodeId === nodeId;
      this.nodes.splice(idx, 1);
      // Remove any edges connected to this node
      this.edges = this.edges.filter(e => e.from.nodeId !== nodeId && e.to.nodeId !== nodeId);
      if (this.connecting.active && this.connecting.sourceNodeId === nodeId) {
        this.cancelConnection();
      }
      if (wasSelected) this.selectedNodeId = null;

      // Close modal
      this.deleteConfirmation.show = false;
      this.deleteConfirmation.nodeId = null;
      this.deleteConfirmation.nodeLabel = '';
    },
    cancelRemoveNode() {
      this.deleteConfirmation.show = false;
      this.deleteConfirmation.nodeId = null;
      this.deleteConfirmation.nodeLabel = '';
    },
    startDrag(node, event) {
      // If interacting with a port, do not initiate node dragging
      if (event.target && event.target.closest && event.target.closest('.port')) {
        return;
      }
      const rect = event.currentTarget.getBoundingClientRect();
      this.dragging.active = true;
      this.dragging.nodeId = node.id;
      this.dragging.offsetX = event.clientX - rect.left;
      this.dragging.offsetY = event.clientY - rect.top;
    },
    onMouseMove(event) {
      if (this.connecting.active) {
        this.updateTempConnectionMouse(event);
      }

      if (!this.dragging.active) return;
      const canvasRect = this.$refs.canvas?.getBoundingClientRect();
      const node = this.nodes.find(n => n.id === this.dragging.nodeId);
      if (!node || !canvasRect) return;

      // Calculate new position relative to canvas
      let newX = event.clientX - canvasRect.left - this.dragging.offsetX;
      let newY = event.clientY - canvasRect.top - this.dragging.offsetY;

      node.x = Math.max(0, newX);
      node.y = Math.max(0, newY);
      this.updateCanvasSize();
    },
    onMouseUp() {
      this.dragging.active = false;
      this.dragging.nodeId = null;
      if (this.connecting.active) {
        this.cancelConnection();
      }
    },
    // Connection helpers
    beginConnection(node, port) {
      // Start connecting from an output port
      this.connecting.active = true;
      this.connecting.sourceNodeId = node.id;
      this.connecting.sourcePortId = port.id;
      const p = this.getPortPosition(node.id, port.id, 'output');
      this.connecting.mouseX = p.x;
      this.connecting.mouseY = p.y;
    },
    completeConnection(targetNode, targetPort) {
      if (!this.connecting.active) return;
      const sourceNodeId = this.connecting.sourceNodeId;
      const sourcePortId = this.connecting.sourcePortId;
      const targetNodeId = targetNode.id;
      const targetPortId = targetPort.id;
      if (this.validateConnection(sourceNodeId, targetNodeId)) {
        // Reset the target node and its descendants since the input is changing
        this.resetDownstreamNodes(targetNodeId);
        targetNode.status = 'pending';
        targetNode.lastResult = null;
        if (this.$store) {
          this.$store.commit('removeComparisonData', targetNodeId);
        }

        this.edges = this.edges.filter(e =>
          !(e.to.nodeId === targetNodeId && e.to.portId === targetPortId)
        );
        this.addEdge(sourceNodeId, sourcePortId, targetNodeId, targetPortId);
      }
      this.cancelConnection();
    },
    cancelConnection() {
      this.connecting.active = false;
      this.connecting.sourceNodeId = null;
      this.connecting.sourcePortId = null;
    },
    addEdge(sourceNodeId, sourcePortId, targetNodeId, targetPortId) {
      const exists = this.edges.some(e => e.from.nodeId === sourceNodeId && e.from.portId === sourcePortId && e.to.nodeId === targetNodeId && e.to.portId === targetPortId);
      if (exists) return;
      this.edges.push({
        from: { nodeId: sourceNodeId, portId: sourcePortId },
        to: { nodeId: targetNodeId, portId: targetPortId },
      });
    },
    updateTempConnectionMouse(event) {
      const canvasRect = this.$refs.canvas?.getBoundingClientRect();
      if (!canvasRect) return;
      this.connecting.mouseX = event.clientX - canvasRect.left;
      this.connecting.mouseY = event.clientY - canvasRect.top;
    },
    getPortPosition(nodeId, portId, side) {
      // side: 'input' | 'output'
      const canvasRect = this.$refs.canvas?.getBoundingClientRect();
      const el = this.$el.querySelector(`[data-node-id="${nodeId}"] .port[data-port-side="${side}"][data-port-id="${portId}"]`);
      if (!el || !canvasRect) {
        const nodeEl = this.$el.querySelector(`[data-node-id="${nodeId}"]`);
        const rect = nodeEl?.getBoundingClientRect() || null;
        return {
          x: rect ? rect.left - (canvasRect?.left || 0) + rect.width / 2 : 0,
          y: rect ? rect.top - (canvasRect?.top || 0) + rect.height / 2 : 0,
        };
      }
      const r = el.getBoundingClientRect();
      return {
        x: r.left - canvasRect.left + r.width / 2,
        y: r.top - canvasRect.top + r.height / 2,
      };
    },
    autoConnectNewNode(newNode) {
      const candidates = this.nodes.filter(n => n.id !== newNode.id && Array.isArray(n.outputs) && n.outputs.length && this.validateConnection(n.id, newNode.id));
      if (!candidates.length) return;
      const closest = candidates.reduce((best, n) => {
        const dx = (n.x || 0) - (newNode.x || 0);
        const dy = (n.y || 0) - (newNode.y || 0);
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (!best || dist < best.dist) return { node: n, dist };
        return best;
      }, null);
      const src = closest?.node;
      if (!src) return;
      const sourcePortId = src.outputs[0]?.id;
      const targetPortId = newNode.inputs[0]?.id;
      if (sourcePortId && targetPortId) {
        this.addEdge(src.id, sourcePortId, newNode.id, targetPortId);
      }
    },
    getStatusLabel(status) {
      const textMap = {
        ready: 'Ready',
        success: 'Completed',
        running: 'Running',
        error: 'Error',
        pending: 'Pending',
        stale: 'Stale',
        invalid: 'Needs Attention',
        empty: 'No Data',
      };
      return textMap[status] || 'Idle';
    },
    getStatusBadgeClass(status) {
      const classMap = {
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
      return classMap[status] || 'bg-secondary';
    },
    // Compressor pipeline updates
    handlePipelineModulesUpdated(mods) {
      if (!this.selectedNode || this.selectedNode.type !== 'compressor') return;

      // Only update timestamp if modules actually changed
      const hasChanged = !this.selectedNode.modules ||
        JSON.stringify(this.selectedNode.modules) !== JSON.stringify(mods);

      this.selectedNode.modules = mods;
      if (hasChanged) {
        this.selectedNode.lastUpdatedAt = Date.now();
      }

      const ready = mods && mods.every(m => m?.value && Object.keys(m.value).length);
      this.selectedNode.status = ready ? 'ready' : 'pending';
    },
    async computeDataKey() {
      return crypto.randomUUID();
    },
    async handleRunCompressor(config) {
      if (!this.selectedNode || this.selectedNode.type !== 'compressor') return;

      const nodeId = this.selectedNode.id;
      this.setNodeStatus(nodeId, 'running', 'Compressing the data...');

      try {
        // Data flow:
        // 1. If compressor is connected to a filter node, use the filtered data from the store
        //    (filters update the global store when they complete)
        // 2. Otherwise, use the original dataset from the store
        // The config already contains dataset_meta from this.$store.state.dataset,
        // which is updated by filters, so we ensure we're using the correct data

        const datasetToUse = this.$store.state.dataset?.content;
        let dataKeyToUse = config.data_key;

        // Ensure we have a data_key if possible
        if (!dataKeyToUse && datasetToUse) {
          const newKey = await this.computeDataKey();
          dataKeyToUse = newKey;
          this.$store.commit('setFileData', {
            dataset: { ...this.$store.state.dataset, data_key: newKey }
          });
        }

        // Update config with correct data key
        // (dataset_meta is already correct from the store)
        config.data_key = dataKeyToUse;

        const executeCompression = async (conf) => {
          const formData = new FormData();
          formData.append("get_options", 0);
          formData.append("configurations", JSON.stringify({ [nodeId]: conf }));
          return await axios.post('/api/indexlist', formData);
        };

        let response;
        try {
          response = await executeCompression(config);
        } catch (err) {
          const serverMsg = err?.response?.data?.error;
          // If data is missing from backend cache (404), upload it and retry
          if (err?.response?.status === 404 && serverMsg?.includes('DATA_KEY_NOT_FOUND') && datasetToUse) {
            this.setNodeStatus(nodeId, 'running', 'Uploading data to server cache...');

            const uploadForm = new FormData();
            uploadForm.append('metric_type', 'statistics'); // Dummy metric to trigger cache storage
            uploadForm.append('parameters', JSON.stringify({
              dimensions: config.dataset_meta.dimensions,
              precision: config.dataset_meta.precision,
              endianness: config.dataset_meta.endianness
            }));
            uploadForm.append('data_key', config.data_key);
            const blob = new Blob([datasetToUse], { type: 'application/octet-stream' });
            uploadForm.append('data', blob, config.dataset_meta.name || 'data.bin');

            await axios.post('/api/analysis/compute/upload', uploadForm);

            // Retry compression
            this.setNodeStatus(nodeId, 'running', 'Compressing the data...');
            response = await executeCompression(config);
          } else {
            throw err;
          }
        }

        const nodeResult = response.data[nodeId];

        // Final guard: check if node still exists and is the same type
        const finalNode = this.nodes.find(n => n.id === nodeId);
        if (!finalNode) {
          console.warn(`Node ${nodeId} no longer exists, discarding results.`);
          return;
        }

        if (nodeResult.error) {
          this.setNodeStatus(nodeId, 'error', nodeResult.error);
        } else {
          // Fetch the actual decompressed binary data using the data_key
          if (nodeResult.data_key) {
            try {
              const dataResp = await axios.get(`/api/decompressed/${nodeResult.data_key}`, {
                responseType: 'arraybuffer'
              });
              nodeResult.decp_data = dataResp.data;
            } catch (err) {
              console.error('Failed to fetch decompressed data:', err);
            }
          }

          this.setNodeStatus(nodeId, 'success', 'Compression completed.');
          finalNode.lastResult = nodeResult;
          finalNode.lastRunAt = Date.now();

          if (this.$store) {
            this.$store.commit('setComparisonData', { [nodeId]: nodeResult });
          }
        }
      } catch (error) {
        console.error('Error running compressor:', error);
        const msg = error.response?.data?.error || error.message;
        this.setNodeStatus(nodeId, 'error', msg);
      }
    },
    toggleCompressorExpansion(nodeId) {
      const node = this.nodes.find(n => n.id === nodeId);
      if (!node || node.type !== 'compressor') return;
      node.expanded = !node.expanded;
      if (!node.expanded) {
        // Clear module selection when collapsing
        node.selectedModuleIdx = null;
      }
      // Recalculate canvas size after expansion state changes
      this.$nextTick(() => {
        this.updateCanvasSize();
      });
    },
    selectCompressorModule(nodeId, moduleIdx) {
      const node = this.nodes.find(n => n.id === nodeId);
      if (!node || node.type !== 'compressor') return;

      // Toggle selection: if same module clicked, deselect
      if (node.selectedModuleIdx === moduleIdx) {
        node.selectedModuleIdx = null;
      } else {
        node.selectedModuleIdx = moduleIdx;
        // Ensure node is selected too
        this.selectedNodeId = nodeId;
      }
    },
    onModuleDragOver(nodeId, moduleIdx, moduleId, event) {
      // Check if the dragged option matches this module
      const draggedModuleId = event.dataTransfer.getData('module-id');
      if (draggedModuleId && draggedModuleId !== moduleId) {
        event.dataTransfer.dropEffect = 'none';
        event.currentTarget.style.cursor = 'not-allowed';
      } else {
        event.dataTransfer.dropEffect = 'copy';
        event.currentTarget.style.cursor = 'copy';
      }
    },
    onModuleDragLeave(event) {
      event.currentTarget.style.cursor = 'pointer';
    },
    onModuleDrop(nodeId, moduleIdx, moduleId, event) {
      const node = this.nodes.find(n => n.id === nodeId);
      if (!node || node.type !== 'compressor') return;

      // Get the dragged option data
      const optionLabel = event.dataTransfer.getData('text/plain');
      const draggedModuleId = event.dataTransfer.getData('module-id');

      if (!optionLabel || draggedModuleId !== moduleId) {
        event.currentTarget.style.cursor = 'pointer';
        return;
      }

      // Find the option value from the component's data
      // We need to get this from the SZ3Pipeline component
      // For now, we'll emit an event that the component can handle
      if (this.selectedNode && this.selectedNode.editorComponent) {
        // Update the module value directly
        const module = node.modules[moduleIdx];
        if (module && module.id === moduleId) {
          // We need to get the actual option value
          // This is a simplified version - in production you'd look it up properly
          const moduleOptions = this.getModuleOptionsForId(node.definitionId, moduleId);
          const option = moduleOptions?.find(opt => opt.label === optionLabel);

          if (option && option.state !== 'unavailable') {
            module.value = { [optionLabel]: option.value };
            node.lastUpdatedAt = Date.now();

            // Check if all modules are configured
            const ready = node.modules.every(m => m?.value && Object.keys(m.value).length);
            node.status = ready ? 'ready' : 'pending';
          }
        }
      }

      event.currentTarget.style.cursor = 'pointer';
    },
    getModuleOptionsForId(compressorId, moduleId) {
      // Return the options for a specific module based on compressor type
      // This is hardcoded for SZ3 but should be made dynamic for extensibility
      if (compressorId === 'sz3') {
        const sz3Options = {
          predictor: [
            { label: 'Bypass', state: 'available', value: 'ALGO_NOPRED' },
            { label: 'Interpolation', state: 'available', value: 'ALGO_INTERP' },
            { label: 'Lorenzo', state: 'available', value: 'ALGO_INTERP_LORENZO' },
            { label: 'Adaptive', state: 'available', value: 'ALGO_LORENZO_REG' },
          ],
          quantizer: [
            { label: 'Linear-scaling', state: 'available', value: 65536 },
          ],
          encoder: [
            { label: 'Bypass', state: 'available', value: '0' },
            { label: 'Huffman', state: 'available', value: '1' },
            { label: 'Arithmetic', state: 'available', value: '2' },
          ],
          lossless: [
            { label: 'Bypass', state: 'available', value: '0' },
            { label: 'Zstd', state: 'available', value: '1' },
          ],
        };
        return sz3Options[moduleId] || [];
      }
      return [];
    },
    getIncomingData(nodeId) {
      const node = this.nodes.find(n => n.id === nodeId);
      const incomingEdges = this.edges.filter(e => e.to.nodeId === nodeId);
      const data = {};

      // Process explicit connections
      incomingEdges.forEach(edge => {
        const sourceNode = this.nodes.find(n => n.id === edge.from.nodeId);
        if (!sourceNode) return;

        let sourceData = null;
        if (sourceNode.type === 'source') {
          sourceData = {
            data_key: this.$store.state.dataset?.data_key || this.$store.state.dataset?.name,
            meta: {
              dimensions: [
                this.$store.state.dataset?.width,
                this.$store.state.dataset?.height,
                this.$store.state.dataset?.depth
              ].filter(d => d && d !== '1' && d !== 1).map(Number),
              precision: this.$store.state.dataset?.precision,
              name: this.$store.state.dataset?.name
            }
          };
        } else if (sourceNode.type === 'filter' || sourceNode.type === 'compressor' || sourceNode.type === 'correction') {
          const rawData = sourceNode.lastResult || (this.comparisonData ? this.comparisonData[sourceNode.id] : null);
          if (rawData) {
            // Include node ID for downstream traceability (e.g. for batch processing)
            sourceData = { ...rawData, sourceNodeId: sourceNode.id };
          } else {
            // Provide a placeholder with node ID to allow variants detection before the node is run
            sourceData = { sourceNodeId: sourceNode.id, is_placeholder: true };
          }
        }

        data[edge.to.portId] = sourceData;
      });

      // Special handling for correction nodes: implicitly provide original data
      if (node && node.type === 'correction') {
        const originalSourceNode = this.nodes.find(n => n.type === 'source');
        if (originalSourceNode) {
          data['original'] = {
            data_key: this.$store.state.dataset?.data_key || this.$store.state.dataset?.name,
            meta: {
              dimensions: [
                this.$store.state.dataset?.width,
                this.$store.state.dataset?.height,
                this.$store.state.dataset?.depth
              ].filter(d => d && d !== '1' && d !== 1).map(Number),
              precision: this.$store.state.dataset?.precision,
              name: this.$store.state.dataset?.name
            }
          };
        }
      }

      return data;
    },
    updateCanvasSize() {
      if (!this.nodes.length) {
        this.initializeCanvasSize();
        return;
      }

      // Get minimum dimensions from current pane size
      const paneEl = this.$refs.graphPane?.$el;
      const rect = paneEl?.getBoundingClientRect();

      let minWidth = 800;
      let minHeight = 600;

      if (rect) {
        minWidth = Math.max(400, rect.width - 15);
        minHeight = Math.max(400, rect.height - 60);
      }

      // Calculate required canvas size based on rendered node bounds when available.
      let maxX = minWidth;
      let maxY = minHeight;
      const footerReserve = this.nodes.length ? 44 : 0;
      const canvasEl = this.$refs.canvas;
      const renderedNodes = canvasEl
        ? Array.from(canvasEl.querySelectorAll('[data-node-id]'))
        : [];
      const measuredNodes = new Map(
        renderedNodes.map((el) => [el.dataset.nodeId, { width: el.offsetWidth, height: el.offsetHeight }])
      );

      this.nodes.forEach(node => {
        const measured = measuredNodes.get(node.id);
        const nodeWidth = measured?.width || 420;
        const nodeHeight = measured?.height || 220;

        const rightEdge = (node.x || 0) + nodeWidth + 50;
        const bottomEdge = (node.y || 0) + nodeHeight + 50 + footerReserve;

        if (rightEdge > maxX) maxX = rightEdge;
        if (bottomEdge > maxY) maxY = bottomEdge;
      });

      this.canvasSize.width = maxX;
      this.canvasSize.height = maxY;
    },
    formatTimestamp(timestamp) {
      if (!timestamp) return '—';
      const date = new Date(timestamp);
      return date.toLocaleString();
    },
    getWorkflowDefinition(type, definitionId) {
      if (!definitionId) return null;
      const registries = {
        filter: this.availableFilters,
        module: this.availableModules,
        compressor: this.availableCompressors,
        correction: this.availableCorrections,
      };
      return registries[type]?.find(def => def.id === definitionId) || null;
    },
    getWorkflowNodeDefaults(type, definitionId) {
      const definition = this.getWorkflowDefinition(type, definitionId);
      const fallback = {
        source: { label: 'Data Source', icon: 'bi-database' },
        filter: { label: 'Filter', icon: 'bi-funnel' },
        module: { label: 'Module', icon: 'bi-puzzle' },
        compressor: { label: 'Compressor', icon: 'bi-cpu', architecture: 'parametric' },
        correction: { label: 'Correction', icon: 'bi-gear' },
      }[type] || { label: 'Node', icon: 'bi-box' };

      return {
        ...fallback,
        ...(definition || {}),
      };
    },
    stripWorkflowMetadata(value) {
      if (Array.isArray(value)) {
        return value.map(item => this.stripWorkflowMetadata(item));
      }
      if (!value || typeof value !== 'object') {
        return value;
      }

      return Object.entries(value).reduce((acc, [key, entry]) => {
        if (['timestamp', 'createdAt', 'updatedAt', 'lastUpdatedAt'].includes(key)) {
          return acc;
        }
        acc[key] = this.stripWorkflowMetadata(entry);
        return acc;
      }, {});
    },
    hasWorkflowValue(value) {
      if (Array.isArray(value)) return value.length > 0;
      if (!value || typeof value !== 'object') return value !== undefined && value !== null;
      return Object.keys(value).length > 0;
    },
    serializeWorkflowNode(node) {
      const definition = node.definitionId || node.compressorId || null;
      const defaults = this.getWorkflowNodeDefaults(node.type, definition);
      const data = {
        id: node.id,
        type: node.type,
      };

      if (definition) data.definition = definition;
      if (node.label && node.label !== defaults.label) data.label = node.label;
      if (Number.isFinite(node.x) || Number.isFinite(node.y)) {
        data.position = {
          x: Number.isFinite(node.x) ? Math.round(node.x) : 0,
          y: Number.isFinite(node.y) ? Math.round(node.y) : 0,
        };
      }
      if (this.hasWorkflowValue(node.config)) {
        data.config = this.stripWorkflowMetadata(node.config);
      }
      if (node.type === 'compressor') {
        const architecture = node.architecture || defaults.architecture;
        if (architecture && architecture !== defaults.architecture) data.architecture = architecture;
        if (this.hasWorkflowValue(node.modules)) {
          data.modules = this.stripWorkflowMetadata(node.modules);
        }
      }

      return data;
    },
    normalizeWorkflowEndpoint(endpoint, defaultPortId) {
      if (typeof endpoint === 'string') {
        return { nodeId: endpoint, portId: defaultPortId };
      }
      return {
        nodeId: endpoint?.nodeId || endpoint?.node || endpoint?.id,
        portId: endpoint?.portId || endpoint?.port || defaultPortId,
      };
    },
    normalizeWorkflowEdge(edge) {
      if (Array.isArray(edge)) {
        return {
          from: this.normalizeWorkflowEndpoint(edge[0], 'out-0'),
          to: this.normalizeWorkflowEndpoint(edge[1], 'in-0'),
        };
      }
      return {
        from: this.normalizeWorkflowEndpoint(edge?.from, 'out-0'),
        to: this.normalizeWorkflowEndpoint(edge?.to, 'in-0'),
      };
    },
    applyWorkflowEditorComponent(node, definitionId) {
      if (node.type === 'source') {
        node.editorComponent = markRaw(InputDataset);
      } else if (node.type === 'filter') {
        if (definitionId === 'clipping') node.editorComponent = markRaw(DataClipping);
        else if (definitionId === 'threshold_mask') node.editorComponent = markRaw(DataThresholdMask);
        else if (definitionId === 'normalization') node.editorComponent = markRaw(DataNormalization);
        else node.editorComponent = null;
      } else if (node.type === 'compressor') {
        if (definitionId === 'sz3') node.editorComponent = markRaw(SZ3Pipeline);
        else if (definitionId === 'zfp') node.editorComponent = markRaw(ZFPConfig);
        else node.editorComponent = null;
      } else if (node.type === 'module') {
        node.editorComponent = markRaw(BaseCompressionModule);
      } else if (node.type === 'correction') {
        if (definitionId === 'morse_smale_correction') node.editorComponent = markRaw(CriticalPointsCorrection);
        else if (definitionId === 'ffcz_correction') node.editorComponent = markRaw(FFCzCorrection);
        else node.editorComponent = null;
      }
    },
    recalculateWorkflowCounters() {
      const counters = { source: 0, filter: 0, module: 0, compressor: 0, correction: 0 };
      this.nodes.forEach(node => {
        if (!(node.type in counters)) return;
        const match = String(node.id || '').match(/-(\d+)$/);
        counters[node.type] = Math.max(counters[node.type], match ? Number(match[1]) : counters[node.type] + 1);
      });
      this.counters = counters;
    },
    describeModuleSelection(module) {
      if (!module || !module.value || !Object.keys(module.value).length) {
        return 'Not configured';
      }
      const [label] = Object.keys(module.value);
      return label || 'Configured';
    },

    /**
     * Export the workflow graph as compact, LLM-friendly JSON.
     */
    exportWorkflow() {
      try {
        const serializedNodes = this.nodes.map(node => this.serializeWorkflowNode(node));
        const serializedEdges = this.edges.map(edge => ({
          from: edge.from.portId === 'out-0'
            ? edge.from.nodeId
            : { node: edge.from.nodeId, port: edge.from.portId },
          to: edge.to.portId === 'in-0'
            ? edge.to.nodeId
            : { node: edge.to.nodeId, port: edge.to.portId },
        }));
        const baseConfigurations = this.stripWorkflowMetadata({ ...this.baseConfigurations });
        const derivedConfigurations = this.stripWorkflowMetadata({ ...this.derivedConfigurations });
        const hasConfigurations = this.hasWorkflowValue(baseConfigurations) || this.hasWorkflowValue(derivedConfigurations);

        const workflowData = {
          version: '1.1',
          nodes: serializedNodes,
          edges: serializedEdges,
          ...(hasConfigurations && {
            configurations: {
              base: baseConfigurations,
              derived: derivedConfigurations,
            },
          }),
        };

        const json = JSON.stringify(workflowData, null, 2);
        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `workflow-${Date.now()}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);

        this.$store.commit('setStatus', {
          type: 'success',
          message: 'Workflow exported successfully!'
        });
      } catch (error) {
        console.error('Failed to export workflow:', error);
        this.$store.commit('setStatus', {
          type: 'danger',
          message: 'Failed to export workflow: ' + error.message
        });
      }
    },

    /**
     * Import a workflow graph from a JSON file
     */
    importWorkflow() {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = 'application/json,.json';

      input.onchange = async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        try {
          const text = await file.text();
          const workflowData = JSON.parse(text);

          // Validate the workflow data
          if (!Array.isArray(workflowData.nodes) || !Array.isArray(workflowData.edges)) {
            throw new Error('Invalid workflow file format');
          }

          // Clear existing workflow
          this.nodes = [];
          this.edges = [];
          this.selectedNodeId = null;

          // Restore counters
          if (workflowData.counters) {
            this.counters = { ...workflowData.counters };
          }

          // Recreate nodes using NodeFactory
          workflowData.nodes.forEach(nodeData => {
            const definitionId = nodeData.definition || nodeData.definitionId || nodeData.compressorId || null;
            const defaults = this.getWorkflowNodeDefaults(nodeData.type, definitionId);
            const position = nodeData.position || {};
            const nodeConfig = nodeData.config || {};
            const node = NodeFactory.createNode(
              nodeData.type,
              nodeData.id,
              nodeData.label || defaults.label,
              nodeData.icon || defaults.icon,
              definitionId,
              {
                inputCount: nodeData.inputCount || nodeData.input_count || defaults.inputCount,
                outputCount: nodeData.outputCount || nodeData.output_count || defaults.outputCount,
                architecture: nodeData.architecture || nodeConfig.architecture || defaults.architecture,
              }
            );

            // Restore position
            node.x = position.x ?? nodeData.x ?? 0;
            node.y = position.y ?? nodeData.y ?? 0;

            // Restore config
            node.config = nodeConfig;

            // Restore compressor-specific properties
            if (nodeData.type === 'compressor') {
              node.expanded = nodeData.expanded || false;
              node.modules = nodeData.modules || [];
              node.selectedModuleIdx = nodeData.selectedModuleIdx || null;
              node.definitionId = definitionId;
            }

            // Restore filter/correction/module definition IDs
            if (definitionId) {
              node.definitionId = definitionId;
            }

            // Restore description
            if (nodeData.description) {
              node.description = nodeData.description;
            }

            // Restore editor component
            if (nodeData.editorComponent && typeof nodeData.editorComponent === 'string') {
              node.editorComponent = nodeData.editorComponent;
            } else {
              this.applyWorkflowEditorComponent(node, definitionId);
            }

            // Set initial status based on node type
            if (node.type === 'source') {
              node.status = this.datasetLoaded ? 'ready' : 'empty';
            } else {
              node.status = 'pending';
            }

            this.nodes.push(node);
          });

          // Restore edges
          workflowData.edges.forEach(edgeData => {
            const edge = this.normalizeWorkflowEdge(edgeData);
            if (edge.from.nodeId && edge.to.nodeId) {
              this.edges.push(edge);
            }
          });
          if (!workflowData.counters) {
            this.recalculateWorkflowCounters();
          }

          // Restore Config Graph data
          const baseConfigurations = workflowData.baseConfigurations || workflowData.configurations?.base;
          const derivedConfigurations = workflowData.derivedConfigurations || workflowData.configurations?.derived;
          if (baseConfigurations) {
            // Clear existing configurations
            this.$store.state.baseConfigurations = {};
            this.$store.state.derivedConfigurations = {};

            // Restore base configurations
            Object.entries(baseConfigurations).forEach(([name, config]) => {
              this.$store.commit('addBaseConfiguration', { name, config });
            });

            // Restore derived configurations
            if (derivedConfigurations) {
              Object.entries(derivedConfigurations).forEach(([baseName, derivedMap]) => {
                Object.entries(derivedMap).forEach(([derivedName, config]) => {
                  this.$store.commit('addDerivedConfiguration', { baseName, derivedName, config });
                });
              });
            }
          }

          // Update canvas size based on imported nodes
          this.$nextTick(() => {
            this.updateCanvasSize();
          });

          const configCount = Object.keys(baseConfigurations || {}).length;
          const configMsg = configCount > 0 ? ` and ${configCount} base configuration(s)` : '';
          this.$store.commit('setStatus', {
            type: 'success',
            message: `Workflow imported successfully! Loaded ${this.nodes.length} nodes, ${this.edges.length} connections${configMsg}.`
          });
        } catch (error) {
          console.error('Failed to import workflow:', error);
          this.$store.commit('setStatus', {
            type: 'danger',
            message: 'Failed to import workflow: ' + error.message
          });
        }
      };

      input.click();
    },
  }
};
</script>

<template>
  <div class="dataflow-workbench h-100 container-fluid py-2">
    <!-- Delete Confirmation Modal -->
    <div
      class="modal fade"
      :class="{ show: deleteConfirmation.show, 'd-block': deleteConfirmation.show }"
      tabindex="-1"
      role="dialog"
      @click.self="cancelRemoveNode"
    >
      <div class="modal-dialog modal-dialog-centered" role="document">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              <i class="bi bi-exclamation-triangle-fill text-warning me-2"></i>
              Confirm Deletion
            </h5>
            <button type="button" class="btn-close" @click="cancelRemoveNode" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <p class="mb-2">
              Are you sure you want to remove the <strong>"{{ deleteConfirmation.nodeLabel }}"</strong> node?
            </p>
            <div class="alert alert-warning mb-0">
              <i class="bi bi-info-circle me-1"></i>
              This may affect downstream operations and connections will be removed.
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" @click="cancelRemoveNode">Cancel</button>
            <button type="button" class="btn btn-danger" @click="confirmRemoveNode">
              <i class="bi bi-trash me-1"></i>Delete Node
            </button>
          </div>
        </div>
      </div>
    </div>
    <div v-if="deleteConfirmation.show" class="modal-backdrop fade show"></div>

    <!-- Novice Exploration Modal -->
    <div
      class="modal fade"
      :class="{ show: showExploreModal, 'd-block': showExploreModal }"
      tabindex="-1"
      role="dialog"
      @click.self="closeExploreModal"
    >
      <div class="modal-dialog modal-lg modal-dialog-centered" role="document">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">Novice Exploration</h5>
            <button type="button" class="btn-close" @click="closeExploreModal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <p class="text-muted small mb-2">
              Parallel coordinates view of generated configurations for <strong>{{ exploreNodeId }}</strong>.
            </p>
            <div v-if="explorePlot" class="explore-plot">
              <svg :width="540" :height="260">
                <g>
                  <line
                    v-for="(axis, idx) in explorePlot.axes"
                    :key="`axis-${axis.key}`"
                    :x1="exploreAxisX(idx, 540, 40)"
                    :y1="30"
                    :x2="exploreAxisX(idx, 540, 40)"
                    :y2="230"
                    stroke="#adb5bd"
                    stroke-width="1"
                  />
                  <text
                    v-for="(axis, idx) in explorePlot.axes"
                    :key="`axis-label-${axis.key}`"
                    :x="exploreAxisX(idx, 540, 40)"
                    y="18"
                    text-anchor="middle"
                    font-size="14"
                    font-weight="500"
                    fill="#495057"
                  >
                    {{ (axis.label || axis.key).replace(/^.*?:/, '') }}
                  </text>
                  <g v-for="(axis, idx) in explorePlot.axes" :key="`axis-options-${axis.key}`">
                    <text
                      v-for="(optLabel, optIdx) in axis.optionLabels"
                      :key="`axis-option-${axis.key}-${optIdx}`"
                      :x="exploreAxisX(idx, 540, 40) + 6"
                      :y="exploreOptionY(axis, optIdx, 260, 40)"
                      text-anchor="start"
                      font-size="12"
                      fill="#6c757d"
                    >
                      {{ optLabel }}
                    </text>
                  </g>
                  <text
                    v-for="(axis, idx) in explorePlot.axes"
                    :key="`axis-value-${axis.key}`"
                    :x="exploreAxisX(idx, 540, 40)"
                    y="245"
                    text-anchor="middle"
                    font-size="12"
                    fill="#6c757d"
                  >
                    {{ formatExploreValue(axis, explorePlot.values[0]?.[idx]) }}
                  </text>
                </g>
                <g>
                  <path
                    v-for="(row, idx) in explorePlot.values"
                    :key="`row-${idx}`"
                    :d="explorePathForRow(row, 540, 260, 40)"
                    :stroke="idx === 0 ? '#0d6efd' : 'rgba(13,110,253,0.25)'"
                    :stroke-width="idx === 0 ? 2 : 1"
                    fill="none"
                  />
                </g>
              </svg>
            </div>
            <div v-else class="text-muted small">
              No configurations available for visualization.
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" @click="closeExploreModal">Close</button>
          </div>
        </div>
      </div>
    </div>
    <div v-if="showExploreModal" class="modal-backdrop fade show"></div>

    <!-- Node Properties Modal -->
    <div
      class="modal fade"
      :class="{ show: showPropertiesModal, 'd-block': showPropertiesModal }"
      tabindex="-1"
      role="dialog"
      @click.self="closePropertiesModal"
    >
      <div class="modal-dialog modal-lg modal-dialog-centered modal-dialog-scrollable" role="document">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              <i v-if="selectedNode" :class="['bi', selectedNode.icon, 'me-2']"></i>
              {{ selectedNode ? selectedNode.label : 'Node Properties' }}
            </h5>
            <button type="button" class="btn-close" @click="closePropertiesModal" aria-label="Close"></button>
          </div>
          <div class="modal-body" v-if="selectedNode">
            <template v-if="selectedNode.type === 'source'">
              <keep-alive>
                <InputDataset />
              </keep-alive>
            </template>

            <template v-else-if="selectedNode.type === 'filter'">
              <p v-if="selectedNode.description" class="text-muted small mb-3">
                {{ selectedNode.description }}
              </p>
              <template v-if="selectedNode.editorComponent">
                <keep-alive>
                  <component
                    :is="selectedNode.editorComponent"
                    :key="selectedNode.id"
                    :nodeId="selectedNode.id"
                    v-bind="selectedNode.props"
                    @filter-start="() => handleFilterStart(selectedNode.id)"
                    @filter-success="($event) => handleFilterSuccess($event.nodeId || selectedNode.id, $event)"
                    @filter-error="($event) => handleFilterError($event.nodeId || selectedNode.id, $event)"
                    @filter-invalid="($event) => handleFilterInvalid($event.nodeId || selectedNode.id, $event)"
                    @filter-finish="() => handleFilterFinish(selectedNode.id)"
                    @dataset-change="() => handleFilterDatasetChange(selectedNode.id)"
                  />
                </keep-alive>
              </template>
              <p v-else class="text-muted small mb-0">No filter UI available.</p>
            </template>

            <template v-else-if="selectedNode.type === 'module'">
              <p v-if="selectedNode.description" class="text-muted small mb-3">
                {{ selectedNode.description }}
              </p>
              <div class="alert alert-info small mb-3">
                <i class="bi bi-info-circle"></i>
                This module requires {{ selectedNode.inputs.length }} input{{ selectedNode.inputs.length > 1 ? 's' : '' }}.
                {{ selectedNode.inputs.length > 1 ? 'Connect multiple data sources or filters to the input ports.' : 'Connect a data source or filter to the input port.' }}
              </div>
              <template v-if="selectedNode.editorComponent">
                <keep-alive>
                  <component
                    :is="selectedNode.editorComponent"
                    :key="selectedNode.id"
                    :node-id="selectedNode.id"
                    :module-definition="availableModules.find(m => m.id === selectedNode.definitionId) || {}"
                    :node-config="selectedNode.config || {}"
                    @config-change="onNodeConfigChange"
                  />
                </keep-alive>
              </template>
              <p v-else class="text-muted small mb-0">No module UI available.</p>
            </template>

            <template v-else-if="selectedNode.type === 'compressor'">
              <div class="mb-3" v-if="selectedNode.definitionId">
                <label class="form-label fw-semibold">
                  Compressor: {{ selectedNode.label }}
                </label>
                <p class="text-muted small mb-0">
                  {{ selectedNode.description }}
                </p>
              </div>
              <template v-if="selectedNode.editorComponent">
                <keep-alive>
                  <component
                    :is="selectedNode.editorComponent"
                    :key="`compressor-${selectedNode.id}-${selectedNode.selectedModuleIdx ?? 'all'}`"
                    :node-id="selectedNode.id"
                    :focused-module-idx="selectedNode.selectedModuleIdx"
                    :modules="selectedNode.modules"
                    :config="selectedNode.config"
                    :explore-state="selectedNode.exploreState"
                    :status="selectedNode.status"
                    @config-change="onNodeConfigChange"
                    @pipeline-modules-updated="handlePipelineModulesUpdated"
                    @run-compressor="handleRunCompressor"
                    @generate-configs="handleCombinatorialGeneration"
                    @explore-state-changed="($event) => handleExploreStateChanged(selectedNode.id, $event)"
                  />
                </keep-alive>
              </template>
              <p v-else class="text-muted small mb-0">No compressor UI available.</p>
            </template>

            <template v-else-if="selectedNode.type === 'correction'">
              <p v-if="selectedNode.description" class="text-muted small mb-3">
                {{ selectedNode.description }}
              </p>
              <template v-if="selectedNode.editorComponent">
                <keep-alive>
                  <component
                    :is="selectedNode.editorComponent"
                    :key="selectedNode.id"
                    :nodeId="selectedNode.id"
                    :config="selectedNode.config"
                    :input-data="getIncomingData(selectedNode.id)"
                    @config-change="onNodeConfigChange"
                    @start="(nodeId) => handleFilterStart(nodeId)"
                    @success="handleCorrectionSuccess"
                    @error="($event) => handleFilterError($event.nodeId || selectedNode.id, $event)"
                    @finish="($event) => handleFilterFinish($event || selectedNode.id)"
                  />
                </keep-alive>
              </template>
              <p v-else class="text-muted small mb-0">No correction UI available.</p>
            </template>

            <template v-else>
              <p class="text-muted small mb-0">No editor available for this node type ({{ selectedNode.type }}).</p>
            </template>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" @click="closePropertiesModal">Close</button>
          </div>
        </div>
      </div>
    </div>
    <div v-if="showPropertiesModal" class="modal-backdrop fade show"></div>

    <Splitpanes class="default-theme w-100 h-100" :dbl-click-splitter="false" @resized="onSplitResize">
      <!-- Left: Node Palette -->
      <Pane :size="30" min-size="20" max-size="50" class="h-100 overflow-auto">
        <div class="card shadow-sm">
          <div class="card-header d-flex align-items-center justify-content-between py-2">
            <span class="fw-semibold">Pipeline Components</span>
          </div>
          <div class="list-group list-group-flush">
            <!-- Data Source -->
            <button
              type="button"
              class="list-group-item d-flex align-items-center justify-content-between text-start"
              :class="{
                'node-disabled': !canAddNodeType('source'),
                'node-enabled': canAddNodeType('source')
              }"
              :draggable="canAddNodeType('source')"
              @dragstart="onDragStart($event, { type: 'source', id: 'source' })"
              title="Load and manage input dataset."
            >
              <div class="d-flex align-items-center gap-2">
                <i class="bi bi-database" aria-hidden="true"></i>
                <span class="fw-semibold">Data Source</span>
              </div>
              <i class="bi bi-arrows-move text-muted" aria-hidden="true" title="Drag to canvas"></i>
            </button>

            <!-- Data Filters -->
            <div
              class="list-group-item bg-light fw-semibold d-flex justify-content-between align-items-center cursor-pointer"
              @click="paletteState.filters = !paletteState.filters"
            >
              <div class="d-flex align-items-center gap-2">
                <i :class="['bi', paletteState.filters ? 'bi-chevron-down' : 'bi-chevron-right']"></i>
                <span>Data Filters</span>
              </div>
              <span class="badge bg-secondary">{{ availableFilters.length }}</span>
            </div>

            <template v-if="paletteState.filters">
              <button
                v-for="filter in availableFilters"
                :key="`pf-${filter.id}`"
                type="button"
                class="list-group-item d-flex align-items-center justify-content-between text-start"
                :class="{
                  'node-disabled': !canAddNodeType('filter'),
                  'node-enabled': canAddNodeType('filter')
                }"
                :draggable="canAddNodeType('filter')"
                @dragstart="onDragStart($event, { type: 'filter', id: filter.id })"
                :title="filter.description"
              >
                <div class="d-flex align-items-center gap-2">
                  <i :class="['bi', filter.icon || 'bi-funnel']" aria-hidden="true"></i>
                  <div>
                    <div class="fw-semibold">{{ filter.label }}</div>
                    <div class="text-muted small">{{ filter.description }}</div>
                  </div>
                </div>
                <i class="bi bi-arrows-move text-muted" aria-hidden="true" title="Drag to canvas"></i>
              </button>
            </template>

            <div
              class="list-group-item bg-light fw-semibold d-flex justify-content-between align-items-center cursor-pointer"
              @click="paletteState.modules = !paletteState.modules"
            >
              <div class="d-flex align-items-center gap-2">
                <i :class="['bi', paletteState.modules ? 'bi-chevron-down' : 'bi-chevron-right']"></i>
                <span>Compression Modules</span>
              </div>
              <span class="badge bg-secondary">{{ availableModules.length }}</span>
            </div>

            <template v-if="paletteState.modules">
              <button
                v-for="mod in availableModules"
                :key="`pm-${mod.id}`"
                type="button"
                class="list-group-item d-flex align-items-center justify-content-between text-start"
                :class="{
                  'node-disabled': !canAddNodeType('module'),
                  'node-enabled': canAddNodeType('module')
                }"
                :draggable="canAddNodeType('module')"
                @dragstart="onDragStart($event, { type: 'module', id: mod.id })"
                :title="mod.description"
              >
                <div class="d-flex align-items-center gap-2">
                  <i :class="['bi', mod.icon || 'bi-puzzle']" aria-hidden="true"></i>
                  <div>
                    <div class="fw-semibold">{{ mod.label }}</div>
                    <div class="text-muted small">{{ mod.description }}</div>
                  </div>
                </div>
                <i class="bi bi-arrows-move text-muted" aria-hidden="true" title="Drag to canvas"></i>
              </button>
            </template>

            <!-- Compressor Configs -->
            <div
              class="list-group-item bg-light fw-semibold d-flex justify-content-between align-items-center cursor-pointer"
              @click="paletteState.compressors = !paletteState.compressors"
            >
              <div class="d-flex align-items-center gap-2">
                <i :class="['bi', paletteState.compressors ? 'bi-chevron-down' : 'bi-chevron-right']"></i>
                <span>Compressor Configs</span>
              </div>
              <span class="badge bg-secondary">{{ availableCompressors.length }}</span>
            </div>

            <template v-if="paletteState.compressors">
              <button
                v-for="comp in availableCompressors"
                :key="`pc-${comp.id}`"
                type="button"
                class="list-group-item d-flex align-items-center justify-content-between text-start"
                :class="{
                  'node-disabled': !canAddNodeType('compressor'),
                  'node-enabled': canAddNodeType('compressor')
                }"
                :draggable="canAddNodeType('compressor')"
                @dragstart="onDragStart($event, { type: 'compressor', id: comp.id })"
                :title="comp.description"
              >
                <div class="d-flex align-items-center gap-2">
                  <i :class="['bi', comp.icon || 'bi-cpu']" aria-hidden="true"></i>
                  <div>
                    <div class="fw-semibold">{{ comp.label }}</div>
                    <div class="text-muted small">{{ comp.description }}</div>
                  </div>
                </div>
                <i class="bi bi-arrows-move text-muted" aria-hidden="true" title="Drag to canvas"></i>
              </button>
            </template>

            <!-- Corrections -->
            <div
              class="list-group-item bg-light fw-semibold d-flex justify-content-between align-items-center cursor-pointer"
              @click="paletteState.corrections = !paletteState.corrections"
            >
              <div class="d-flex align-items-center gap-2">
                <i :class="['bi', paletteState.corrections ? 'bi-chevron-down' : 'bi-chevron-right']"></i>
                <span>Correction Modules</span>
              </div>
              <span class="badge bg-secondary">{{ availableCorrections.length }}</span>
            </div>

            <template v-if="paletteState.corrections">
              <button
                v-for="corr in availableCorrections"
                :key="`pc-${corr.id}`"
                type="button"
                class="list-group-item d-flex align-items-center justify-content-between text-start"
                :class="{
                  'node-disabled': !canAddNodeType('correction'),
                  'node-enabled': canAddNodeType('correction')
                }"
                :draggable="canAddNodeType('correction')"
                @dragstart="onDragStart($event, { type: 'correction', id: corr.id })"
                :title="corr.description"
              >
                <div class="d-flex align-items-center gap-2">
                  <i :class="['bi', corr.icon || 'bi-gear']" aria-hidden="true"></i>
                  <div>
                    <div class="fw-semibold">{{ corr.label }}</div>
                    <div class="text-muted small">{{ corr.description }}</div>
                  </div>
                </div>
                <i class="bi bi-arrows-move text-muted" aria-hidden="true" title="Drag to canvas"></i>
              </button>
            </template>
          </div>
        </div>
      </Pane>

      <!-- Right: Data Flow Graph area -->
      <Pane ref="graphPane" :size="70" min-size="40" class="h-100 overflow-auto">
        <div class="work-area d-flex flex-column">
          <div
            class="card shadow-sm canvas d-flex flex-column graph-card"
            :style="{ width: canvasSize.width + 'px' }"
            @dragover.prevent
            @drop="onCanvasDrop"
          >
            <div class="card-header d-flex align-items-center justify-content-between py-2">
              <div class="d-flex align-items-center">
                <span class="fw-semibold">Data Flow Graph</span>
                <small class="text-muted px-3">Drag components from the left panel</small>
              </div>
              <div class="d-flex align-items-center gap-2">
                <button
                  type="button"
                  class="btn btn-sm btn-outline-primary"
                  @click="exportWorkflow"
                  title="Export workflow to JSON file"
                  :disabled="nodes.length === 0"
                >
                  <i class="bi bi-download me-1"></i>Export
                </button>
                <button
                  type="button"
                  class="btn btn-sm btn-outline-secondary"
                  @click="importWorkflow"
                  title="Import workflow from JSON file"
                >
                  <i class="bi bi-upload me-1"></i>Import
                </button>
              </div>
            </div>
            <div
              ref="canvas"
              class="card-body p-0 position-relative"
              @click="clearSelection"
              :style="{ height: canvasSize.height + 'px' }"
            >
              <!-- Edges overlay layer -->
              <svg class="position-absolute top-0 start-0" width="100%" height="100%" style="pointer-events: none; min-width: 100%; min-height: 100%;">
                <template v-for="edge in edges" :key="`${edge.from.nodeId}:${edge.from.portId}->${edge.to.nodeId}:${edge.to.portId}`">
                  <line
                    :x1="getPortPosition(edge.from.nodeId, edge.from.portId, 'output').x"
                    :y1="getPortPosition(edge.from.nodeId, edge.from.portId, 'output').y"
                    :x2="getPortPosition(edge.to.nodeId, edge.to.portId, 'input').x"
                    :y2="getPortPosition(edge.to.nodeId, edge.to.portId, 'input').y"
                    stroke="#0d6efd"
                    stroke-width="2"
                  />
                </template>
                <line
                  v-if="connecting.active && connecting.sourceNodeId && connecting.sourcePortId"
                  :x1="getPortPosition(connecting.sourceNodeId, connecting.sourcePortId, 'output').x"
                  :y1="getPortPosition(connecting.sourceNodeId, connecting.sourcePortId, 'output').y"
                  :x2="connecting.mouseX"
                  :y2="connecting.mouseY"
                  stroke="#6c757d"
                  stroke-width="2"
                  stroke-dasharray="4 4"
                />
              </svg>
              <div
                v-for="node in nodes"
                :key="node.id"
                class="df-node card shadow-sm"
                :class="{ selected: node.id === selectedNodeId }"
                :style="{ left: node.x + 'px', top: node.y + 'px' }"
                :data-node-id="node.id"
                @mousedown.stop="startDrag(node, $event)"
                @click.stop="selectNode(node.id)"
                @dblclick.stop="openPropertiesModal(node.id)"
              >
                <div class="card-header py-1 d-flex align-items-center justify-content-between">
                  <div class="d-flex align-items-center gap-2 flex-wrap flex-grow-1">
                    <i :class="['bi', node.icon]" aria-hidden="true"></i>
                    <span class="fw-semibold">{{ node.label }}</span>
                    <span class="badge rounded-pill" :class="getStatusBadgeClass(node.status)">{{ getStatusLabel(node.status) }}</span>
                    <span
                      v-if="node.type === 'compressor' && getVariantCount(node) > 0"
                      class="badge rounded-pill bg-info text-dark variant-badge"
                      :title="`Variants: ${getVariantCount(node)}`"
                    >
                      <i class="bi bi-layers me-1"></i>{{ getVariantCount(node) }}
                    </span>
                  </div>
                  <div class="d-flex align-items-center gap-1 ms-2">
                    <button
                      v-if="node.type === 'compressor'"
                      type="button"
                      class="btn btn-sm btn-outline-primary"
                      @click.stop="promoteToConfigGraph(node)"
                      title="Promote to Config Graph for bulk generation"
                    >
                      <i class="bi bi-box-arrow-in-up"></i>
                    </button>
                    <button
                      v-if="node.type === 'compressor' && node.modules && node.modules.length"
                      type="button"
                      class="btn btn-sm btn-outline-secondary"
                      @click.stop="toggleCompressorExpansion(node.id)"
                      :title="node.expanded ? 'Collapse pipeline view' : 'Expand pipeline view'"
                    >
                      <i class="bi" :class="node.expanded ? 'bi-chevron-up' : 'bi-chevron-down'"></i>
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-danger" title="Delete node" @click.stop="removeNode(node.id)">
                      <i class="bi bi-trash"></i>
                    </button>
                  </div>
                </div>
                <div class="card-body py-2 small text-muted">
                  <div v-if="node.type === 'source'">
                    <div>Provides dataset to the flow.</div>
                    <div v-if="datasetInfo && node.status !== 'empty'" class="mt-1">
                      <div v-if="datasetInfo.name">Name: <b>{{ datasetInfo.name }}</b></div>
                      <div>Type: <b>{{ datasetInfo.type || 'Unknown' }}</b></div>
                    </div>
                  </div>
                  <template v-else-if="node.type === 'filter'">
                    <!-- <div v-if="node.lastRunAt">Last run: {{ formatTimestamp(node.lastRunAt) }}</div> -->
                    <div v-if="node.lastResult?.dimensions">
                      Output dimensions: {{ node.lastResult.dimensions.join('×') }}
                    </div>
                    <div v-else>No output yet.</div>
                    <div v-if="node.description" class="text-muted small mt-2">{{ node.description }}</div>
                  </template>
                  <template v-else-if="node.type === 'module'">
                    <div class="mb-1">Processing module with {{ node.inputs.length }} inputs.</div>
                    <div v-if="node.description" class="text-muted small mt-2">{{ node.description }}</div>
                    <div class="mt-2 small">
                      <i class="bi bi-plug"></i> Connect {{ node.inputs.length }} data sources to process.
                    </div>
                  </template>
                  <template v-else-if="node.type === 'compressor'">
                    <div v-if="getVariantCount(node) > 0" class="variant-strip mb-2">
                      <span class="fw-semibold">Variants</span>
                      <div class="variant-dots">
                        <span
                          v-for="i in getVariantDots(getVariantCount(node))"
                          :key="`vd-${node.id}-${i}`"
                          class="variant-dot"
                        ></span>
                        <span
                          v-if="getVariantCount(node) > getVariantDots(getVariantCount(node))"
                          class="variant-overflow"
                        >
                          +{{ getVariantCount(node) - getVariantDots(getVariantCount(node)) }}
                        </span>
                      </div>
                    </div>
                    <!-- Expandable Module Pipeline View -->
                    <div v-if="node.expanded && node.modules && node.modules.length" class="module-pipeline mt-2 mb-2">
                      <div class="small text-muted mb-2">
                        <i class="bi bi-info-circle me-1"></i>
                        Click a module to configure it in the properties pane below.
                      </div>
                      <div
                        v-for="(module, idx) in node.modules"
                        :key="module.id"
                        class="module-box"
                        :class="{'selected': node.selectedModuleIdx === idx}"
                        @click.stop="selectCompressorModule(node.id, idx)"
                        @dragover.prevent="onModuleDragOver(node.id, idx, module.id, $event)"
                        @dragleave="onModuleDragLeave($event)"
                        @drop.stop="onModuleDrop(node.id, idx, module.id, $event)"
                      >
                        <div class="module-header">
                          <i class="bi bi-gear-fill me-1"></i>
                          <span class="fw-semibold">{{ module.label }}</span>
                        </div>
                        <div v-if="module.value && Object.keys(module.value).length" class="module-value">
                          <span class="badge bg-success">{{ Object.keys(module.value)[0] }}</span>
                        </div>
                        <div v-else class="module-value">
                          <span class="badge bg-secondary">Not Set</span>
                        </div>
                        <div v-if="idx < node.modules.length - 1" class="module-connector"></div>
                      </div>
                    </div>

                    <!-- Collapsed summary view -->
                    <div v-if="!node.expanded && Array.isArray(node.modules) && node.modules.length">
                      <div class="fw-semibold mt-1">Modules</div>
                      <ul class="list-unstyled mb-0">
                        <li v-for="m in node.modules" :key="m.id" class="d-flex justify-content-between align-items-center">
                          <span>{{ m.label }}</span>
                          <span class="text-muted">{{ describeModuleSelection(m) }}</span>
                        </li>
                      </ul>
                    </div>
                    <div v-if="(!node.modules || !node.modules.length) && node.architecture === 'modular'">No module selections yet.</div>
                    <!-- <div v-if="node.lastUpdatedAt" class="text-muted mt-2">Last updated: {{ formatTimestamp(node.lastUpdatedAt) }}</div> -->
                    <div v-if="node.description" class="text-muted small mt-2">{{ node.description }}</div>
                  </template>
                  <template v-else-if="node.type === 'correction'">
                    <!-- <div v-if="node.lastRunAt">Last run: {{ formatTimestamp(node.lastRunAt) }}</div> -->
                    <div v-if="node.lastResult?.num_edits !== undefined">
                      Applied edits: <b>{{ node.lastResult.num_edits }}</b>
                    </div>
                    <div v-if="hasManifoldData(node.lastResult)">
                      Manifolds: <span class="badge bg-info text-dark">Available</span>
                    </div>
                    <div v-else>Manifolds: <span class="text-muted">Not available</span></div>
                    <div v-if="node.description" class="text-muted small mt-2">{{ node.description }}</div>
                  </template>
                  <div v-else class="text-muted">No summary available.</div>
                </div>

                <!-- Ports -->
                <div class="node-ports">
                  <div class="input-ports">
                    <div
                      v-for="port in node.inputs"
                      :key="port.id"
                      class="port input-port"
                      :data-port-id="port.id"
                      data-port-side="input"
                      :title="port.label"
                      @mouseup.stop="completeConnection(node, port)"
                    ></div>
                  </div>
                  <div class="output-ports">
                    <div
                      v-for="port in node.outputs"
                      :key="port.id"
                      class="port output-port"
                      :data-port-id="port.id"
                      data-port-side="output"
                      :title="port.label"
                      @mousedown.stop="beginConnection(node, port)"
                    ></div>
                  </div>
                </div>
              </div>

              <div v-if="!nodes.length" class="h-100 d-flex align-items-center justify-content-center">
                <div class="text-center text-muted">
                  <i class="bi bi-arrows-move fs-3"></i>
                  <div class="mt-1">Drag a node from the left palette to start.</div>
                </div>
              </div>

              <!-- Instruction hint -->
              <div v-if="nodes.length" class="position-absolute bottom-0 start-0 w-100 text-center pb-2">
                <small class="text-muted">
                  <i class="bi bi-info-circle me-1"></i>
                  Double-click a node to open its properties
                </small>
              </div>
            </div>
          </div>
        </div>
      </Pane>
    </Splitpanes>
  </div>
</template>

<style scoped>

.canvas :deep(.card-body) {
  min-width: fit-content;
  min-height: fit-content;
}

.work-area {
  min-height: 100%;
  display: flex;
  flex-direction: column;
}

.graph-card {
  flex: 0 0 auto;
  min-height: fit-content;
  align-self: flex-start;
}

.df-node {
  position: absolute;
  display: inline-block;
  width: auto; /* allow node to expand to fit content */
  min-width: 180px;
  max-width: 400px; /* cap width to avoid overly wide nodes */
  cursor: move;
  user-select: none;
}

.cursor-pointer {
  cursor: pointer;
}

.node-disabled {
  opacity: 0.5;
  filter: grayscale(1);
  cursor: not-allowed !important;
  background-color: #f8f9fa !important;
  pointer-events: none; /* Disable all interactions including drag */
}

.node-enabled {
  background-color: rgba(25, 135, 84, 0.04) !important;
  border-left: 3px solid #198754 !important;
}

.df-node.selected {
  outline: 2px solid var(--bs-primary, #0d6efd);
}
/* Allow header to wrap when needed */
.df-node :deep(.card-header) {
  flex-wrap: wrap;
}
/* Ensure text wraps nicely inside the node */
.df-node :deep(.card-body) {
  white-space: normal;
  word-break: break-word;
}

/* Port Styles */
.node-ports {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.input-ports, .output-ports {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: row;
  gap: 8px;
}

.input-ports {
  top: -8px;
}

.output-ports {
  bottom: -8px;
}

.port {
  width: 16px;
  height: 16px;
  background-color: #fff;
  border: 2px solid #6c757d;
  border-radius: 50%;
  pointer-events: auto;
  cursor: crosshair;
  transition: background-color 0.2s, border-color 0.2s;
}

.port:hover {
  background-color: #e9ecef;
  border-color: #0d6efd;
}

/* Expandable Module Pipeline Styles */
.compressor-expanded {
  max-width: 500px !important; /* Allow more width when expanded */
}

.module-pipeline {
  background: #f8f9fa;
  border-radius: 6px;
  padding: 8px;
  border: 1px solid #dee2e6;
}

.module-box {
  position: relative;
  background: white;
  border: 2px solid #dee2e6;
  border-radius: 4px;
  padding: 8px 12px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.module-box:hover {
  border-color: #0d6efd;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.module-box.selected {
  border-color: #0d6efd;
  background-color: #e7f1ff;
  box-shadow: 0 0 0 2px rgba(13, 110, 253, 0.25);
}

.module-box:last-child {
  margin-bottom: 0;
}

.module-header {
  font-size: 0.875rem;
  margin-bottom: 4px;
  color: #495057;
}

.module-value {
  font-size: 0.75rem;
}

.module-value .badge {
  font-size: 0.7rem;
}

.module-connector {
  position: absolute;
  left: 50%;
  bottom: -8px;
  transform: translateX(-50%);
  width: 2px;
  height: 8px;
  background-color: #dee2e6;
  z-index: -1;
}

.variant-badge {
  border: 1px solid rgba(0, 0, 0, 0.08);
}

.variant-strip {
  display: flex;
  align-items: center;
  gap: 8px;
}

.variant-dots {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.variant-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #0dcaf0;
  box-shadow: 0 0 0 1px rgba(13, 202, 240, 0.3);
}

.variant-overflow {
  font-size: 0.75rem;
  color: #0b7285;
}

.explore-plot {
  border: 1px solid #dee2e6;
  border-radius: 8px;
  background: #fff;
  padding: 8px;
  overflow: auto;
}
.config-graph-overlay {
  transition: transform 0.2s ease, opacity 0.2s ease;
  backdrop-filter: blur(5px);
  background-color: rgba(255, 255, 255, 0.95) !important;
}

.config-graph-overlay:hover {
  box-shadow: 0 1rem 3rem rgba(0,0,0,0.175) !important;
}

.card-header.bg-primary.bg-gradient {
  background: linear-gradient(45deg, #0d6efd, #0dcaf0) !important;
}

/* Instruction hint at bottom of canvas */
.position-absolute.bottom-0 small {
  background: rgba(255, 255, 255, 0.9);
  padding: 4px 12px;
  border-radius: 4px;
  display: inline-block;
  backdrop-filter: blur(4px);
  pointer-events: none;
}
</style>
