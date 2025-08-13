<script>
import * as d3 from 'd3';
import { Modal, Tooltip } from 'bootstrap';
import Multiselect from 'vue-multiselect';

export default {
  name: 'ConfigGraph',
  props: {
    baseConfigurations: { type: Object, required: true },
    derivedConfigurations: { type: Object, required: true },
    savedConfigurations: { type: Object, required: true },
    compressorOptions: { type: Object, required: false, default: () => ({}) },
  },
  components: {
    Multiselect,
  },
  emits: ['run-all-configurations', 'error-bound-bulk-generation', 'propagate-parameter'],

  data() {
    return {
      graphData: { nodes: [], links: [] },
      simulation: null,
      zoomBehavior: null,
      contextMenuTarget: null,
      selectedParameter: null,
      parameterValues: [],
      bulkSettings: {
        count: 10,
        minBound: 0.00001,
        maxBound: 0.001,
        distribution: 'linear',
      },
      availableParameters: {},
      baseNodeParameters: {},
      loading: false,
    };
  },
  
  mounted() {
    this.$nextTick(() => {
      this.initializeGraph();
      this.setupResizeObserver();
    });
  },

  beforeUnmount() {
    // Dispose of all tooltips before unmounting
    if (this.$refs.graphContainer) {
      Array.from(this.$refs.graphContainer.querySelectorAll('[data-bs-toggle="tooltip"]'))
        .forEach(el => {
          try {
            const tip = Tooltip.getInstance(el);
            if (tip) {
              tip.dispose();
            }
          } catch (error) {
            console.warn('Tooltip disposal error during unmount:', error);
          }
        });
    }
    
    if (this.$refs.largeGraphContainer) {
      Array.from(this.$refs.largeGraphContainer.querySelectorAll('[data-bs-toggle="tooltip"]'))
        .forEach(el => {
          try {
            const tip = Tooltip.getInstance(el);
            if (tip) {
              tip.dispose();
            }
          } catch (error) {
            console.warn('Large graph tooltip disposal error during unmount:', error);
          }
        });
    }
    
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
    }
  },

  watch: {
    savedConfigurations: {
      handler() {
        this.$nextTick(() => {
          this.updateGraphData();
        });
      },
      deep: true,
    },
  },
  
  methods: {
    deleteNode() {
      if (!this.contextMenuTarget) return;
      if (!confirm(`Are you sure you want to delete configuration '${this.contextMenuTarget.name}'?`)) return;

      // Remove from baseConfigurations and all its derived configs
      if (this.contextMenuTarget.type === "base" && this.baseConfigurations[this.contextMenuTarget.id]) {
        if (this.derivedConfigurations[this.contextMenuTarget.id]) {
          Object.keys(this.derivedConfigurations[this.contextMenuTarget.id]).forEach(derivedId => {
            if (this.savedConfigurations[derivedId]) {
              delete this.savedConfigurations[derivedId];
            }
          });
          delete this.derivedConfigurations[this.contextMenuTarget.id];
        }
        delete this.baseConfigurations[this.contextMenuTarget.id];
      }

      // Remove from derived configurations
      if (this.contextMenuTarget.type === "derived") {
        const baseName = this.contextMenuTarget.baseName;
        if (this.derivedConfigurations[baseName] && this.derivedConfigurations[baseName][this.contextMenuTarget.id]) {
          delete this.derivedConfigurations[baseName][this.contextMenuTarget.id];
          // If no more derived configs for this base, remove the base key
          if (Object.keys(this.derivedConfigurations[baseName]).length === 0) {
            delete this.derivedConfigurations[baseName];
          }
        }
      }

      // Remove from saved configurations
      if (this.savedConfigurations[this.contextMenuTarget.id]) {
        delete this.savedConfigurations[this.contextMenuTarget.id];
      }

      this.hideContextMenu();
    },

    editDetailInfo() {
      this.$emit('edit-detailed-info', this.contextMenuTarget);
      this.hideContextMenu();
    },

    generateBulkConfigurations() {
      const { node, parameter } = {
        node: this.contextMenuTarget,
        parameter: this.selectedParameter
      };

      if (node?.type === 'base' && parameter) {
        const values = this.generateErrorBoundValues();
        this.$emit('error-bound-bulk-generation', {
          baseConfigName: node.id,
          parameter: this.availableParameters[parameter],
          values
        });
        this.baseNodeParameters[node.id] = this.availableParameters[parameter];
      }

      this.hideContextMenu();
    },

    generateErrorBoundValues() {
      const values = [];
      const { count, minBound, maxBound, distribution } = this.bulkSettings;
      
      for (let i = 0; i < count; i++) {
        let value;
        if (distribution === 'linear') {
          value = minBound + (i / (count - 1)) * (maxBound - minBound);
        } else if (distribution === 'exponential') {
          const minLog = Math.log10(minBound);
          const maxLog = Math.log10(maxBound);
          const logValue = minLog + (i / (count - 1)) * (maxLog - minLog);
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
      this.simulation = d3.forceSimulation()
        .force('link', d3.forceLink()
          .id(d => d.id)
          .distance(link => {
            // Increase distance for base-to-derived links
            if (
              (link.source.type === 'base' && link.target.type === 'derived') ||
              (link.source.type === 'derived' && link.target.type === 'base')
            ) {
              return 50; // <-- Set your desired distance here
            }
            return 10; // Default for other links
          })
        )
        .force('charge', d3.forceManyBody().strength(-20))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(d => d.type === 'base' ? 20 : 6));
      this.updateGraphData();
    },

    isBulkConfigValid() {
      const { minBound, maxBound } = this.bulkSettings;
      return minBound > 0 && maxBound > minBound;
    },

    openLargeGraphModal() {
      const modal = document.getElementById('largeGraphModal');
      if (modal) {
        Modal.getOrCreateInstance(modal).show();
      }
    },

    openPropagateModal() {
      const modal = document.getElementById('propagateModal');
      if (modal) {
        this.availableParameters = {};
        if (this.contextMenuTarget && this.contextMenuTarget.config) {
          const compressorConfig = this.contextMenuTarget.config.compressor_config || {};
          Object.keys(compressorConfig).forEach(val => {
            this.availableParameters[this.getFormattedKey(val)] = val;
          });
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

    promoteToBase() {
      // Emit event to parent for promoting to base
      this.$emit('promote-to-base', this.contextMenuTarget);
      this.hideContextMenu();
    },

    propagateParameter() {
      // Emit event to parent with propagation details
      this.$emit('propagate-parameter', {
        baseNodeId: this.contextMenuTarget.id,
        parameter: this.selectedParameter,
        values: this.parameterValues
      });
      this.baseNodeParameters[this.contextMenuTarget.id] = this.availableParameters[this.selectedParameter];
      this.selectedParameter = null;
      this.parameterValues = [];
      this.hideContextMenu();
    },

    // Generalized node click handler
    onNodeClick(event, d) {
      event.preventDefault();
      event.stopPropagation();
      // Toggle context menu if same node is clicked
      if (this.contextMenuTarget && this.contextMenuTarget.id === d.id) {
        this.contextMenuTarget = null;
        return;
      }
      this.contextMenuTarget = d;
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
      }
    },

    renderGraph() {
      const svg = d3.select(this.$refs.graphSvg);
      const mainGroup = svg.select('.main-group');
      
      // Dispose of existing tooltips before updating the graph
      if (this.$refs.graphContainer) {
        Array.from(this.$refs.graphContainer.querySelectorAll('[data-bs-toggle="tooltip"]'))
          .forEach(el => {
            try {
              const tip = Tooltip.getInstance(el);
              if (tip) {
                tip.dispose();
              }
            } catch (error) {
              console.warn('Tooltip disposal error:', error);
            }
          });
      }
      
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
        .attr('class', 'node');
      node.selectAll('*').remove();
      node.append('circle')
        .attr('r', d => d.type === 'base' ? 20 : 12)
        .attr('fill', '#6c757d')
        .attr('stroke', '#fff')
        .attr('stroke-width', 2);
      node.append('text')
        .attr('text-anchor', 'middle')
        .attr('dy', '.35em')
        .attr('font-size', '9px')
        .attr('fill', 'white')
        .text(d => d.name.length > 6 ? d.name.substring(0, 6) + '...' : d.name);

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
        .attr('font-size', '7px')
        .attr('fill', 'white')
        .attr('class', 'derived-badge-text')
        .text(d => d.derivedCount);

      node.attr('data-bs-toggle', 'tooltip')
        .attr('data-bs-html', 'true')
        .attr('title', d => this.getNodeTooltipHtml(d));

      node
        .on('click', this.onNodeClick);
      this.simulation.on('tick', () => {
        link
          .attr('x1', d => d.source.x)
          .attr('y1', d => d.source.y)
          .attr('x2', d => d.target.x)
          .attr('y2', d => d.target.y);
        node
          .attr('transform', d => `translate(${d.x},${d.y})`);
      });
      this.simulation.alpha(1).restart();
      
      // Re-initialize Bootstrap tooltips for all nodes after rendering
      if (this.$refs.graphContainer) {
        Array.from(this.$refs.graphContainer.querySelectorAll('g.node[data-bs-toggle="tooltip"]')).forEach(el => {
          try {
            new Tooltip(el);
          } catch (error) {
            // Silently handle tooltip initialization errors
            console.warn('Tooltip initialization error:', error);
          }
        });
      }
    },

    renderLargeGraph() {
      const width = this.$refs.largeGraphContainer.clientWidth || window.innerWidth;
      const height = this.$refs.largeGraphContainer.clientHeight || window.innerHeight;
      const svg = d3.select(this.$refs.largeGraphSvg)
        .attr('width', width)
        .attr('height', height);
      
      // Dispose of existing tooltips before updating the large graph
      if (this.$refs.largeGraphContainer) {
        Array.from(this.$refs.largeGraphContainer.querySelectorAll('[data-bs-toggle="tooltip"]'))
          .forEach(el => {
            try {
              const tip = Tooltip.getInstance(el);
              if (tip) {
                tip.dispose();
              }
            } catch (error) {
              // Silently handle tooltip disposal errors
              console.warn('Large graph tooltip disposal error:', error);
            }
          });
      }
      
      svg.selectAll('*').remove();
      const mainGroup = svg.append('g').attr('class', 'main-group');
      mainGroup.append('g').attr('class', 'links');
      mainGroup.append('g').attr('class', 'nodes');
      const zoomBehavior = d3.zoom()
        .scaleExtent([0.1, 4])
        .on('zoom', event => mainGroup.attr('transform', event.transform));
      svg.call(zoomBehavior);
      // Use a new simulation for the large graph
      const simulation = d3.forceSimulation()
        .force('link', d3.forceLink()
          .id(d => d.id)
          .distance(link => {
            if (
              (link.source.type === 'base' && link.target.type === 'derived') ||
              (link.source.type === 'derived' && link.target.type === 'base')
            ) {
              return 80;
            }
            return 20;
          })
        )
        .force('charge', d3.forceManyBody().strength(-40))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(d => d.type === 'base' ? 30 : 12));
      simulation.nodes(this.graphData.nodes);
      simulation.force('link').links(this.graphData.links);
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
        .attr('class', 'node');
      node.selectAll('*').remove();
      node.append('circle')
        .attr('r', d => d.type === 'base' ? 30 : 18)
        .attr('fill', '#6c757d')
        .attr('stroke', '#fff')
        .attr('stroke-width', 2);
      node.append('text')
        .attr('text-anchor', 'middle')
        .attr('dy', '.35em')
        .attr('font-size', '13px')
        .attr('fill', 'white')
        .text(d => d.name.length > 10 ? d.name.substring(0, 10) + '...' : d.name);
      const badgeNodes = node.filter(d => d.type === 'base' && d.derivedCount > 0);
      badgeNodes.append('circle')
        .attr('cx', 20)
        .attr('cy', -20)
        .attr('r', 12)
        .attr('fill', '#dc3545')
        .attr('class', 'derived-badge');
      badgeNodes.append('text')
        .attr('x', 20)
        .attr('y', -20)
        .attr('text-anchor', 'middle')
        .attr('dy', '.35em')
        .attr('font-size', '10px')
        .attr('fill', 'white')
        .attr('class', 'derived-badge-text')
        .text(d => d.derivedCount);
      node.attr('data-bs-toggle', 'tooltip')
        .attr('data-bs-html', 'true')
        .attr('title', d => this.getNodeTooltipHtml(d));
      node
        .on('click', this.onNodeClick); // Use the same handler for fullscreen
      simulation.on('tick', () => {
        link
          .attr('x1', d => d.source.x)
          .attr('y1', d => d.source.y)
          .attr('x2', d => d.target.x)
          .attr('y2', d => d.target.y);
        node
          .attr('transform', d => `translate(${d.x},${d.y})`);
      });
      simulation.alpha(1).restart();
      
      // Re-initialize Bootstrap tooltips for all nodes after rendering
      if (this.$refs.largeGraphContainer) {
        Array.from(this.$refs.largeGraphContainer.querySelectorAll('g.node[data-bs-toggle="tooltip"]')).forEach(el => {
          try {
            new Tooltip(el);
          } catch (error) {
            console.warn('Large graph tooltip initialization error:', error);
          }
        });
      }
    },

    setupResizeObserver() {
      if (!this.$refs.graphContainer) return;
      this.resizeObserver = new ResizeObserver(entries => {
        for (let entry of entries) {
          const { width, height } = entry.contentRect;
          if (width > 0 && height > 0 && this.simulation) {
            this.initializeGraphWithDimensions(width, height);
          }
        }
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
        Object.keys(this.baseConfigurations).forEach(baseName => {
          const prevNode = prevNodes.find(n => n.id === baseName && n.type === 'base');
          nodes.push({
            id: baseName,
            type: 'base',
            name: baseName,
            config: this.baseConfigurations[baseName],
            derivedCount: Object.keys(this.derivedConfigurations[baseName] || {}).length,
            showDerived: prevNode ? prevNode.showDerived : false
          });
        });
        Object.entries(this.derivedConfigurations).forEach(([baseName, derivedConfigs]) => {
          const baseNode = nodes.find(n => n.id === baseName);
          if (baseNode && baseNode.showDerived) {
            Object.entries(derivedConfigs).forEach(([derivedName, derivedConfig]) => {
              nodes.push({
                id: derivedName,
                type: 'derived',
                name: derivedName,
                config: derivedConfig,
                baseName: baseName
              });
              links.push({ source: baseName, target: derivedName });
            });
          }
        });
        this.graphData = { nodes, links };
        this.renderGraph();
        this.renderLargeGraph();
        this.loading = false;
      });
    },
  }
}
</script>

<template>
  <!-- Configuration Graph Card Panel -->
  <div class="card border-primary mt-2">
    <div class="card-header d-flex justify-content-between align-items-center">
      <h6 class="mb-0">Configuration Graph</h6>
      <div class="d-flex align-items-center">
        <span class="badge bg-info me-2">{{ Object.keys(baseConfigurations).length }}</span>
        <button class="btn btn-outline-primary btn-sm" @click="openLargeGraphModal" title="Open Fullscreen View">
          <i class="bi bi-arrows-fullscreen"></i>
        </button>
      </div>
    </div>
    <div class="card-body p-2">
      <div id="configuration-graph" ref="graphContainer" style="min-height: 360px; width: 100%; border: 1px solid #dee2e6; border-radius: 0.35rem; cursor: grab; position: relative;">
        <svg ref="graphSvg" width="100%" height="100%"></svg>
        <div
          v-if="loading"
          class="graph-loading-overlay"
          style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: rgba(255,255,255,0.6); z-index: 10; display: flex; align-items: center; justify-content: center; pointer-events: all;">
          <span class="spinner-border text-primary" role="status" aria-hidden="true"></span>
          <span class="ms-2">Rendering...</span>
        </div>
        <!-- Modals remain inside the graph container -->
        <div id="largeGraphModal" class="modal fade" tabindex="-1" aria-labelledby="largeGraphModalLabel" aria-hidden="true">
          <div class="modal-dialog modal-fullscreen">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title" id="largeGraphModalLabel">Configuration Graph - Fullscreen View</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
              </div>
              <div class="modal-body p-0">
                <div id="large-configuration-graph" ref="largeGraphContainer" style="width: 100%; height: 100%; cursor: grab;">
                  <svg ref="largeGraphSvg" width="100%" height="100%"></svg>
                </div>
              </div>
              <div class="modal-footer">
                <div v-if="contextMenuTarget" class="context-menu-footer mb-2 w-100">
                  <div id="node-context-menu-fullscreen" class="d-flex align-items-center flex-wrap gap-2">
                    <span class="text-muted small">Selected: <strong>{{ contextMenuTarget.name }}</strong></span>
                    <div class="vr"></div>
                    <template v-if="contextMenuTarget.type === 'base'">
                      <button class="btn btn-sm btn-outline-primary" @click="openPropagateModal">
                        <i class="bi bi-arrow-repeat me-1"></i>Propagate
                      </button>
                      <button class="btn btn-sm btn-outline-danger" @click="deleteNode">
                        <i class="bi bi-trash me-1"></i>Remove
                      </button>
                    </template>
                    <template v-else-if="contextMenuTarget.type === 'derived'">
                      <button class="btn btn-sm btn-outline-danger" @click="deleteNode">
                        <i class="bi bi-trash me-1"></i>Remove
                      </button>
                    </template>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div id="propagateModal" class="modal fade" tabindex="-1" aria-labelledby="propagateModalLabel" aria-hidden="true">
          <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title" id="propagateModalLabel">Propagate Parameter</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
              </div>
              <div class="modal-body" v-if="contextMenuTarget">
                <label>Select a parameter to propagate:</label>
                <select v-model="selectedParameter" class="form-select" @change="parameterValues = []">
                  <option
                    v-for="label in Object.keys(availableParameters)"
                    :key="label"
                    :value="label"
                  >
                    {{ label }}
                  </option>
                </select>
                <div v-if="selectedParameter && selectedParameter.toLowerCase().includes('error bound') && !selectedParameter.toLowerCase().includes('mode')" class="mt-3">
                  <hr>
                  <strong>Bulk Generate Error Bound Configurations</strong>
                  <form>
                    <div class="mb-2">
                      <div class="form-floating">
                        <input type="number" id="numConfigs" class="form-control" v-model="bulkSettings.count" min="1" max="1000" placeholder="Number of Configurations">
                        <label for="numConfigs">Number of Configurations</label>
                      </div>
                    </div>
                    <div class="mb-2">
                      <div class="form-floating">
                        <select id="generationType" class="form-select" v-model="bulkSettings.distribution">
                          <option value="linear">Linear Distribution</option>
                          <option value="exponential">Exponential Distribution</option>
                          <option value="random">Random Distribution</option>
                        </select>
                        <label for="generationType">Generation Type</label>
                      </div>
                    </div>
                    <div class="mb-2">
                      <div class="form-floating">
                        <input type="number" id="minBound" class="form-control" v-model="bulkSettings.minBound" step="0.00001" placeholder="Min Error Bound">
                        <label for="minBound">Min Error Bound</label>
                      </div>
                    </div>
                    <div class="mb-2">
                      <div class="form-floating">
                        <input type="number" id="maxBound" class="form-control" v-model="bulkSettings.maxBound" step="0.00001" placeholder="Max Error Bound">
                        <label for="maxBound">Max Error Bound</label>
                      </div>
                    </div>
                  </form>
                </div>
                <div v-else-if="selectedParameter && compressorOptions[contextMenuTarget.config.compressor_id]">
                  <label class="mt-2">Value to propagate:</label>
                  <multiselect
                    v-model="parameterValues"
                    :options="compressorOptions[contextMenuTarget.config.compressor_id].Detail[selectedParameter]"
                    :multiple="true"
                    :searchable="true"
                    :placeholder="'Select values'"
                    :close-on-select="false"
                    label="label"
                    track-by="id"
                    class="mb-2"
                  />
                </div>
              </div>
              <div class="modal-footer d-flex justify-content-between">
                <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancel</button>
                <button
                  v-if="selectedParameter && selectedParameter.toLowerCase().includes('error bound') && !selectedParameter.toLowerCase().includes('mode')"
                  type="button"
                  class="btn btn-primary"
                  data-bs-dismiss="modal"
                  :disabled="!isBulkConfigValid"
                  @click="generateBulkConfigurations"
                >
                  Bulk Generate
                </button>
                <button
                  v-else
                  type="button"
                  class="btn btn-primary"
                  data-bs-dismiss="modal"
                  @click="propagateParameter"
                  :disabled="!selectedParameter || !parameterValues || (Array.isArray(parameterValues) && parameterValues.length === 0)"
                >
                  Propagate
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div v-if="Object.keys(baseConfigurations).length === 0" class="text-center text-muted mt-3">
        <p class="mb-0">No saved configurations yet.</p>
      </div>
    </div>
    
    <div class="card-footer">
      <!-- Context menu in footer -->
      <div v-if="contextMenuTarget" class="context-menu-footer mb-2" :style="{ position: $refs.largeGraphModal && $refs.largeGraphModal.contains(document.activeElement) ? 'absolute' : 'static', zIndex: 2000, left: contextMenuTarget && $refs.largeGraphModal && $refs.largeGraphModal.contains(document.activeElement) ? '30px' : undefined, top: contextMenuTarget && $refs.largeGraphModal && $refs.largeGraphModal.contains(document.activeElement) ? '30px' : undefined }">
        <div id="node-context-menu" class="d-flex align-items-center flex-wrap gap-2">
          <span class="text-muted small">Selected: <strong>{{ contextMenuTarget.name }}</strong></span>
          <div class="vr"></div>
          <template v-if="contextMenuTarget.type === 'base'">
            <button class="btn btn-sm btn-outline-primary" @click="openPropagateModal">
              <i class="bi bi-arrow-repeat me-1"></i>Propagate
            </button>
            <button class="btn btn-sm btn-outline-danger" @click="deleteNode">
              <i class="bi bi-trash me-1"></i>Remove
            </button>
          </template>
          <template v-else-if="contextMenuTarget.type === 'derived'">
            <button class="btn btn-sm btn-outline-danger" @click="deleteNode">
              <i class="bi bi-trash me-1"></i>Remove
            </button>
          </template>
        </div>
      </div>
      
      <!-- Configuration graph area -->
      <div class="text-center">
        <button
          type="button"
          class="btn btn-primary w-60"
          @click="$emit('run-all-configurations')"
          :disabled="Object.keys($props.savedConfigurations).length === 0"
        >
          Run All {{ Object.keys($props.savedConfigurations).length }} Configurations
        </button>
      </div>
    </div>

  </div>

  <!-- Alert message box -->
  <div id="compressorAlert" class="alert alert-dismissible fade mt-2" role="alert" tabindex="-1">
    <span id="compressorAlertMessage">Placeholder</span>
  </div>

</template>
