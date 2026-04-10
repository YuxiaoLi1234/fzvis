<script>
import * as d3 from 'd3';
import { Modal } from 'bootstrap';
import Multiselect from 'vue-multiselect';
import axios from 'axios';

export default {
  name: 'ConfigGraph',
  props: {
    baseConfigurations: { type: Object, required: true },
    derivedConfigurations: { type: Object, required: true },
    savedConfigurations: { type: Object, required: true },
    compressorOptions: {
      type: Object,
      default: () => ({})
    },
    noCard: {
      type: Boolean,
      default: false
    }
  },
  components: {
    Multiselect,
  },
  emits: ['error-bound-bulk-generation', 'propagate-parameter', 'rename-derived-configuration'],

  data() {
    return {
      graphData: { nodes: [], links: [] },
      simulation: null,
      zoomBehavior: null,
      contextMenuTarget: null,
      selectedParameter: null,
      parameterValues: [],
      parameterValuesText: '',
      bulkSettings: {
        count: 5,
        minBound: 0.00001,
        maxBound: 0.1,
        distribution: 'linear',
      },
      bulkCustomValuesText: '',
      availableParameters: {},
      baseNodeParameters: {},
      propagateOptions: {},
      loading: false,
      configStatus: {}, // Status for the node: idle, running, success, error
      running: false,   // Spinner overlay
      largeGraphModalOpen: false,
      compressionResults: {},
      nodePositions: {}, // Store node positions by id
      prevNodeIds: [],   // Track previous node ids for change detection
      selectedConfigIds: [],
      mainLinkSelection: null,
      mainNodeSelection: null,
      largeLinkSelection: null,
      largeNodeSelection: null,
      largeGraphTransform: null,
      activeFilterKey: null,
      filterCompressorId: '',
      filterOptionKey: '',
      filterOptionValue: '',
      propagateTargets: [],
    };
  },
  computed: {
    selectedLabel() {
      const count = this.selectedConfigIds?.length || 0;
      if (count === 0) return null;
      if (count > 1) return `${count} configs`;
      const id = this.selectedConfigIds[0];
      const node = this.graphData?.nodes?.find(n => n.id === id);
      return node?.name || id;
    },
    selectedBaseOnly() {
      const ids = this.selectedConfigIds || [];
      if (!ids.length) return false;
      return ids.every(id => {
        const node = this.graphData?.nodes?.find(n => n.id === id);
        return node && node.type === 'base';
      });
    },
    renameTargetId() {
      const ids = this.selectedConfigIds || [];
      if (ids.length === 1) {
        const node = this.graphData?.nodes?.find(n => n.id === ids[0]);
        if (node) return node.id;
      }
      if (this.contextMenuTarget) return this.contextMenuTarget.id;
      return null;
    },
    renameTargetType() {
      const ids = this.selectedConfigIds || [];
      if (ids.length === 1) {
        const node = this.graphData?.nodes?.find(n => n.id === ids[0]);
        return node?.type;
      }
      return this.contextMenuTarget?.type;
    },
    propagateOptionsForSelected() {
      if (!this.selectedParameter) return [];
      const available = this.availableParameters?.[this.selectedParameter];
      if (available?.options && Array.isArray(available.options)) {
        return available.options;
      }
      const compressorId = this.contextMenuTarget?.config?.compressor_id;
      return this.compressorOptions?.[compressorId]?.Detail?.[this.selectedParameter] || [];
    },
    availableCompressorIds() {
      const ids = new Set();
      Object.values(this.baseConfigurations || {}).forEach(cfg => {
        if (cfg?.compressor_id) ids.add(cfg.compressor_id);
      });
      Object.values(this.savedConfigurations || {}).forEach(cfg => {
        if (cfg?.compressor_id) ids.add(cfg.compressor_id);
      });
      return Array.from(ids).sort();
    },
    availableOptionKeyOptions() {
      const compressorId = this.filterCompressorId;
      if (compressorId === 'sz3') {
        return this.getSz3FilterModules().map(m => ({ label: m.label, value: m.key }));
      }
      if (compressorId === 'zfp') {
        return [
          { label: 'Accuracy', value: 'zfp:accuracy' },
          { label: 'Rate', value: 'zfp:rate' },
          { label: 'Precision', value: 'zfp:precision' },
        ];
      }
      const keys = new Set();
      const addKeys = (cfg) => {
        const cc = cfg?.compressor_config || {};
        Object.keys(cc).forEach(k => keys.add(k));
      };
      Object.values(this.baseConfigurations || {}).forEach(addKeys);
      Object.values(this.savedConfigurations || {}).forEach(addKeys);
      return Array.from(keys).sort().map(k => ({ label: this.getFormattedKey(k), value: k }));
    },
    availableOptionValueOptions() {
      if (!this.filterOptionKey) return [];
      const compressorId = this.filterCompressorId;
      if (compressorId === 'sz3') {
        const mod = this.getSz3FilterModules().find(m => m.key === this.filterOptionKey);
        if (mod) {
          return mod.values.map(v => ({ label: v.label, value: String(v.value) }));
        }
      }
      const values = new Set();
      const addValues = (cfg) => {
        if (!cfg?.compressor_config) return;
        if (this.filterCompressorId && cfg.compressor_id !== this.filterCompressorId) return;
        if (this.filterOptionKey in cfg.compressor_config) {
          values.add(String(cfg.compressor_config[this.filterOptionKey]));
        }
      };
      Object.values(this.baseConfigurations || {}).forEach(addValues);
      Object.values(this.savedConfigurations || {}).forEach(addValues);
      return Array.from(values).sort().map(v => ({ label: v, value: v }));
    }
  },
  
  mounted() {
    this.$nextTick(() => {
      this.initializeGraph();
      this.setupResizeObserver();
    });
  },

  beforeUnmount() {
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
    }
    // Clean up any existing tooltips
    this.hideTooltip();
  },

  watch: {
    baseConfigurations: {
      handler() {
        this.queueGraphRefresh();
      },
      deep: true,
    },
    derivedConfigurations: {
      handler() {
        this.queueGraphRefresh();
      },
      deep: true,
    },
    savedConfigurations: {
      handler() {
        this.queueGraphRefresh();
      },
      deep: true,
    },
    filterOptionKey() {
      this.filterOptionValue = '';
    },
  },
  
  methods: {
    queueGraphRefresh() {
      this.$nextTick(() => {
        this.updateGraphData();
      });
    },
    isNodeSelected(nodeId) {
      return (this.selectedConfigIds || []).includes(nodeId)
        || this.contextMenuTarget?.id === nodeId;
    },
    clearActiveSelection() {
      this.contextMenuTarget = null;
      this.selectedConfigIds = [];
      this.hideTooltip();
      this.renderGraph();
      if (this.largeGraphModalOpen) {
        this.renderLargeGraph();
      }
    },
    updateForcePositions() {
      if (this.mainLinkSelection) {
        this.mainLinkSelection
          .attr('x1', d => d.source.x)
          .attr('y1', d => d.source.y)
          .attr('x2', d => d.target.x)
          .attr('y2', d => d.target.y);
      }
      if (this.mainNodeSelection) {
        this.mainNodeSelection
          .attr('transform', d => `translate(${d.x},${d.y})`);
      }
      if (this.largeLinkSelection) {
        this.largeLinkSelection
          .attr('x1', d => d.source.x)
          .attr('y1', d => d.source.y)
          .attr('x2', d => d.target.x)
          .attr('y2', d => d.target.y);
      }
      if (this.largeNodeSelection) {
        this.largeNodeSelection
          .attr('transform', d => `translate(${d.x},${d.y})`);
      }
    },
    applyRadialClusterLayout(graphData, width, height) {
      if (!graphData || !graphData.nodes || !graphData.links) return;
      const bases = graphData.nodes.filter(n => n.type === 'base');
      const nodesById = new Map(graphData.nodes.map(n => [n.id, n]));
      const derivedByBase = new Map(bases.map(b => [b.id, []]));
      const assignedDerived = new Set();

      const centerX = width / 2;
      const centerY = height / 2;
      const minDim = Math.min(width, height);
      // Normalize links and parentage using link source/target first
      graphData.links.forEach(link => {
        const sourceId = typeof link.source === 'string' ? link.source : link.source?.id;
        const targetId = typeof link.target === 'string' ? link.target : link.target?.id;
        const sourceNode = nodesById.get(sourceId);
        const targetNode = nodesById.get(targetId);
        if (!sourceNode || !targetNode) return;
        if (sourceNode.type === 'base' && targetNode.type === 'derived') {
          if (!derivedByBase.has(sourceNode.id)) derivedByBase.set(sourceNode.id, []);
          derivedByBase.get(sourceNode.id).push(targetNode);
          targetNode.baseName = sourceNode.id;
          targetNode.parentId = sourceNode.id;
          assignedDerived.add(targetNode.id);
        }
        link.source = sourceNode;
        link.target = targetNode;
      });
      // Fallback: attach any derived nodes without link-based assignment
      graphData.nodes.forEach(n => {
        if (n.type !== 'derived' || assignedDerived.has(n.id)) return;
        const baseId = n.baseName;
        if (baseId && derivedByBase.has(baseId)) {
          derivedByBase.get(baseId).push(n);
          n.parentId = baseId;
          assignedDerived.add(n.id);
        }
      });

      const totalDerived = bases.reduce((sum, b) => sum + (derivedByBase.get(b.id)?.length || 0), 0);
      const weights = bases.map(b => {
        const count = derivedByBase.get(b.id)?.length || 0;
        if (!b.showDerived || count === 0) return 1;
        return 1 + Math.min(6, Math.sqrt(count));
      });
      const totalWeight = weights.reduce((sum, w) => sum + w, 0) || 1;
      const baseRadius = minDim * (0.24 + Math.min(0.18, totalDerived * 0.002));
      const baseRingMin = minDim * 0.08;
      const baseRingMax = minDim * 0.22;
      let cursor = -Math.PI / 2;

      bases.forEach((base, i) => {
        const slice = (2 * Math.PI * weights[i]) / totalWeight;
        const angle = cursor + slice / 2;
        cursor += slice;
        const bx = centerX + baseRadius * Math.cos(angle);
        const by = centerY + baseRadius * Math.sin(angle);
        base.x = bx;
        base.y = by;
        base.vx = 0;
        base.vy = 0;

        const derived = derivedByBase.get(base.id) || [];
        const count = derived.length;
        if (!count) return;
        if (!base.showDerived) {
          derived.forEach(d => {
            d.x = bx;
            d.y = by;
            d.vx = 0;
            d.vy = 0;
          });
          return;
        }
        const arcLen = Math.max(40, baseRadius * slice);
        const localRadiusCap = Math.max(baseRingMin, Math.min(baseRingMax, arcLen * 0.35));
        const baseLocalRadius = Math.min(localRadiusCap, baseRingMin + Math.min(120, count * 6));
        const span = Math.max(Math.PI / 3, Math.min(Math.PI * 1.5, slice * 0.9));
        const arcLenRing = Math.max(40, span * baseLocalRadius);
        const maxPerRing = Math.max(3, Math.floor(arcLenRing / 26));
        const ringCount = Math.ceil(count / maxPerRing);
        const ringSpacing = 18;
        const maxRingRadius = Math.min(baseRingMax + ringSpacing * (ringCount - 1), minDim * 0.3);
        const startRadius = Math.max(baseRingMin, Math.min(baseLocalRadius, maxRingRadius - ringSpacing * (ringCount - 1)));
        let placed = 0;
        for (let r = 0; r < ringCount; r += 1) {
          const ringRadius = startRadius + ringSpacing * r;
          const remaining = count - placed;
          const nodesInRing = Math.min(maxPerRing, remaining);
          for (let j = 0; j < nodesInRing; j += 1) {
            const idx = placed + j;
            const t = nodesInRing === 1 ? 0.5 : j / (nodesInRing - 1);
            const a = angle - span / 2 + span * t;
            const d = derived[idx];
            d.x = bx + ringRadius * Math.cos(a);
            d.y = by + ringRadius * Math.sin(a);
            d.vx = 0;
            d.vy = 0;
          }
          placed += nodesInRing;
        }
      });

      // Update links to use fixed positions
      graphData.links.forEach(link => {
        if (typeof link.source === 'string') {
          link.source = graphData.nodes.find(n => n.id === link.source) || link.source;
        }
        if (typeof link.target === 'string') {
          link.target = graphData.nodes.find(n => n.id === link.target) || link.target;
        }
      });

      // Freeze simulation if available
      if (this.simulation) {
        this.simulation.stop();
      }
    },
    deleteNode() {
      if (!this.contextMenuTarget) return;
      if (!confirm(`Are you sure you want to delete configuration '${this.contextMenuTarget.name}'?`)) return;

      this.deleteConfigById(this.contextMenuTarget.id, this.contextMenuTarget.type, this.contextMenuTarget.baseName);

      this.hideContextMenu();
    },

    generateBulkValues() {
      const values = [];
      const { count, minBound, maxBound, distribution } = this.bulkSettings;
      if (distribution === 'custom') {
        return (this.bulkCustomValuesText || '')
          .split(',')
          .map(v => Number(v.trim()))
          .filter(v => Number.isFinite(v) && v > 0);
      }
      
      const total = Math.max(1, Number(count) || 1);
      for (let i = 0; i < total; i++) {
        let value;
        if (distribution === 'linear') {
          value = total === 1 ? minBound : minBound + (i / (total - 1)) * (maxBound - minBound);
        } else if (distribution === 'exponential') {
          const minLog = Math.log10(minBound);
          const maxLog = Math.log10(maxBound);
          const logValue = total === 1 ? minLog : minLog + (i / (total - 1)) * (maxLog - minLog);
          value = Math.pow(10, logValue);
        } else if (distribution === 'random') {
          value = minBound + Math.random() * (maxBound - minBound);
        }
        values.push(parseFloat(value.toFixed(8)));
      }
      
      return values;
    },

    getFormattedKey(key) {
      return key
        .replace(/^.*?:/, "")               // remove namespace prefix like `sz3:` or `pressio:`
        .replace(/_str$/, "")               // remove `_str` suffix
        // .replace(/_mode$/, "")              // remove `_mode` suffix
        .replace(/_algo$/, "")              // remove `_algo` suffix
        .replace("_error_bound", " Error Bound") // special handling
        .replace(/_/g, " ")                 // underscores to spaces
        .replace(/\b\w/g, c => c.toUpperCase()); // capitalize words
    },

    getNodeTooltipHtml(d) {
      let html = `<div><strong>${d.name}</strong></div>`;
      const status = this.configStatus[d.id] || 'idle';
      // Show error info if status is error
      if (status === 'error') {
        let errorMsg = '';
        // Try to get error message from store's comparisonData
        const comparisonData = this.$store.state.comparisonData || {};
        if (comparisonData[d.id] && comparisonData[d.id].error) {
          errorMsg = comparisonData[d.id].error;
        } else if (comparisonData[d.id]) {
          errorMsg = JSON.stringify(comparisonData[d.id], null, 2);
        }
        html += `<div class='small text-danger'><strong>Error:</strong> ${errorMsg || 'Unknown error.'}</div>`;
      }
      if (d.type === 'base') {
        html += `<div class='small text-success'><strong>Derived: ${d.derivedCount}</strong></div>`;
        if (d.config && d.config.compressor_config) {
          html += `<div class='small text-info'>Base Configuration:</div>`;
          Object.entries(d.config.compressor_config).forEach(([key, value]) => {
            html += `<div class='small'><strong>${this.getFormattedKey(key)}:</strong> ${value}</div>`;
          });
          return html;
        }
      }
      if (d.type === 'derived') {
        const baseParamKey = this.baseNodeParameters[d?.baseName];
        if (baseParamKey) {
          let paramValue = '';
          if (d.config && d.config.compressor_config && baseParamKey in d.config.compressor_config) {
            paramValue = d.config.compressor_config[baseParamKey];
          } else if (d.config && d.config.early_config && baseParamKey in d.config.early_config) {
            paramValue = d.config.early_config[baseParamKey];
          }
          html += `<div class='small text-info'>Propagated Parameter:</div>`;
          html += `<div class='small'><strong>${this.getFormattedKey(baseParamKey)}:</strong> ${paramValue}</div>`;
          return html;
        }
        if (d.config && d.config.compressor_config) {
          html += `<div class='small text-info'>Derived Configuration:</div>`;
          Object.entries(d.config.compressor_config).forEach(([key, value]) => {
            html += `<div class='small'><strong>${this.getFormattedKey(key)}:</strong> ${value}</div>`;
          });
          return html;
        }
      }
      // fallback: no compressor_config found
      html += `<div class='small text-danger'>No compressor_config found</div>`;
      html += `<pre class='small'>${d.config ? JSON.stringify(d.config, null, 2) : ''}</pre>`;
      return html;
    },

    hideContextMenu() {
      this.contextMenuTarget = null;
      this.propagateTargets = [];
    },
    deleteConfigById(id, typeHint = null, baseNameHint = null) {
      if (!id) return;
      if (this.$store) {
        this.$store.commit('removeComparisonData', id);
      }
      const isBase = typeHint === 'base' || (this.baseConfigurations && this.baseConfigurations[id]);
      if (isBase) {
        if (this.derivedConfigurations[id]) {
          Object.keys(this.derivedConfigurations[id]).forEach(derivedId => {
            if (this.$store) {
              this.$store.commit('removeComparisonData', derivedId);
            }
            if (this.savedConfigurations[derivedId]) {
              delete this.savedConfigurations[derivedId];
              if (this.compressionResults[derivedId]) {
                delete this.compressionResults[derivedId];
              }
            }
          });
          delete this.derivedConfigurations[id];
        }
        delete this.baseConfigurations[id];
      } else {
        const baseName = baseNameHint || Object.keys(this.derivedConfigurations || {}).find(b => this.derivedConfigurations[b]?.[id]);
        if (baseName && this.derivedConfigurations[baseName] && this.derivedConfigurations[baseName][id]) {
          delete this.derivedConfigurations[baseName][id];
          if (Object.keys(this.derivedConfigurations[baseName]).length === 0) {
            delete this.derivedConfigurations[baseName];
          }
        }
      }

      if (this.savedConfigurations[id]) {
        delete this.savedConfigurations[id];
      }
      if (this.compressionResults[id]) {
        delete this.compressionResults[id];
      }
    },
    deleteSelected() {
      const ids = this.selectedConfigIds || [];
      if (!ids.length) return;
      if (!confirm(`Delete ${ids.length} selected configuration(s)?`)) return;
      ids.forEach(id => {
        const node = this.graphData?.nodes?.find(n => n.id === id);
        this.deleteConfigById(id, node?.type, node?.baseName);
      });
      this.selectedConfigIds = [];
      this.hideContextMenu();
    },
    promptRenameBase() {
      const targetId = this.renameTargetId;
      const targetType = this.renameTargetType;
      if (!targetId) return;

      const currentName = targetId;
      const promptText = targetType === 'base' ? 'Rename base configuration:' : 'Rename derived configuration:';
      const nextName = window.prompt(promptText, currentName);
      if (nextName == null) return;

      const trimmed = nextName.trim();
      if (!trimmed) {
        alert('Name cannot be empty.');
        return;
      }
      if (trimmed === currentName) return;

      // Check if name already exists in saved configurations
      if (this.savedConfigurations && this.savedConfigurations[trimmed]) {
        alert(`Name '${trimmed}' already exists. Please choose a unique name.`);
        return;
      }

      if (targetType === 'base') {
        // Rename base configuration
        if (this.$store) {
          this.$store.commit('renameBaseConfiguration', { oldName: currentName, newName: trimmed });
        }
      } else if (targetType === 'derived') {
        // Rename derived configuration
        const node = this.graphData?.nodes?.find(n => n.id === currentName);
        const baseName = node?.baseName;
        if (!baseName) {
          alert('Could not find base configuration for this derived node.');
          return;
        }

        // Emit event to parent to handle prop mutations
        this.$emit('rename-derived-configuration', {
          oldName: currentName,
          newName: trimmed,
          baseName: baseName
        });

        // Update compression results (local data)
        if (this.compressionResults[currentName]) {
          this.compressionResults[trimmed] = this.compressionResults[currentName];
          delete this.compressionResults[currentName];
        }

        // Update config status (local data)
        if (this.configStatus[currentName]) {
          this.configStatus[trimmed] = this.configStatus[currentName];
          delete this.configStatus[currentName];
        }

        // Update store comparison data
        if (this.$store) {
          const comparisonData = this.$store.state.comparisonData || {};
          if (comparisonData[currentName]) {
            this.$store.commit('setComparisonData', {
              ...comparisonData,
              [trimmed]: comparisonData[currentName]
            });
            this.$store.commit('removeComparisonData', currentName);
          }
        }
      }

      // Update selectedConfigIds
      if (this.selectedConfigIds?.length) {
        this.selectedConfigIds = this.selectedConfigIds.map(id => id === currentName ? trimmed : id);
      }

      // Update contextMenuTarget
      if (this.contextMenuTarget?.id === currentName) {
        this.contextMenuTarget = { ...this.contextMenuTarget, id: trimmed, name: trimmed };
      }

      // Force graph update
      this.updateGraphData();
    },

    initializeGraph() {
      if (!this.$refs.graphContainer || !this.$refs.graphSvg) return;
      const width = this.$refs.graphContainer.clientWidth || 600;
      const height = this.$refs.graphContainer.clientHeight || 300;
      this.initializeGraphWithDimensions(width, height);
    },

    initializeGraphWithDimensions(width, height) {
      const svg = d3.select(this.$refs.graphSvg)
        .attr('width', width)
        .attr('height', height);
      svg.selectAll('*').remove();
      const mainGroup = svg.append('g').attr('class', 'main-group');
      mainGroup.append('g').attr('class', 'links');
      mainGroup.append('g').attr('class', 'nodes');
      this.zoomBehavior = d3.zoom()
        .scaleExtent([0.1, 4])
        .on('zoom', event => mainGroup.attr('transform', event.transform));
      svg.call(this.zoomBehavior);
      svg.on('click', event => {
        if (event.target === svg.node()) {
          this.clearActiveSelection();
        }
      });
      this.simulation = d3.forceSimulation()
        .force('link', d3.forceLink()
          .id(d => d.id)
          .distance(link => {
            // Increase distance for base-to-derived links
            if (
              (link.source.type === 'base' && link.target.type === 'derived') ||
              (link.source.type === 'derived' && link.target.type === 'base')
            ) {
              return 80;
            }
            return 30;
          })
          .strength(link => {
            if (
              (link.source.type === 'base' && link.target.type === 'derived') ||
              (link.source.type === 'derived' && link.target.type === 'base')
            ) {
              return 0.8;
            }
            return 0.3;
          })
        )
        .force('charge', d3.forceManyBody().strength(d => {
          const n = this.graphData.nodes.length || 1;
          const base = -Math.min(140, 20 + n * 2);
          return d.type === 'derived' ? base * 1.6 : base;
        }))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(d => d.type === 'base' ? 28 : 18))
        .force('x', d3.forceX(d => {
          const baseCount = Math.max(1, this.graphData.nodes.filter(n => n.type === 'base').length);
          const idx = d.groupIndex ?? 0;
          return ((idx + 1) / (baseCount + 1)) * width;
        }).strength(d => d.type === 'base' ? 0.25 : 0.1))
        .force('y', d3.forceY(d => {
          const offset = d.type === 'derived' ? (d.derivedOffset || 0) : 0;
          return height / 2 + offset;
        }).strength(d => d.type === 'base' ? 0.06 : 0.2));
      this.updateGraphData();
    },

    isBulkConfigValid() {
      const { minBound, maxBound, distribution, count } = this.bulkSettings;
      if (distribution === 'custom') {
        const values = (this.bulkCustomValuesText || '')
          .split(',')
          .map(v => Number(v.trim()))
          .filter(v => Number.isFinite(v));
        return values.length > 0;
      }
      return Number.isFinite(minBound) && Number.isFinite(maxBound) && maxBound > minBound && Number(count) >= 1;
    },

    openLargeGraphModal() {
      this.hideTooltip();
      const modal = document.getElementById('largeGraphModal');
      if (modal) {
        const modalInstance = Modal.getOrCreateInstance(modal);
        // Add event listeners for modal events
        modal.addEventListener('hidden.bs.modal', () => {
          this.hideTooltip();
          this.largeGraphModalOpen = false;
        });
        modal.addEventListener('shown.bs.modal', () => {
          this.largeGraphModalOpen = true;
          this.renderLargeGraph();
        }, { once: true });
        modalInstance.show();
      }
    },

    openPropagateModal() {
      this.hideTooltip();
      const modal = document.getElementById('propagateModal');
      if (modal) {
        this.availableParameters = {};
        this.propagateOptions = {};
        this.parameterValuesText = '';
        this.bulkCustomValuesText = '';
        if (this.contextMenuTarget && this.contextMenuTarget.config) {
          const config = this.contextMenuTarget.config;
          const compressorConfig = config.compressor_config || {};
          const compressorId = config.compressor_id;
          Object.entries(compressorConfig).forEach(([key, value]) => {
            if (typeof value === 'number' && Number.isFinite(value)) {
              if (key === 'sz3:quant_bin_size' || key === 'pressio:nthreads') return;
              this.availableParameters[this.getFormattedKey(key)] = { key, type: 'number' };
            }
          });
          if (compressorId === 'sz3') {
            const modeKey = 'sz3:error_bound_mode_str';
            const formatted = this.getFormattedKey(modeKey);
            let options = this.compressorOptions?.[compressorId]?.Detail?.[formatted] || [];
            if (!options.length) {
              options = [
                { id: 'ABS', label: 'ABS', value: 'ABS' },
                { id: 'REL', label: 'REL', value: 'REL' },
                { id: 'PSNR', label: 'PSNR', value: 'PSNR' },
              ];
            }
            this.availableParameters[formatted] = { key: modeKey, type: 'enum', options };
          } else if (compressorId === 'zfp') {
            const makeOptions = (values, type) => (
              values.map(v => ({
                id: v,
                label: String(v),
                type,
                value: v
              }))
            );
            const uniqSorted = (values) => {
              const out = Array.from(new Set(values.filter(v => Number.isFinite(v))));
              out.sort((a, b) => a - b);
              return out;
            };
            if (typeof compressorConfig['zfp:accuracy'] === 'number') {
              const v = compressorConfig['zfp:accuracy'];
              const values = uniqSorted([v * 0.5, v * 0.75, v, v * 1.5, v * 2].filter(x => x > 0));
              const label = 'Accuracy';
              this.availableParameters[label] = { key: 'zfp:accuracy', type: 'number', options: makeOptions(values, 'zfp:accuracy') };
            } else if (typeof compressorConfig['zfp:rate'] === 'number') {
              const v = compressorConfig['zfp:rate'];
              const values = uniqSorted([v - 2, v - 1, v, v + 1, v + 2].map(x => Math.max(0.1, x)));
              const label = 'Rate';
              this.availableParameters[label] = { key: 'zfp:rate', type: 'number', options: makeOptions(values, 'zfp:rate') };
            } else if (typeof compressorConfig['zfp:precision'] === 'number') {
              const v = compressorConfig['zfp:precision'];
              const values = uniqSorted([v - 4, v - 2, v, v + 2, v + 4].map(x => Math.max(1, Math.round(x))));
              const label = 'Precision';
              this.availableParameters[label] = { key: 'zfp:precision', type: 'number', options: makeOptions(values, 'zfp:precision') };
            }
          }
          Modal.getOrCreateInstance(modal).show();
        } else {
          // Show alert for no available parameters
          const alertElement = document.getElementById('compressorAlert');
          const alertMessage = document.getElementById('compressorAlertMessage');
          if (alertElement && alertMessage) {
            alertMessage.textContent = 'No parameters available for propagation on this configuration.';
            alertElement.className = 'alert alert-warning alert-dismissible fade show mt-2';
            alertElement.style.display = 'block';
            setTimeout(() => {
              alertElement.classList.remove('show');
            }, 3000);
          }
        }
      }
    },

    propagateParameter() {
      const selected = this.availableParameters?.[this.selectedParameter];
      if (!selected) return;
      let values = [];
      if (selected.type === 'number') {
        if (this.parameterValuesText) {
          values = this.parameterValuesText
            .split(',')
            .map(v => Number(v.trim()))
            .filter(v => Number.isFinite(v));
        } else {
          values = this.parameterValues;
        }
      } else {
        values = (this.parameterValues || []).map(v => v?.value ?? v?.id ?? v?.label ?? v);
      }
      if (!values || values.length === 0) return;
      const targets = this.propagateTargets.length
        ? this.propagateTargets
        : (this.contextMenuTarget?.id ? [this.contextMenuTarget.id] : []);
      targets.forEach(baseId => {
        this.$emit('propagate-parameter', {
          baseNodeId: baseId,
          parameter: selected.key,
          values
        });
        this.baseNodeParameters[baseId] = selected.key;
      });
      this.selectedParameter = null;
      this.parameterValues = [];
      this.parameterValuesText = '';
      this.propagateTargets = [];
      this.hideContextMenu();
    },
    bulkGenerateParameter() {
      const selected = this.availableParameters?.[this.selectedParameter];
      if (!selected || selected.type !== 'number') return;
      const values = this.generateBulkValues();
      if (!values || values.length === 0) return;
      const targets = this.propagateTargets.length
        ? this.propagateTargets
        : (this.contextMenuTarget?.id ? [this.contextMenuTarget.id] : []);
      const isSz3ErrorBound = this.contextMenuTarget?.config?.compressor_id === 'sz3'
        && selected.key
        && selected.key.includes('error_bound')
        && !selected.key.includes('mode');
      targets.forEach(baseId => {
        if (isSz3ErrorBound) {
          this.$emit('error-bound-bulk-generation', {
            baseConfigName: baseId,
            parameter: selected.key,
            values
          });
        } else {
          this.$emit('propagate-parameter', {
            baseNodeId: baseId,
            parameter: selected.key,
            values
          });
        }
        this.baseNodeParameters[baseId] = selected.key;
      });
      this.selectedParameter = null;
      this.parameterValues = [];
      this.parameterValuesText = '';
      this.bulkCustomValuesText = '';
      this.propagateTargets = [];
      this.hideContextMenu();
    },

    // Generalized node click handler
    onNodeClick(event, d) {
      event.preventDefault();
      event.stopPropagation();
      this.hideTooltip();
      const toggleSelection = event.ctrlKey || event.metaKey;

      if (toggleSelection) {
        const nextSelected = new Set(this.selectedConfigIds || []);
        if (nextSelected.has(d.id)) {
          nextSelected.delete(d.id);
        } else {
          nextSelected.add(d.id);
        }
        this.selectedConfigIds = Array.from(nextSelected);
      } else {
        this.selectedConfigIds = [d.id];
      }

      this.contextMenuTarget = this.isNodeSelected(d.id)
        ? d
        : (this.graphData?.nodes?.find(n => this.selectedConfigIds.includes(n.id)) || null);

      // If fullscreen modal is open, set focus to it so context menu condition is met
      this.$nextTick(() => {
        const modal = this.$refs.largeGraphModal;
        if (modal && modal.classList.contains('show')) {
          modal.focus();
        }
      });
      if (d.type === 'base') {
        d.showDerived = !d.showDerived;
        this.updateGraphData();
        return;
      }

      this.renderGraph();
      if (this.largeGraphModalOpen) {
        this.renderLargeGraph();
      }
    },

    async submitConfigurations() {
      const alertBox = document.getElementById("compressorAlert");
      const alertMessage = document.getElementById("compressorAlertMessage");
      const fileData = this.$store.state.dataset?.content;
      if (!fileData) {
        if (alertBox && alertMessage) {
          alertBox.classList.remove("alert-success", "alert-secondary");
          alertBox.classList.add("alert-danger", "show");
          alertMessage.textContent = "No dataset selected!";
        }
        return;
      }
      // Set all configs to running
      Object.keys(this.$props.savedConfigurations).forEach(key => {
        this.configStatus[key] = "running";
      });
      this.running = true;
      this.renderGraph();
      // Only render large graph if modal is open
      if (this.largeGraphModalOpen) {
        this.renderLargeGraph();
      }
      if (alertBox && alertMessage) {
        alertBox.classList.remove("alert-danger", "alert-success");
        alertBox.classList.add("alert-secondary", "show");
        alertMessage.textContent = "Processing...";
      }
      // Submit each config as a separate request in parallel
      const configEntries = Object.entries(this.$props.savedConfigurations);
      this.compressionResults = {};

      let dataKey = this.$store.state.dataset?.data_key || this.$store.state.dataset?.name || null;
      if (!dataKey && this.$store.state.dataset?.content) {
        dataKey = crypto.randomUUID();
        this.$store.commit('setFileData', {
          dataset: { ...this.$store.state.dataset, data_key: dataKey }
        });
      }
      const datasetMeta = {
        name: this.$store.state.dataset?.name || null,
        dimensions: this.$store.state.dataset?.dimensions || null,
        precision: this.$store.state.dataset?.precision || null,
        endianness: this.$store.state.dataset?.endianness || 'little',
      };

      await Promise.all(configEntries.map(async ([key, config]) => {
        let formData = new FormData();
        const configPayload = {
          ...config,
          data_key: config.data_key || dataKey,
          dataset_meta: config.dataset_meta || datasetMeta,
        };
        formData.append("get_options", 0);
        formData.append("configurations", JSON.stringify({ [key]: configPayload }));
        try {
          const executeCompression = async () => {
            const body = new FormData();
            body.append("get_options", 0);
            body.append("configurations", JSON.stringify({ [key]: configPayload }));
            return await axios.post(`/api/indexlist`, body);
          };
          let response;
          try {
            response = await executeCompression();
          } catch (err) {
            const serverMsg = err?.response?.data?.error;
            if (err?.response?.status === 404 && serverMsg?.includes('DATA_KEY_NOT_FOUND') && this.$store.state.dataset?.content) {
              const uploadForm = new FormData();
              uploadForm.append('metric_type', 'statistics');
              uploadForm.append('parameters', JSON.stringify({
                dimensions: configPayload.dataset_meta?.dimensions,
                precision: configPayload.dataset_meta?.precision,
                endianness: configPayload.dataset_meta?.endianness
              }));
              uploadForm.append('data_key', configPayload.data_key);
              const blob = new Blob([this.$store.state.dataset.content], { type: 'application/octet-stream' });
              uploadForm.append('data', blob, configPayload.dataset_meta?.name || 'data.bin');
              await axios.post('/api/analysis/compute/upload', uploadForm);
              response = await executeCompression();
            } else {
              throw err;
            }
          }
          const result = response.data[key] || response.data;
          
          // Fetch the actual decompressed binary data using the data_key
          if (result.data_key) {
            try {
              const dataResp = await axios.get(`/api/decompressed/${result.data_key}`, {
                responseType: 'arraybuffer'
              });
              result.decp_data = dataResp.data;
            } catch (err) {
              console.error(`Failed to fetch decompressed data for ${key}:`, err);
            }
          }

          this.configStatus[key] = "success";
          this.compressionResults[key] = result;
        } catch (error) {
          this.configStatus[key] = "error";
          this.compressionResults[key] = { error: error.response ? error.response.data.error : error.toString() };
        }
        this.renderGraph();
        if (this.largeGraphModalOpen) {
          this.renderLargeGraph();
        }
      }));
      // Update store with all results
      console.log("Configuration results:", Object.keys(this.compressionResults));
      this.$store.commit("setComparisonData", this.compressionResults);
      if (alertBox && alertMessage) {
        if (Object.values(this.configStatus).every(s => s === "success")) {
          alertBox.classList.remove("alert-danger", "alert-secondary");
          alertBox.classList.add("alert-success", "show");
          alertMessage.textContent = "Compression executed successfully!";
          setTimeout(() => { alertBox.classList.remove("show"); }, 6000);
        } else {
          alertBox.classList.remove("alert-success", "alert-secondary");
          alertBox.classList.add("alert-danger", "show");
          alertMessage.textContent = "Some compressions failed. See node status.";
          setTimeout(() => { alertBox.classList.remove("show"); }, 8000);
        }
      }
      this.running = false;
      this.renderGraph();
      if (this.largeGraphModalOpen) {
        this.renderLargeGraph();
      }
    },

    renderGraph() {
      const svg = d3.select(this.$refs.graphSvg);
      const mainGroup = svg.select('.main-group');
      const selectedIds = new Set([
        ...(this.selectedConfigIds || []),
        ...(this.contextMenuTarget?.id ? [this.contextMenuTarget.id] : [])
      ]);
      // Save current node ids
      const currentNodeIds = this.graphData.nodes.map(n => n.id).sort();
      this.nodePositions = {};
      this.simulation.nodes(this.graphData.nodes);
      this.simulation.force('link').links(this.graphData.links);
      const link = mainGroup.select('.links')
        .selectAll('line')
        .data(this.graphData.links)
        .join('line')
        .attr('stroke', '#999')
        .attr('stroke-opacity', 0.6)
        .attr('stroke-width', 2);
      const node = mainGroup.select('.nodes')
        .selectAll('g')
        .data(this.graphData.nodes)
        .join('g')
        .attr('class', d => `node${selectedIds.has(d.id) ? ' node-selected' : ''}`)
        .style('cursor', 'pointer');
      node.selectAll('*').remove();
      node.append('circle')
        .attr('r', d => d.type === 'base' ? 20 : 12)
        .attr('fill', d => {
          const status = this.configStatus[d.id] || 'idle';
          if (status === 'running') return 'rgba(0,123,255,0.5)';
          if (status === 'success') return '#28a745';
          if (status === 'error') return '#dc3545';
          return '#6c757d';
        })
        .attr('stroke', d => selectedIds.has(d.id) ? '#0d6efd' : '#fff')
        .attr('stroke-width', d => selectedIds.has(d.id) ? 4 : 2)
        .attr('opacity', d => this.matchesActiveFilter(d) ? 1 : 0.15)
        .style('filter', d => selectedIds.has(d.id) ? 'drop-shadow(0 0 8px rgba(13,110,253,0.6))' : null)
        .style('transition', 'stroke-width 120ms ease, filter 120ms ease, opacity 120ms ease');
      node.append('text')
        .attr('text-anchor', 'middle')
        .attr('dy', '.35em')
        .attr('font-size', '9px')
        .attr('fill', 'white')
        .text(d => d.name.length > 6 ? d.name.substring(0, 6) + '...' : d.name);
      // Add badge for base nodes with derivedCount > 0
      const badgeNodes = node.filter(d => d.type === 'base' && d.derivedCount > 0);
      badgeNodes.append('circle')
        .attr('cx', 13)
        .attr('cy', -13)
        .attr('r', 7)
        .attr('fill', '#dc3545')
        .attr('class', 'derived-badge');
      badgeNodes.append('text')
        .attr('x', 13)
        .attr('y', -13)
        .attr('text-anchor', 'middle')
        .attr('dy', '.35em')
        .attr('font-size', '8px')
        .attr('fill', 'white')
        .attr('class', 'derived-badge-text')
        .text(d => d.derivedCount);

      // Add plain HTML tooltip functionality
      node
        .on('mouseover', (event, d) => {
          this.showTooltip(event, d);
        })
        .on('mousemove', (event,) => {
          this.updateTooltipPosition(event);
        })
        .on('mouseout', () => {
          this.hideTooltip();
        })
        .on('click', this.onNodeClick);
      this.mainLinkSelection = link;
      this.mainNodeSelection = node;
      this.simulation.on('tick', () => {
        this.updateForcePositions();
      });
      this.simulation.alpha(0.9).restart();
      // Update prevNodeIds
      this.prevNodeIds = currentNodeIds;
    },

    renderLargeGraph() {
      const width = this.$refs.largeGraphContainer.clientWidth || window.innerWidth;
      const height = this.$refs.largeGraphContainer.clientHeight || window.innerHeight;
      const svg = d3.select(this.$refs.largeGraphSvg)
        .attr('width', width)
        .attr('height', height);
      const selectedIds = new Set([
        ...(this.selectedConfigIds || []),
        ...(this.contextMenuTarget?.id ? [this.contextMenuTarget.id] : [])
      ]);
      svg.selectAll('*').remove();
      const mainGroup = svg.append('g').attr('class', 'main-group');
      mainGroup.append('g').attr('class', 'links');
      mainGroup.append('g').attr('class', 'nodes');
      const zoomBehavior = d3.zoom()
        .scaleExtent([0.1, 4])
        .on('zoom', event => {
          mainGroup.attr('transform', event.transform);
          this.largeGraphTransform = event.transform;
        });
      svg.call(zoomBehavior);
      svg.on('click', event => {
        if (event.target === svg.node()) {
          this.clearActiveSelection();
        }
      });
      const initialTransform = this.largeGraphTransform || d3.zoomIdentity;
      mainGroup.attr('transform', initialTransform);
      svg.call(zoomBehavior.transform, initialTransform);
      // positions already set via radial layout
      const link = mainGroup.select('.links')
        .selectAll('line')
        .data(this.graphData.links)
        .join('line')
        .attr('stroke', '#999')
        .attr('stroke-opacity', 0.6)
        .attr('stroke-width', 2);
      const node = mainGroup.select('.nodes')
        .selectAll('g')
        .data(this.graphData.nodes)
        .join('g')
        .attr('class', d => `node${selectedIds.has(d.id) ? ' node-selected' : ''}`)
        .style('cursor', 'pointer');
      node.selectAll('*').remove();
      node.append('circle')
        .attr('r', d => d.type === 'base' ? 24 : 14)
        .attr('fill', d => {
          const status = this.configStatus[d.id] || 'idle';
          if (status === 'running') return 'rgba(0,123,255,0.5)';
          if (status === 'success') return '#28a745';
          if (status === 'error') return '#dc3545';
          return '#6c757d';
        })
        .attr('stroke', d => selectedIds.has(d.id) ? '#0d6efd' : '#fff')
        .attr('stroke-width', d => selectedIds.has(d.id) ? 4 : 2)
        .attr('opacity', d => this.matchesActiveFilter(d) ? 1 : 0.15)
        .style('filter', d => selectedIds.has(d.id) ? 'drop-shadow(0 0 10px rgba(13,110,253,0.65))' : null)
        .style('transition', 'stroke-width 120ms ease, filter 120ms ease, opacity 120ms ease');
      node.append('text')
        .attr('text-anchor', 'middle')
        .attr('dy', '.35em')
        .attr('font-size', '10px')
        .attr('fill', 'white')
        .text(d => d.name.length > 12 ? d.name.substring(0, 12) + '...' : d.name);
      const badgeNodes = node.filter(d => d.type === 'base' && d.derivedCount > 0);
      badgeNodes.append('circle')
        .attr('cx', 13)
        .attr('cy', -13)
        .attr('r', 7)
        .attr('fill', '#dc3545')
        .attr('class', 'derived-badge');
      badgeNodes.append('text')
        .attr('x', 13)
        .attr('y', -13)
        .attr('text-anchor', 'middle')
        .attr('dy', '.35em')
        .attr('font-size', '8px')
        .attr('fill', 'white')
        .attr('class', 'derived-badge-text')
        .text(d => d.derivedCount);
      // Add plain HTML tooltip functionality
      node
        .on('mouseover', (event, d) => {
          this.showTooltip(event, d);
        })
        .on('mousemove', (event,) => {
          this.updateTooltipPosition(event);
        })
        .on('mouseout', () => {
          this.hideTooltip();
        })
        .on('click', this.onNodeClick);
      this.largeLinkSelection = link;
      this.largeNodeSelection = node;
      this.updateForcePositions();
    },

    setupResizeObserver() {
      if (!this.$refs.graphContainer) return;
      this.resizeObserver = new ResizeObserver(entries => {
        // Use requestAnimationFrame to avoid "ResizeObserver loop completed with undelivered notifications"
        window.requestAnimationFrame(() => {
          if (!entries.length || !this.$refs.graphContainer) return;
          for (let entry of entries) {
            const { width, height } = entry.contentRect;
            if (width > 0 && height > 0 && this.simulation) {
              this.initializeGraphWithDimensions(width, height);
            }
          }
        });
      });
      this.resizeObserver.observe(this.$refs.graphContainer);
    },

    updateGraphData() {
      this.loading = true;
      this.$nextTick(() => {
        const nodes = [];
        const links = [];
        // Preserve showDerived state for each base node
        const prevNodes = this.graphData.nodes || [];
        Object.keys(this.baseConfigurations).forEach((baseName, idx) => {
          const prevNode = prevNodes.find(n => n.id === baseName && n.type === 'base');
          nodes.push({
            id: baseName,
            type: 'base',
            name: baseName,
            config: this.baseConfigurations[baseName],
            derivedCount: Object.keys(this.derivedConfigurations[baseName] || {}).length,
            showDerived: prevNode ? prevNode.showDerived : false,
            groupIndex: idx
          });
        });
        Object.entries(this.derivedConfigurations).forEach(([baseName, derivedConfigs]) => {
          const baseNode = nodes.find(n => n.id === baseName);
          if (baseNode && baseNode.showDerived) {
            if (!this.baseConfigurations[baseName]) return;
            const derivedEntries = Object.entries(derivedConfigs);
            const derivedCount = derivedEntries.length;
            derivedEntries.forEach(([derivedName, derivedConfig], idx) => {
              if (!this.baseConfigurations[baseName]) return;
              const offset = (idx - (derivedCount - 1) / 2) * 22;
              nodes.push({
                id: derivedName,
                type: 'derived',
                name: derivedName,
                config: derivedConfig,
                baseName: baseName,
                groupIndex: baseNode.groupIndex,
                derivedOffset: offset,
                derivedIndex: idx,
                derivedCount
              });
              links.push({ source: baseName, target: derivedName });
            });
          }
        });
        this.graphData = { nodes, links };
        this.renderGraph();
        // Only render large graph if modal is open
        if (this.largeGraphModalOpen) {
          this.renderLargeGraph();
        }
        this.loading = false;
      });
    },

    // Tooltip methods for plain HTML tooltips
    showTooltip(event, d) {
      // Remove any existing tooltip
      this.hideTooltip();
      
      // Create tooltip element
      const tooltip = document.createElement('div');
      tooltip.id = 'graph-tooltip';
      tooltip.style.cssText = `
        position: absolute;
        background: rgba(0, 0, 0, 0.9);
        color: white;
        padding: 8px 12px;
        border-radius: 4px;
        font-size: 12px;
        pointer-events: none;
        z-index: 1080;
        max-width: 300px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
      `;
      
      // Set tooltip content
      tooltip.innerHTML = this.getNodeTooltipHtml(d);
      
      // Add to document
      document.body.appendChild(tooltip);
      
      // Position tooltip
      this.updateTooltipPosition(event);
    },

    updateTooltipPosition(event) {
      const tooltip = document.getElementById('graph-tooltip');
      if (tooltip) {
        const x = event.pageX + 10;
        const y = event.pageY - 10;
        
        // Adjust position if tooltip would go off screen
        const rect = tooltip.getBoundingClientRect();
        const finalX = (x + rect.width > window.innerWidth) ? event.pageX - rect.width - 10 : x;
        const finalY = (y < 0) ? event.pageY + 20 : y;
        
        tooltip.style.left = finalX + 'px';
        tooltip.style.top = finalY + 'px';
      }
    },

    hideTooltip() {
      const tooltip = document.getElementById('graph-tooltip');
      if (tooltip) {
        tooltip.remove();
      }
    },
    matchesActiveFilter(node) {
      if (!this.activeFilterKey) return true;
      const config = node?.config || null;
      if (!config) return false;
      if (this.activeFilterKey === 'custom') {
        if (this.filterCompressorId && config.compressor_id !== this.filterCompressorId) return false;
        if (this.filterOptionKey) {
          const cc = config.compressor_config || {};
          if (!(this.filterOptionKey in cc)) return false;
          if (this.filterOptionValue && String(cc[this.filterOptionKey]) !== String(this.filterOptionValue)) return false;
        }
        return true;
      }
      return true;
    },
    getSz3FilterModules() {
      return [
        {
          key: 'sz3:algorithm_str',
          label: 'Predictor',
          values: [
            { label: 'Bypass', value: 'ALGO_NOPRED' },
            { label: 'Interpolation', value: 'ALGO_INTERP' },
            { label: 'Lorenzo', value: 'ALGO_INTERP_LORENZO' },
            { label: 'Adaptive', value: 'ALGO_LORENZO_REG' },
          ],
        },
        {
          key: 'sz3:quant_bin_size',
          label: 'Quantizer',
          values: [
            { label: 'Linear-scaling', value: 65536 },
          ],
        },
        {
          key: 'sz3:encoder',
          label: 'Encoder',
          values: [
            { label: 'Bypass', value: '0' },
            { label: 'Huffman', value: '1' },
            { label: 'Arithmetic', value: '2' },
          ],
        },
        {
          key: 'sz3:lossless',
          label: 'Lossless',
          values: [
            { label: 'Bypass', value: '0' },
            { label: 'Zstd', value: '1' },
          ],
        },
      ];
    },
    applyFilter() {
      this.activeFilterKey = 'custom';
      this.renderGraph();
      if (this.largeGraphModalOpen) {
        this.renderLargeGraph();
      }
    },
    clearFilter() {
      this.activeFilterKey = null;
      this.renderGraph();
      if (this.largeGraphModalOpen) {
        this.renderLargeGraph();
      }
    },
    selectAllMatching() {
      this.activeFilterKey = 'custom';
      const selected = this.graphData.nodes
        .filter(n => this.matchesActiveFilter(n))
        .map(n => n.id);
      this.selectedConfigIds = selected;
      this.renderGraph();
      if (this.largeGraphModalOpen) {
        this.renderLargeGraph();
      }
    },
    clearSelection() {
      this.clearActiveSelection();
    },
    openPropagateForSelection() {
      const baseTargets = (this.selectedConfigIds || [])
        .map(id => this.graphData?.nodes?.find(n => n.id === id))
        .filter(n => n && n.type === 'base');
      if (!baseTargets.length) return;
      const compressorId = baseTargets[0]?.config?.compressor_id;
      const mixed = baseTargets.some(n => n?.config?.compressor_id !== compressorId);
      if (mixed) {
        const alertElement = document.getElementById('compressorAlert');
        const alertMessage = document.getElementById('compressorAlertMessage');
        if (alertElement && alertMessage) {
          alertMessage.textContent = 'Select base configurations with the same compressor to propagate.';
          alertElement.className = 'alert alert-warning alert-dismissible fade show mt-2';
          alertElement.style.display = 'block';
          setTimeout(() => {
            alertElement.classList.remove('show');
          }, 3000);
        }
        return;
      }
      this.propagateTargets = baseTargets.map(n => n.id);
      this.contextMenuTarget = baseTargets[0];
      this.openPropagateModal();
    },

  }
}
</script>

