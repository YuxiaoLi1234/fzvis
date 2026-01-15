
<script>
import InputDataset from '../InputDataset.vue';
import DataClipping from '../filter/DataClipping.vue';
import DataThresholding from '../filter/DataThresholding.vue';
import SZ3Pipeline from '../compressor/SZ3Pipeline.vue';
import { Splitpanes, Pane } from 'splitpanes';
import { NodeFactory } from '../../utils/nodeClasses';

export default {
  name: 'DataFlowWorkbench',
  components: { 
    InputDataset,
    DataClipping,
    DataThresholding,
    SZ3Pipeline,
    Splitpanes,
    Pane
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
          id: 'thresholding',
          label: 'Threshold',
          description: 'Filter data using lower/upper threshold values.',
          icon: 'bi-sliders',
        },
      ],
      // Modules imported from PipelineBrowser definitions
      availableModules: [
        {
          id: 'testing',
          label: 'Testing Module',
          description: 'A simple testing module that accepts two inputs and generates two outputs.',
          icon: 'bi-puzzle',
          inputCount: 2, 
          outputCount: 2,
        },
        // Example: Add more modules with different configurations
        {
          id: 'merger',
          label: 'Data Merger',
          description: 'Merges three data streams into one.',
          icon: 'bi-bezier2',
          inputCount: 3,
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
      ],
      // Compressors imported from PipelineBrowser definitions
      availableCompressors: [
        {
          id: 'sz3',
          label: 'SZ3 Compressor',
          description: 'A Modular Error-bounded Lossy Compression Framework.',
          icon: 'bi-cpu',
        },
      ],
      nodes: [],
      selectedNodeId: null,
      counters: { source: 0, filter: 0, module: 0, compressor: 0 },
      dragging: { active: false, nodeId: null, offsetX: 0, offsetY: 0 },
      paletteState: {
        filters: true,
        modules: true,
        compressors: true,
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
        show: false,
        nodeId: null,
        nodeLabel: '',
      },
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
  },

  watch: {
    datasetLoaded: {
      immediate: true,
      handler(loaded) {
        this.nodes.filter(n => n.type === 'source').forEach(n => {
          n.status = loaded ? 'ready' : 'empty';
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
      const availableWidth = Math.max(400, rect.width - 20);
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
      }

      const id = `${type}-${defId || 'inst'}-${this.counters[type] || Date.now()}`;
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
        node.editorComponent = InputDataset;
      } else if (type === 'filter') {
        if (defId === 'clipping') node.editorComponent = DataClipping;
        else if (defId === 'thresholding') node.editorComponent = DataThresholding;
        else node.editorComponent = null;
        node.status = 'pending';
      } else if (type === 'compressor') {
        if (defId === 'sz3') node.editorComponent = SZ3Pipeline;
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
    onNodeConfigChange(payload) {
      if (this.selectedNode) {
        // Sync the component's output back to the node's config
        this.selectedNode.config = { ...this.selectedNode.config, ...payload };
        console.log(`Node ${this.selectedNode.id} config updated:`, this.selectedNode.config);
      }
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
        // Add other context items here if needed in the future
      });

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
        empty: 'No Dataset',
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
      if (!this.selectedNode || this.selectedNode.type !== 'compression') return;
      this.selectedNode.modules = mods;
      this.selectedNode.lastUpdatedAt = Date.now();
      const ready = mods && mods.every(m => m?.value && Object.keys(m.value).length);
      this.selectedNode.status = ready ? 'ready' : 'pending';
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
        minWidth = Math.max(400, rect.width - 20);
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
        const nodeWidth = 420; // max node width from CSS
        const nodeHeight = 200; // estimated max node height
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
        <div class="card shadow-sm h-100">
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
                  <div class="d-flex align-items-center gap-2 flex-wrap">
                    <i :class="['bi', node.icon]" aria-hidden="true"></i>
                    <span class="fw-semibold">{{ node.label }}</span>
                    <span class="badge rounded-pill ms-1" :class="getStatusBadgeClass(node.status)">{{ getStatusLabel(node.status) }}</span>
                  </div>
                  <button type="button" class="btn btn-sm btn-outline-danger ms-2" title="Delete node" @click.stop="removeNode(node.id)">
                    <i class="bi bi-trash"></i>
                  </button>
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
                    <div class="mb-1">Status: <b>{{ getStatusLabel(node.status) }}</b></div>
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
                  <template v-else-if="node.type === 'compression'">
                    <div class="mb-1">Status: <b>{{ getStatusLabel(node.status) }}</b></div>
                    <div v-if="Array.isArray(node.modules) && node.modules.length">
                      <div class="fw-semibold mt-1">Modules</div>
                      <ul class="list-unstyled mb-0">
                        <li v-for="m in node.modules" :key="m.id" class="d-flex justify-content-between align-items-center">
                          <span>{{ m.label }}</span>
                          <span class="text-muted">{{ describeModuleSelection(m) }}</span>
                        </li>
                      </ul>
                    </div>
                    <div v-else>No module selections yet.</div>
                    <div v-if="node.lastUpdatedAt" class="text-muted mt-2">Last updated: {{ formatTimestamp(node.lastUpdatedAt) }}</div>
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
                      v-bind="selectedNode.props"
                      @filter-start="() => handleFilterStart(selectedNode.id)"
                      @filter-success="($event) => handleFilterSuccess(selectedNode.id, $event)"
                      @filter-error="($event) => handleFilterError(selectedNode.id, $event)"
                      @filter-invalid="($event) => handleFilterInvalid(selectedNode.id, $event)"
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

              <template v-else-if="selectedNode.type === 'compression'">
                <div class="mb-3" v-if="selectedNode.definitionId">
                  <label for="compressorSelection" class="form-label fw-semibold">Compressor</label>
                  <select
                    id="compressorSelection"
                    class="form-select"
                    :value="selectedNode.definitionId"
                    :disabled="availableCompressors.length <= 1"
                    @change="(e) => addNode('compressor', selectedNode.x, selectedNode.y, e.target.value)"
                  >
                    <option v-for="compressor in availableCompressors" :key="compressor.id" :value="compressor.id">
                      {{ compressor.label }}
                    </option>
                  </select>
                  <p class="text-muted small mt-2 mb-0">
                    {{ availableCompressors.find(c => c.id === selectedNode.definitionId)?.description || '' }}
                  </p>
                </div>
                <template v-if="selectedNode.editorComponent">
                  <keep-alive>
                    <component
                      :is="selectedNode.editorComponent"
                      :key="`compressor-${selectedNode.id}`"
                      @pipeline-modules-updated="handlePipelineModulesUpdated"
                    />
                  </keep-alive>
                </template>
                <p v-else class="text-muted small mb-0">No compressor UI available.</p>
                <p class="alert alert-light border small mt-3 mb-0" v-if="selectedNode.editorComponent">
                  Drag module options onto each stage. Once every stage has a selection the compressor will be marked as ready.
                </p>
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
  flex: 0 0 40%; /* occupy 40% of the right pane height */
  min-height: 0; /* critical for nested overflow to work in flex columns */
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
</style>
