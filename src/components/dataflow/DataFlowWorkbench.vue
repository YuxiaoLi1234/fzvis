
<script>
import { markRaw } from 'vue';
import axios from 'axios';
import InputDataset from '../InputDataset.vue';
import DataClipping from '../filter/DataClipping.vue';
import DataThresholdMask from '../filter/DataThresholdMask.vue';
import DataNormalization from '../filter/DataNormalization.vue';
import SZ3Pipeline from '../compressor/SZ3Pipeline.vue';
import ZFPConfig from '../compressor/ZFPConfig.vue';
import CriticalPointsCorrection from '../correction/CriticalPointsCorrection.vue';
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
        // Example: Add more modules with different configurations
        {
          id: 'merger',
          label: 'Data Merger',
          description: 'Merges three data streams into one.',
          icon: 'bi-bezier2',
          inputCount: 2,
          outputCount: 1,
        },
        {
          id: 'splitter',
          label: 'Data Splitter',
          description: 'Splits one data stream into two.',
          icon: 'bi-diagram-3',
          inputCount: 1,
          outputCount: 2,
        },
        {
          id: 'testing',
          label: 'Testing Module',
          description: 'A simple testing module that accepts two inputs and generates two outputs.',
          icon: 'bi-puzzle',
          inputCount: 2, 
          outputCount: 2,
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
          id: 'critical_points',
          label: 'Critical Points Correction',
          description: 'Apply fixes to correct critical points in the compressed data',
          icon: 'bi-bullseye',
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
    '$store.state.bulkGenerationRequests': {
      handler(requests) {
        if (requests && requests.length > 0) {
          const req = requests[0];
          if (req.type === 'error-bound') {
            this.handleErrorBoundBulkGeneration(req.payload);
          } else if (req.type === 'propagate') {
            this.handlePropagateParameter(req.payload);
          }
          this.$store.commit('clearBulkGenerationRequest', req.id);
        }
      },
      deep: true
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
    onSplitResize() {
      // Trigger layout recalculations for nested components/VTK canvas
      window.dispatchEvent(new Event('resize'));
      if (!this.nodes.length) {
        this.$nextTick(() => {
          this.initializeCanvasSize();
        });
      }
    },
    
    onWindowResize() {
      // Update canvas size when window is resized
      if (!this.nodes.length) {
        this.initializeCanvasSize();
      }
    },

    initializeCanvasSize() {
      // Calculate canvas size based on available pane space
      const paneEl = this.$refs.graphPane?.$el;
      if (!paneEl) return;
      
      const rect = paneEl.getBoundingClientRect();
      const availableWidth = Math.max(400, rect.width - 15);
      let availableHeight = rect.height;
      
      if (this.selectedNode) {
        // Properties card takes ~40% of height plus margin
        availableHeight = Math.max(400, rect.height * 0.6);
      } else {
        // No properties card, use full height minus card header and margins
        availableHeight = Math.max(400, rect.height - 60);
      }
      
      this.canvasSize.width = availableWidth;
      this.canvasSize.height = availableHeight;
    },
    canAddNodeType(type) {
      const nodeClass = NodeFactory.getClassByType(type);
      return nodeClass.canAdd(this.nodes);
    },
    clearSelection() {
      this.selectedNodeId = null;
      if (!this.nodes.length) {
        this.$nextTick(() => {
          this.initializeCanvasSize();
        });
      }
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
      } else if (type === 'correction') {
        if (defId === 'critical_points') node.editorComponent = markRaw(CriticalPointsCorrection);
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

      // Add error bound if present in node config or as defaults
      // For now, use some defaults if not found
      if (node.definitionId === 'sz3') {
        config.compressor_config['sz3:error_bound_mode_str'] = 'ABS';
        config.compressor_config['sz3:abs_error_bound'] = 1e-3;
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
      if (!baseNode) {
        this.$store.commit('setStatus', { type: 'danger', message: 'Base node not found in workspace.' });
        return;
      }

      const batchId = Date.now();
      values.forEach((val, index) => {
        // Store this derived config in the store as well for the ConfigGraph to see
        const derivedConfig = JSON.parse(JSON.stringify(this.baseConfigurations[baseConfigName]));
        derivedConfig.compressor_config[parameter] = val;
        this.$store.commit('addDerivedConfiguration', { 
          baseName: baseConfigName, 
          derivedName: `${baseNode.definitionId}-bulk-${batchId}-${index}`, 
          config: derivedConfig 
        });
      });

      this.$store.commit('setStatus', { type: 'success', message: `Generated ${values.length} variants for ${baseNode.label}.` });
    },

    handlePropagateParameter({ baseNodeId, parameter, values }) {
      // Similar to error bound but for other parameters
      // For now, let's treat it similarly or just show a message
      console.log('Propagating parameter from base node:', baseNodeId, parameter, values);
      this.$store.commit('setStatus', { type: 'info', message: 'Parameter propagation not fully implemented for data flow nodes yet.' });
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
      // Recalculate canvas size if empty since properties panel affects available space
      if (!this.nodes.length) {
        this.$nextTick(() => {
          this.initializeCanvasSize();
        });
      }
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

      // Perform node-specific cleanup/reverse operations
      node.onDestroy({ 
        store: this.$store,
        filterComponents: this.filterComponents,
      });

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
        // Ensure we have a data_key if possible
        if (!config.data_key && this.$store.state.dataset?.content) {
          const newKey = await this.computeDataKey();
          config.data_key = newKey;
          this.$store.commit('setFileData', { 
            dataset: { ...this.$store.state.dataset, data_key: newKey } 
          });
        }

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
          if (err?.response?.status === 404 && serverMsg?.includes('DATA_KEY_NOT_FOUND') && this.$store.state.dataset?.content) {
            this.setNodeStatus(nodeId, 'running', 'Uploading data to server cache...');
            
            const uploadForm = new FormData();
            uploadForm.append('metric_type', 'statistics'); // Dummy metric to trigger cache storage
            uploadForm.append('parameters', JSON.stringify({
              dimensions: config.dataset_meta.dimensions,
              precision: config.dataset_meta.precision
            }));
            uploadForm.append('data_key', config.data_key);
            const blob = new Blob([this.$store.state.dataset.content], { type: 'application/octet-stream' });
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
          sourceData = sourceNode.lastResult || (this.comparisonData ? this.comparisonData[sourceNode.id] : null);
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
        if (this.selectedNode) {
          minHeight = Math.max(400, rect.height * 0.6);
        } else {
          minHeight = Math.max(400, rect.height - 60);
        }
      }
      
      // Calculate required canvas size based on node positions
      let maxX = minWidth;
      let maxY = minHeight;
      
      this.nodes.forEach(node => {
        // Calculate dynamic node width based on type and state
        let nodeWidth = 420; // default max node width from CSS
        
        if (node.type === 'compressor' && node.modules && node.modules.length) {
          // Compressor nodes are narrower when collapsed
          nodeWidth = node.expanded ? 420 : 350;
        }
        
        // Calculate dynamic node height based on type and state
        let nodeHeight = 200; // base height
        
        if (node.type === 'compressor' && node.expanded && node.modules && node.modules.length) {
          // Each module box is ~60px
          // Add instruction text (~30px) and pipeline container padding (~20px)
          const moduleCount = node.modules.length;
          const moduleHeight = moduleCount * 60 + (moduleCount - 1) * 6; // 6px margin between modules
          nodeHeight = 150 + moduleHeight + 50; // base content + modules + padding
        } else if (node.type === 'compressor' && node.modules && node.modules.length) {
          // Collapsed view with module list
          const moduleCount = node.modules.length;
          nodeHeight = 180 + (moduleCount * 20); // base + list items
        }
        
        const rightEdge = (node.x || 0) + nodeWidth + 50; // 50px padding
        const bottomEdge = (node.y || 0) + nodeHeight + 50; // 50px padding
        
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
    describeModuleSelection(module) {
      if (!module || !module.value || !Object.keys(module.value).length) {
        return 'Not configured';
      }
      const [label] = Object.keys(module.value);
      return label || 'Configured';
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

    <Splitpanes class="default-theme w-100 h-100" :dbl-click-splitter="false" @resized="onSplitResize">
      <!-- Left: Node Palette -->
      <Pane :size="30" min-size="20" max-size="30" class="h-100 overflow-auto">
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

            <!-- Compression Modules -->
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
        <div class="work-area d-flex flex-column h-100">
          <div
            class="card shadow-sm canvas d-flex flex-column"
            :style="{ width: canvasSize.width + 'px' }"
            @dragover.prevent
            @drop="onCanvasDrop"
          >
            <div class="card-header d-flex align-items-center justify-content-between py-2">
              <span class="fw-semibold">Data Flow Graph</span>
              <small class="text-muted">Drag components from the left to compose a pipeline</small>
            </div>
            <div 
              ref="canvas"
              class="card-body p-0 position-relative flex-grow-1" 
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
                    <div v-if="node.lastRunAt">Last run: {{ formatTimestamp(node.lastRunAt) }}</div>
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
                    <div v-if="node.lastUpdatedAt" class="text-muted mt-2">Last updated: {{ formatTimestamp(node.lastUpdatedAt) }}</div>
                    <div v-if="node.description" class="text-muted small mt-2">{{ node.description }}</div>
                  </template>
                  <template v-else-if="node.type === 'correction'">
                    <div v-if="node.lastRunAt">Last run: {{ formatTimestamp(node.lastRunAt) }}</div>
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
            </div>
          </div>

          <div v-if="selectedNode" class="card shadow-sm mt-2 properties-card">
            <div class="card-header d-flex align-items-center justify-content-between py-2">
              <span class="fw-semibold">Properties</span>
              <button type="button" class="btn btn-sm btn-outline-secondary" title="Hide" @click="clearSelection">
                <i class="bi bi-x-lg"></i>
              </button>
            </div>
            <div class="card-body overflow-auto">
              <template v-if="selectedNode.type === 'source'">
                <keep-alive>
                  <InputDataset />
                </keep-alive>
              </template>

              <template v-else-if="selectedNode.type === 'filter'">
                <p v-if="selectedNode.description" class="text-muted small mb-1">
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
                      :focused-module-idx="selectedNode.selectedModuleIdx"
                      :modules="selectedNode.modules"
                      :status="selectedNode.status"
                      @pipeline-modules-updated="handlePipelineModulesUpdated"
                      @run-compressor="handleRunCompressor"
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
  min-height: 0; /* allow children to shrink and scroll inside */
}

.properties-card {
  flex: 0 1 auto; /* Don't grow, allow shrink, size based on content */
  max-height: 40%;
  display: flex;
  flex-direction: column;
}
.properties-card :deep(.card-body) {
  overflow-y: auto;
}

.df-node {
  position: absolute;
  display: inline-block;
  width: auto; /* allow node to expand to fit content */
  min-width: 180px;
  max-width: 420px; /* cap width to avoid overly wide nodes */
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
  max-width: 520px !important; /* Allow more width when expanded */
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
</style>