<template>
  <div :class="noCard ? 'h-100 d-flex flex-column' : 'card border-primary mt-2'">
    <div v-if="!noCard" class="card-header d-flex justify-content-between align-items-center">
      <h6 class="mb-0">Configuration Graph</h6>
      <div class="d-flex align-items-center">
        <span class="badge bg-info me-2">{{ Object.keys(baseConfigurations).length }}</span>
        <button class="btn btn-outline-primary btn-sm" @click="openLargeGraphModal" title="Open Fullscreen View">
          <i class="bi bi-arrows-fullscreen"></i>
        </button>
      </div>
    </div>
    <div :class="noCard ? 'flex-grow-1 p-2 position-relative d-flex flex-column config-graph-body' : 'card-body p-2'">
      <!-- Floating action button for fullscreen if noCard -->
      <button 
        v-if="noCard" 
        class="btn btn-sm btn-outline-primary border-0 shadow-sm position-absolute top-0 end-0 m-2" 
        style="z-index: 10; background: rgba(255,255,255,0.8); backdrop-filter: blur(2px);"
        @click="openLargeGraphModal" 
        title="Open Fullscreen View"
      >
        <i class="bi bi-arrows-fullscreen"></i>
      </button>
      <div class="d-flex flex-wrap align-items-center gap-2 mb-2">
        <span class="text-muted small">Filter:</span>
        <select v-model="filterCompressorId" class="form-select form-select-sm" style="width: 140px;">
          <option value="">All compressors</option>
          <option v-for="id in availableCompressorIds" :key="id" :value="id">{{ id }}</option>
        </select>
        <select v-model="filterOptionKey" class="form-select form-select-sm" style="width: 200px;">
          <option value="">Any option</option>
          <option v-for="opt in availableOptionKeyOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
        <select v-model="filterOptionValue" class="form-select form-select-sm" style="width: 180px;" :disabled="!filterOptionKey">
          <option value="">Any value</option>
          <option v-for="val in availableOptionValueOptions" :key="val.value" :value="val.value">{{ val.label }}</option>
        </select>
        <button type="button" class="btn btn-sm btn-outline-secondary" @click="applyFilter">Apply Filter</button>
        <button type="button" class="btn btn-sm btn-outline-secondary" @click="clearFilter">Clear Filter</button>
        <span class="text-muted small ms-2">Selection:</span>
        <button type="button" class="btn btn-sm btn-outline-primary" @click="selectAllMatching">Select Matching</button>
        <button type="button" class="btn btn-sm btn-outline-primary" @click="clearSelection">Clear Selection</button>
      </div>
      <div
        id="configuration-graph"
        ref="graphContainer"
        class="config-graph-canvas"
        :style="{ minHeight: noCard ? '0': '320px', width: '100%', border: noCard ? 'none' : '1px solid #dee2e6', borderRadius: '0.35rem', cursor: 'grab', position: 'relative' }"
      >
        <svg ref="graphSvg" width="100%" height="100%"></svg>
        <div
          v-if="loading"
          class="graph-loading-overlay"
          style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: rgba(255,255,255,0.6); z-index: 10; display: flex; align-items: center; justify-content: center; pointer-events: all;">
          <span class="spinner-border text-primary" role="status" aria-hidden="true"></span>
          <span class="ms-2">Rendering...</span>
        </div>
      </div>
      <div v-if="Object.keys(baseConfigurations).length === 0" class="text-center text-muted mt-3">
        <p class="mb-0">No saved configurations yet.</p>
      </div>
    </div>
    
    <div class="card-footer">
      <!-- Context menu in footer -->
      <div
        v-if="selectedConfigIds.length || contextMenuTarget"
        class="context-menu-footer mb-2"
        :style="{ position: $refs.largeGraphModal && $refs.largeGraphModal.contains(document.activeElement) ? 'absolute' : 'static', zIndex: 2000, left: contextMenuTarget && $refs.largeGraphModal && $refs.largeGraphModal.contains(document.activeElement) ? '30px' : undefined, top: contextMenuTarget && $refs.largeGraphModal && $refs.largeGraphModal.contains(document.activeElement) ? '30px' : undefined }"
      >
        <div id="node-context-menu" class="d-flex align-items-center flex-wrap gap-2">
          <span class="text-muted small">
            Selected: <strong>{{ selectedLabel || contextMenuTarget?.name }}</strong>
          </span>
          <div class="vr"></div>
          <button
            class="btn btn-sm btn-outline-primary"
            :disabled="selectedConfigIds.length ? !selectedBaseOnly : (contextMenuTarget?.type !== 'base')"
            @click="selectedConfigIds.length ? openPropagateForSelection() : openPropagateModal()"
          >
            <i class="bi bi-arrow-repeat me-1"></i>Propagate
          </button>
          <button
            class="btn btn-sm btn-outline-danger"
            @click="selectedConfigIds.length ? deleteSelected() : deleteNode()"
          >
            <i class="bi bi-trash me-1"></i>Remove
          </button>
          <button
            class="btn btn-sm btn-outline-secondary"
            :disabled="!renameTargetId"
            @click="promptRenameBase"
          >
            <i class="bi bi-pencil-square me-1"></i>Rename
          </button>
        </div>
      </div>
      
      <!-- Configuration graph area -->
      <div class="text-center">
        <button
          type="button"
          class="btn btn-primary w-60"
          @click="submitConfigurations"
          :disabled="Object.keys($props.savedConfigurations).length === 0 || running"
        >
          <span v-if="running">
            <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
            Running...
          </span>
          <span v-else>
            Run All {{ Object.keys($props.savedConfigurations).length }} Configurations
          </span>
        </button>
      </div>
    </div>

  </div>

  <!-- Alert message box -->
  <div id="compressorAlert" class="alert alert-dismissible fade mt-2" role="alert" tabindex="-1">
    <span id="compressorAlertMessage">Placeholder</span>
  </div>

  <teleport to="body">
    <div id="largeGraphModal" class="modal fade" tabindex="-1" aria-labelledby="largeGraphModalLabel" aria-hidden="true" style="z-index: 2000;">
      <div class="modal-dialog modal-fullscreen">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="largeGraphModalLabel">Configuration Graph - Fullscreen View</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body p-0 overflow-hidden">
            <div id="large-configuration-graph" ref="largeGraphContainer" style="width: 100%; height: 100%; cursor: grab;">
              <svg ref="largeGraphSvg" width="100%" height="100%"></svg>
            </div>
          </div>
          <div class="modal-footer">
            <div class="w-100 mb-2">
              <div class="d-flex flex-wrap align-items-center gap-2">
                <span class="text-muted small">Filter:</span>
                <select v-model="filterCompressorId" class="form-select form-select-sm" style="width: 140px;">
                  <option value="">All compressors</option>
                  <option v-for="id in availableCompressorIds" :key="id" :value="id">{{ id }}</option>
                </select>
                <select v-model="filterOptionKey" class="form-select form-select-sm" style="width: 200px;">
                  <option value="">Any option</option>
                  <option v-for="opt in availableOptionKeyOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                </select>
                <select v-model="filterOptionValue" class="form-select form-select-sm" style="width: 180px;" :disabled="!filterOptionKey">
                  <option value="">Any value</option>
                  <option v-for="val in availableOptionValueOptions" :key="val.value" :value="val.value">{{ val.label }}</option>
                </select>
                <button type="button" class="btn btn-sm btn-outline-secondary" @click="applyFilter">Apply Filter</button>
                <button type="button" class="btn btn-sm btn-outline-secondary" @click="clearFilter">Clear Filter</button>
                <span class="text-muted small ms-2">Selection:</span>
                <button type="button" class="btn btn-sm btn-outline-primary" @click="selectAllMatching">Select Matching</button>
                <button type="button" class="btn btn-sm btn-outline-primary" @click="clearSelection">Clear Selection</button>
              </div>
            </div>
            <div v-if="selectedConfigIds.length || contextMenuTarget" class="context-menu-footer mb-2 w-100">
              <div id="node-context-menu-fullscreen" class="d-flex align-items-center flex-wrap gap-2">
                <span class="text-muted small">Selected: <strong>{{ selectedLabel || contextMenuTarget?.name }}</strong></span>
                <div class="vr"></div>
                <button
                  class="btn btn-sm btn-outline-primary"
                  :disabled="selectedConfigIds.length ? !selectedBaseOnly : (contextMenuTarget?.type !== 'base')"
                  @click="selectedConfigIds.length ? openPropagateForSelection() : openPropagateModal()"
                >
                  <i class="bi bi-arrow-repeat me-1"></i>Propagate
                </button>
                <button
                  class="btn btn-sm btn-outline-danger"
                  @click="selectedConfigIds.length ? deleteSelected() : deleteNode()"
                >
                  <i class="bi bi-trash me-1"></i>Remove
                </button>
                <button
                  class="btn btn-sm btn-outline-secondary"
                  :disabled="!renameTargetId"
                  @click="promptRenameBase"
                >
                  <i class="bi bi-pencil-square me-1"></i>Rename
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div id="propagateModal" class="modal fade" tabindex="-1" aria-labelledby="propagateModalLabel" aria-hidden="true" style="z-index: 2100;">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="propagateModalLabel">Propagate Parameter</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body" v-if="contextMenuTarget">
            <label>Select a parameter to propagate:</label>
            <select v-model="selectedParameter" class="form-select" @change="parameterValues = []; parameterValuesText = '';">
              <option
                v-for="label in Object.keys(availableParameters)"
                :key="label"
                :value="label"
              >
                {{ label }}
              </option>
            </select>
            <div v-if="selectedParameter && availableParameters[selectedParameter]?.type === 'number'" class="mt-3">
              <hr>
              <strong>Bulk Generate Values</strong>
              <form>
                <div class="mb-2">
                  <div class="form-floating">
                    <input type="number" id="numConfigs-tele" class="form-control" v-model="bulkSettings.count" min="1" max="1000" placeholder="Number of Configurations">
                    <label for="numConfigs-tele">Number of Configurations</label>
                  </div>
                </div>
                <div class="mb-2">
                  <div class="form-floating">
                    <select id="generationType-tele" class="form-select" v-model="bulkSettings.distribution">
                      <option value="linear">Linear Distribution</option>
                      <option value="exponential">Exponential Distribution</option>
                      <option value="random">Random Distribution</option>
                      <option value="custom">Custom Values</option>
                    </select>
                    <label for="generationType-tele">Generation Type</label>
                  </div>
                </div>
                <div v-if="bulkSettings.distribution !== 'custom'" class="mb-2">
                  <div class="form-floating">
                    <input type="number" id="minBound-tele" class="form-control" v-model="bulkSettings.minBound" step="0.00001" placeholder="Min Error Bound">
                    <label for="minBound-tele">Min Value</label>
                  </div>
                </div>
                <div v-if="bulkSettings.distribution !== 'custom'" class="mb-2">
                  <div class="form-floating">
                    <input type="number" id="maxBound-tele" class="form-control" v-model="bulkSettings.maxBound" step="0.00001" placeholder="Max Error Bound">
                    <label for="maxBound-tele">Max Value</label>
                  </div>
                </div>
                <div v-if="bulkSettings.distribution === 'custom'" class="mb-2">
                  <label class="form-label">Custom values (comma-separated)</label>
                  <input
                    type="text"
                    class="form-control"
                    v-model="bulkCustomValuesText"
                    placeholder="e.g. 0.01, 0.001, 0.0001"
                  >
                </div>
              </form>
            </div>
            <div v-else-if="selectedParameter">
              <label class="mt-2">Value to propagate:</label>
              <template v-if="availableParameters[selectedParameter]?.type === 'number'">
                <input
                  type="text"
                  class="form-control"
                  v-model="parameterValuesText"
                  placeholder="Comma-separated numeric values, e.g. 0.001, 0.002"
                >
                <div v-if="propagateOptionsForSelected.length" class="form-text">
                  Suggested: {{ propagateOptionsForSelected.map(o => o.label).join(', ') }}
                </div>
              </template>
              <template v-else>
                <multiselect
                  v-model="parameterValues"
                  :options="propagateOptionsForSelected"
                  :multiple="true"
                  :searchable="true"
                  :placeholder="'Select values'"
                  :close-on-select="false"
                  label="label"
                  track-by="id"
                  class="mb-2"
                />
                <div v-if="propagateOptionsForSelected.length === 0" class="text-muted small">
                  No propagation values available for this parameter.
                </div>
              </template>
            </div>
          </div>
          <div class="modal-footer d-flex justify-content-between">
            <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancel</button>
            <button
              v-if="selectedParameter && availableParameters[selectedParameter]?.type === 'number'"
              type="button"
              class="btn btn-primary"
              data-bs-dismiss="modal"
              :disabled="!isBulkConfigValid"
              @click="bulkGenerateParameter"
            >
              Bulk Generate
            </button>
            <button
              v-else
              type="button"
              class="btn btn-primary"
              data-bs-dismiss="modal"
              @click="propagateParameter"
              :disabled="!selectedParameter || (availableParameters[selectedParameter]?.type === 'number' ? !parameterValuesText : !parameterValues || (Array.isArray(parameterValues) && parameterValues.length === 0))"
            >
              Propagate
            </button>
          </div>
        </div>
      </div>
    </div>
  </teleport>
</template>

<style scoped>
.config-graph-body {
  min-height: 0;
}

.config-graph-canvas {
  flex: 1 1 auto;
  min-height: 0;
}
</style>

<style src="vue-multiselect/dist/vue-multiselect.min.css"></style>
