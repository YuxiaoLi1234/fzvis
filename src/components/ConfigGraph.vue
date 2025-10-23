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
    compressorOptions: { type: Object, required: false, default: () => ({}) },
  },
  components: {
    Multiselect,
  },
  emits: ['error-bound-bulk-generation', 'propagate-parameter'],

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
      configStatus: {}, // Status for the node: idle, running, success, error
      running: false,   // Spinner overlay
      largeGraphModalOpen: false,
      compressionResults: {},
      nodePositions: {}, // Store node positions by id
      prevNodeIds: [],   // Track previous node ids for change detection
    };
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
              if (this.compressionResults[derivedId]) {
                delete this.compressionResults[derivedId];
              }
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
      if (this.compressionResults[this.contextMenuTarget.id]) {
        delete this.compressionResults[this.contextMenuTarget.id];
      }

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
              return 50;
            }
            return 10;
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
        if (this.contextMenuTarget && this.contextMenuTarget.config) {
          const config = this.contextMenuTarget.config;
          const compressorConfig = config.compressor_config || {};
          if (config.compressor_id === 'sz3') {
            Object.keys(compressorConfig).forEach(val => {
              if (val.toLowerCase().includes('error_bound')) {
                this.availableParameters[this.getFormattedKey(val)] = val;
              }
            });
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
      // Hide tooltip when clicking
      this.hideTooltip();
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

    async submitConfigurations() {
      const alertBox = document.getElementById("compressorAlert");
      const alertMessage = document.getElementById("compressorAlertMessage");
      const fileData = this.$store.state.fileData;
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
      await Promise.all(configEntries.map(async ([key, config]) => {
        let formData = new FormData();
        formData.append("get_options", 0);
        formData.append("configurations", JSON.stringify({ [key]: config }));
        try {
          const response = await axios.post(`${localStorage.getItem("fzvis_server_address")}/indexlist`, formData);
          this.configStatus[key] = "success";
          this.compressionResults[key] = response.data[key] || response.data;
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
      // Save current node ids
      const currentNodeIds = this.graphData.nodes.map(n => n.id).sort();
      const prevNodeIds = this.prevNodeIds || [];
      const nodeSetChanged =
        currentNodeIds.length !== prevNodeIds.length ||
        currentNodeIds.some((id, i) => id !== prevNodeIds[i]);
      // Restore node positions if not changed
      if (!nodeSetChanged) {
        this.graphData.nodes.forEach(n => {
          if (this.nodePositions[n.id]) {
            n.x = this.nodePositions[n.id].x;
            n.y = this.nodePositions[n.id].y;
            n.vx = this.nodePositions[n.id].vx;
            n.vy = this.nodePositions[n.id].vy;
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
        .attr('fill', d => {
          const status = this.configStatus[d.id] || 'idle';
          if (status === 'running') return 'rgba(0,123,255,0.5)';
          if (status === 'success') return '#28a745';
          if (status === 'error') return '#dc3545';
          return '#6c757d';
        })
        .attr('stroke', '#fff')
        .attr('stroke-width', 2);
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
      // Save node positions on tick
      this.simulation.on('tick', () => {
        link
          .attr('x1', d => d.source.x)
          .attr('y1', d => d.source.y)
          .attr('x2', d => d.target.x)
          .attr('y2', d => d.target.y);
        node
          .attr('transform', d => `translate(${d.x},${d.y})`);
        // Save positions
        this.graphData.nodes.forEach(n => {
          this.nodePositions[n.id] = {
            x: n.x,
            y: n.y,
            vx: n.vx,
            vy: n.vy
          };
        });
      });
      // Only restart simulation if node set changed
      if (nodeSetChanged) {
        this.simulation.alpha(1).restart();
      } else {
        this.simulation.alpha(0.1).restart(); // Just a nudge for color/status update
      }
      // Update prevNodeIds
      this.prevNodeIds = currentNodeIds;
    },

    renderLargeGraph() {
      const width = this.$refs.largeGraphContainer.clientWidth || window.innerWidth;
      const height = this.$refs.largeGraphContainer.clientHeight || window.innerHeight;
      const svg = d3.select(this.$refs.largeGraphSvg)
        .attr('width', width)
        .attr('height', height);
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
        .force('collision', d3.forceCollide().radius(d => d.type === 'base' ? 25 : 17));
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
        .attr('r', d => d.type === 'base' ? 24 : 14)
        .attr('fill', d => {
          const status = this.configStatus[d.id] || 'idle';
          if (status === 'running') return 'rgba(0,123,255,0.5)';
          if (status === 'success') return '#28a745';
          if (status === 'error') return '#dc3545';
          return '#6c757d';
        })
        .attr('stroke', '#fff')
        .attr('stroke-width', 2);
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
      <div id="configuration-graph" ref="graphContainer" style="min-height: 320px; width: 100%; border: 1px solid #dee2e6; border-radius: 0.35rem; cursor: grab; position: relative;">
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

</template>
