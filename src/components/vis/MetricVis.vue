<script>
import Plotly from 'plotly.js-dist-min';
import * as d3 from "d3";
import { mapState } from 'vuex';
import { requestWithFallback } from '@/utils/datasetUtils';
import Multiselect from 'vue-multiselect';

export default {
  name: "MetricVis",
  components: { Multiselect },

  data() {
    return {
      tooltip: null,
      activeSubTab: 'analysis', // 'compression' or 'analysis'
      // Analysis-related data
      autoSelectAllSources: true,
      selectedSources: ['original'], // Default to original
      activeMetrics: [],
      powerSpectrumState: {
        fullX: null,
        fullY: null,
        viewX: null,
        viewY: null,
        roi: null,
        chartWidth: 800,
        chartHeight: 400,
        errorChartHeight: 350,
      },
      availableMetrics: [
        {
          id: 'histogram',
          name: 'Histogram',
          icon: 'bi bi-bar-chart text-success',
          description: 'Distribution of data values',
          parameters: [
            { name: 'bins', label: 'Number of Bins', type: 'number', value: 50, min: 10, max: 200, step: 10 },
          ],
        },
        {
          id: 'statistics',
          name: 'Statistical Summary',
          icon: 'bi bi-calculator text-info',
          description: 'Basic statistics (min, max, mean, std, etc.)',
          parameters: [],
        },
        {
          id: 'dssim',
          name: 'DSSIM',
          icon: 'bi bi-circle text-danger',
          description: 'Compute DSSIM between original and decompressed data',
          parameters: [
            { name: 'window_size', label: 'Window Size', type: 'number', value: 11, min: 3, max: 51, step: 2 },
            { name: 'sigma', label: 'Gaussian Sigma', type: 'number', value: 1.5, min: 0.5, max: 10, step: 0.1 },
            { name: 'bins', label: 'Quantization Bins', type: 'number', value: 256, min: 2, max: 4096, step: 1 },
            { name: 'c1', label: 'C1', type: 'number', value: 1e-8, min: 0, max: 1, step: 1e-9 },
            { name: 'c2', label: 'C2', type: 'number', value: 1e-8, min: 0, max: 1, step: 1e-9 },
          ],
        },
        {
          id: 'power_spectrum',
          name: 'Power Spectrum',
          icon: 'bi bi-graph-up-arrow text-primary',
          description: 'Compute and visualize frequency domain characteristics',
          parameters: [],
        },
        {
          id: 'critical_points',
          name: 'Critical Points',
          icon: 'bi bi-grid text-warning',
          description: 'Compute critical points (minima, maxima, and saddles)',
          parameters: [
            { name: 'computeSegmentation', label: 'Compute Morse-Smale Segmentation', type: 'boolean', value: true },
          ],
        },
      ],
      criticalPointPlotOptions: [
        { label: 'False Min', value: 'faults.num_false_min' },
        { label: 'False Max', value: 'faults.num_false_max' },
        { label: 'False Segmentation Labels', value: 'faults.num_false_labels' },
      ],
      showRawCompression: false,
      useLocalMetrics: false,
      compressionComparisons: [],
      comparisonCounter: 0,
      rawMetricFilterText: '',
      rawMetricCategory: 'all',
      comparisonGroupSelection: {},
      comparisonGroupMap: {},
      comparisonHoverPoint: {},
      comparisonMarkerSize: 20,
      comparisonChartHeight: 550,
      comparisonMarkerOpacity: 0.85,
      comparisonShowLegend: true,
      compressionMetricSelection: {},
    };
  },
  
  computed: {
    ...mapState(['dataset', 'baseConfigurations', 'derivedConfigurations']),
    comparisonData() {
      return this.$store.state.comparisonData;
    },
    canCompute() {
      return this.dataset && this.dataset.content;
    },
    availableSources() {
      const sources = [{ id: 'original', name: 'Original Data' }];
      if (this.comparisonData) {
        Object.keys(this.comparisonData).forEach(key => {
          sources.push({ id: key, name: key });
        });
      }
      return sources;
    },
    selectableSourceIds() {
      return this.availableSources
        .map(source => source.id)
        .filter(id => id !== 'original');
    },
    hasLocalMetrics() {
      return Object.values(this.comparisonData || {}).some(c => c.local_metrics);
    },
    hasSelectableSources() {
      return this.selectableSourceIds.length > 0;
    },
    allSelectableSourcesSelected() {
      if (!this.selectableSourceIds.length) return false;
      return this.selectableSourceIds.every(id => this.selectedSources.includes(id));
    },
    compressionMetricOptions() {
      const options = [];
      if (!this.comparisonData) return options;
      const keys = new Set();
      this.compressionMetricRows.forEach(row => {
        const value = Number(row.value);
        if (!Number.isFinite(value)) return;
        // RELAXED: allow zero values (e.g. 0 faults, 0 rmse) to be plottable
        keys.add(row.key);
      });
      Array.from(keys).sort().forEach(k => {
        options.push({ value: k, label: this.formatMetricKey(k) });
      });
      // Config keys removed from dropdown - use metrics instead
      return options;
    },
    compressionMetricRows() {
      if (!this.comparisonData) return [];
      const rows = [];
      Object.entries(this.comparisonData).forEach(([sourceId, data]) => {
        if (!data?.metrics) return;
        Object.entries(data.metrics).forEach(([key, value]) => {
          const parts = key.split(':');
          let category = 'other';
          let metricName = key;
          
          if (parts.length > 1) {
            category = parts[0];
            metricName = parts.slice(1).join(':');
          } else {
            // Default MSz/Correction metrics to 'qoi' category for better grouping
            if (['overall_compression_ratio', 'num_edits', 'edit_overhead'].includes(key) || key.startsWith('false_')) {
              category = 'qoi';
            }
          }

          if (category === 'time' && !['compress', 'decompress'].includes(metricName)) {
            return;
          }
          rows.push({
            sourceId,
            compressorId: data.compressor_id || '-',
            key,
            label: this.formatMetricKey(key),
            category,
            metricName,
            value,
          });
        });
      });
      return rows;
    },
    compressionMetricCategories() {
      const cats = new Set(this.compressionMetricRows.map(r => r.category));
      return Array.from(cats).sort();
    },
    filteredCompressionRows() {
      const text = this.rawMetricFilterText.trim().toLowerCase();
      return this.compressionMetricRows.filter(row => {
        if (this.rawMetricCategory !== 'all' && row.category !== this.rawMetricCategory) return false;
        if (!text) return true;
        return (
          row.sourceId.toLowerCase().includes(text) ||
          row.compressorId.toLowerCase().includes(text) ||
          row.label.toLowerCase().includes(text)
        );
      });
    },
    groupedCompressionRows() {
      const groups = {};
      this.filteredCompressionRows.forEach(row => {
        if (!groups[row.category]) groups[row.category] = [];
        groups[row.category].push(row);
      });
      return groups;
    },
    availableCompressionMetricSelections() {
      const groups = {};
      this.compressionMetricRows.forEach(row => {
        if (!groups[row.category]) groups[row.category] = new Map();
        if (!groups[row.category].has(row.label)) {
          groups[row.category].set(row.label, row.key);
        }
      });
      const result = {};
      Object.entries(groups).forEach(([category, map]) => {
        result[category] = Array.from(map.entries()).map(([label, key]) => ({
          label,
          value: key,
        }));
      });
      return result;
    },
    compressionCategoriesList() {
      return Object.keys(this.availableCompressionMetricSelections || {}).sort();
    },
    selectedCompressionKeys() {
      const selected = new Set();
      Object.values(this.compressionMetricSelection || {}).forEach(list => {
        (list || []).forEach(item => {
          if (item?.value) selected.add(item.value);
        });
      });
      return selected;
    },
    filteredCompressionChartData() {
      const selected = this.selectedCompressionKeys;
      if (!selected.size) return this.compressionMetricRows;
      return this.compressionMetricRows.filter(row => selected.has(row.key));
    },
  },
  
  watch: {
    useLocalMetrics() {
      this.refreshCompressionMetrics();
    },
    // Watch for changes in comparisonData to redraw charts
    comparisonData: {
      handler(newData) {
        if (newData) {
          setTimeout(() => {
            this.$nextTick(() => {
              this.drawBarCharts();
              this.drawComparisonCharts();
            });
          }, 300);
        }
      },
      deep: true,
    },
    // Sync selectedSources when availableSources change (e.g. node removed)
    availableSources: {
      handler(newSources) {
        const availableIds = newSources.map(s => s.id);
        // Remove sources that are no longer available
        this.selectedSources = this.selectedSources.filter(id => availableIds.includes(id));
        
        // Also remove results from active metrics for these sources
        this.activeMetrics.forEach(metric => {
          if (metric.results) {
            Object.keys(metric.results).forEach(sourceId => {
              if (sourceId !== 'original' && !availableIds.includes(sourceId)) {
                delete metric.results[sourceId];
              }
            });
          }
        });

        if (this.autoSelectAllSources && this.hasSelectableSources) {
          this.selectedSources = ['original', ...this.selectableSourceIds];
          this.autoSelectAllSources = false;
        }
      },
      deep: true
    },
    comparisonGroupSelection: {
      handler() {
        this.updateComparisonHighlighting();
      },
      deep: true
    },
    comparisonMarkerSize() {
      this.drawComparisonCharts();
    },
    comparisonChartHeight() {
      this.drawComparisonCharts();
    },
    comparisonMarkerOpacity() {
      this.drawComparisonCharts();
    },
    comparisonShowLegend() {
      this.drawComparisonCharts();
    }
  },

  mounted() {
    // Listen for Bootstrap tab show event
    const metricsTab = document.getElementById('metrics-tab');
    if (metricsTab) {
      metricsTab.addEventListener('shown.bs.tab', () => {
        if (this.activeSubTab === 'compression') {
          this.drawBarCharts();
        }
      });
    }
  },

  methods: {
    async computeDataKey() {
      return crypto.randomUUID();
    },
    // Analysis methods
    isMetricActive(metricId) {
      return this.activeMetrics.some(m => m.id === metricId);
    },

    toggleMetric(metricTemplate) {
      const index = this.activeMetrics.findIndex(m => m.id === metricTemplate.id);
      if (index > -1) {
        // Remove metric if already active
        this.activeMetrics.splice(index, 1);
      } else {
        // Add metric if not active
        const metric = {
          ...metricTemplate,
          parameters: metricTemplate.parameters ? 
            JSON.parse(JSON.stringify(metricTemplate.parameters)) : [],
          computing: false,
          results: {}, // Map of sourceId -> result
          viewMode: 'raw',
        };
        if (metric.id === 'critical_points') {
          metric.plotFields = [...this.criticalPointPlotOptions];
          metric.histogramMode = 'min'; // Default to either min or max
          metric.histogramIncludeOriginal = true; // Default to showing original
        }
        // Add to the beginning of the list so it appears on top
        this.activeMetrics.unshift(metric);
      }
    },

    toggleSource(sourceId) {
      if (sourceId === 'original') return; // Original is always selected
      this.autoSelectAllSources = false;

      const idx = this.selectedSources.indexOf(sourceId);
      if (idx > -1) {
        this.selectedSources.splice(idx, 1);
      } else {
        this.selectedSources.push(sourceId);
      }
    },
    toggleAllSources() {
      if (!this.hasSelectableSources) return;
      this.autoSelectAllSources = false;
      if (this.allSelectableSourcesSelected) {
        this.selectedSources = ['original'];
      } else {
        this.selectedSources = ['original', ...this.selectableSourceIds];
      }
    },

    clearAllMetrics() {
      this.activeMetrics = [];
    },

    async computeMetric(metric) {
      if (!this.canCompute) {
        this.$store.commit('setStatus', { 
          type: 'warning', 
          message: 'No dataset loaded' 
        });
        return;
      }

      metric.computing = true;
      // We don't necessarily want to clear all results, maybe just the selected ones
      this.selectedSources.forEach(sourceId => {
        metric.results[sourceId] = null;
      });

      try {
        const params = {};
        if (metric.parameters) {
          metric.parameters.forEach(p => {
            params[p.name] = p.value;
          });
        }

        params.dimensions = this.dataset.dimensions;
        params.precision = this.dataset.precision;
        params.endianness = this.dataset.endianness || 'little';

        let originalDataKey = this.dataset.data_key;

        // Create a copy and sort to ensure 'original' is first
        const sortedSources = [...this.selectedSources].sort((a, b) => {
          if (a === 'original') return -1;
          if (b === 'original') return 1;
          return 0;
        });

        // Loop through selected sources
        for (const sourceId of sortedSources) {
          if (metric.id === 'dssim' && sourceId === 'original') {
            continue;
          }
          let dataKey;
          let currentDataset;

          // Fresh parameters for this source request
          const requestParams = {
            ...params,
            dimensions: this.dataset.dimensions,
            precision: this.dataset.precision
          };

          if (sourceId === 'original') {
            dataKey = this.dataset.data_key;
            currentDataset = this.dataset;
          } else {
            const comp = this.comparisonData ? this.comparisonData[sourceId] : null;
            if (!comp) {
              console.warn(`Source ${sourceId} not found in comparisonData`);
              continue;
            }
            dataKey = comp.data_key;
            currentDataset = comp;
            
            // Add comparison key for compressed sources
            if (originalDataKey) {
              requestParams.comparison_key = originalDataKey;
            }
          }

          if (!dataKey && currentDataset.content instanceof ArrayBuffer) {
            dataKey = await this.computeDataKey();
            if (sourceId === 'original') {
              originalDataKey = dataKey; // Capture for others in this loop
              this.$store.commit('setFileData', { 
                dataset: { ...this.dataset, data_key: dataKey } 
              });
            } else {
              // Update comparison data in store with data_key
              if (this.comparisonData && this.comparisonData[sourceId]) {
                const newComp = { ...this.comparisonData[sourceId], data_key: dataKey };
                const newComparisonData = { ...this.comparisonData, [sourceId]: newComp };
                this.$store.commit('setComparisonData', newComparisonData);
              }
            }
          }

          if (dataKey) {
            const formData = new FormData();
            formData.append('metric_type', metric.id);
            formData.append('parameters', JSON.stringify(requestParams));
            formData.append('data_key', dataKey);
            
            // Prepare datasets map for fallback recovery
            const datasetsMap = {};
            if (originalDataKey) datasetsMap[originalDataKey] = this.dataset;
            if (dataKey) datasetsMap[dataKey] = currentDataset;

            const response = await requestWithFallback({
              method: 'post',
              url: '/api/analysis/compute',
              data: formData
            }, datasetsMap);

            if (response?.data?.result) {
              metric.results = { 
                ...metric.results, 
                [sourceId]: response.data.result 
              };
              if (metric.id === 'dssim' && response.data.result.type === 'scalar') {
                this.updateComparisonMetric(sourceId, 'qoi:dssim', response.data.result.value);
              }
              if (metric.id === 'critical_points' && sourceId !== 'original') {
                const faults = response.data.result?.faults;
                if (faults) {
                  const falseMin = Number(faults.num_false_min) || 0;
                  const falseMax = Number(faults.num_false_max) || 0;
                  const falseLabels = Number(faults.num_false_labels) || 0;
                  const totalFalse = falseMin + falseMax + falseLabels;
                  this.updateComparisonMetric(sourceId, 'qoi:false_min', falseMin);
                  this.updateComparisonMetric(sourceId, 'qoi:false_max', falseMax);
                  this.updateComparisonMetric(sourceId, 'qoi:false_segmentations', falseLabels);
                  this.updateComparisonMetric(sourceId, 'qoi:false_critical_points', totalFalse);
                }
              }
            }
          }
        }

        this.$store.commit('setStatus', { 
          type: 'success', 
          message: `${metric.name} computed for selected sources` 
        });
        
        // Redraw charts for visualizations
        this.$nextTick(() => {
          this.activeMetrics.forEach(metric => {
            const id = metric.id;
            if (id === 'histogram') this.drawHistogram(this.activeMetrics.find(m => m.id === id));
            else if (id === 'power_spectrum') this.drawPowerSpectrum(this.activeMetrics.find(m => m.id === id));
            else if (id === 'correlation') this.drawCorrelation(this.activeMetrics.find(m => m.id === id));
          });
          if (metric.viewMode === 'plot') {
            this.drawMetricPlot(metric);
          }
        });

      } catch (error) {
        console.error('Error computing metric:', error);
        this.$store.commit('setStatus', { 
          type: 'danger', 
          message: `Failed to compute ${metric.name}: ${error.response?.data?.error || error.message}` 
        });
      } finally {
        metric.computing = false;
      }
    },
    setMetricView(metric, mode) {
      metric.viewMode = mode;
      if (mode === 'plot') {
        this.$nextTick(() => this.drawMetricPlot(metric));
      }
    },
    updateComparisonMetric(sourceId, metricKey, metricValue) {
      if (!this.comparisonData || !this.comparisonData[sourceId]) return;
      const comp = this.comparisonData[sourceId];
      const nextMetrics = { ...(comp.metrics || {}), [metricKey]: metricValue };
      const next = { ...this.comparisonData, [sourceId]: { ...comp, metrics: nextMetrics } };
      this.$store.commit('setComparisonData', next);
    },
    drawMetricPlot(metric) {
      if (metric.id === 'dssim') this.drawDssimPlot(metric);
      if (metric.id === 'critical_points') {
        this.drawCriticalPointsPlot(metric);
        this.drawCriticalPointsValueHistogram(metric);
      }
    },
    truncateAxisLabel(label, maxLen = 14) {
      if (typeof label !== 'string') return label;
      if (label.length <= maxLen) return label;
      return `${label.slice(0, Math.max(0, maxLen - 1))}…`;
    },
    calculateOptimalTicks(chartHeight) {
      // Dynamically calculate number of ticks based on chart height
      // More height = more space for labels = more ticks
      if (chartHeight < 250) return 2;
      if (chartHeight < 350) return 3;
      if (chartHeight < 500) return 4;
      if (chartHeight < 650) return 5;
      return 6; // Maximum 6 ticks even for very large charts
    },
    calculateOptimalTicksForWidth(chartWidth) {
      // Dynamically calculate number of ticks based on chart width
      // More width = more space for labels = more ticks
      if (chartWidth < 300) return 2;
      if (chartWidth < 450) return 3;
      if (chartWidth < 600) return 4;
      if (chartWidth < 750) return 5;
      return 6; // Maximum 6 ticks even for very wide charts
    },
    filterTicksEvenlyInLogSpace(allTicks, targetCount) {
      // Distribute ticks evenly in LOG SPACE (not array index)
      // This ensures visual spacing is even on log scale
      if (allTicks.length <= targetCount) return allTicks;
      if (targetCount < 2) return [allTicks[0]];

      const minVal = allTicks[0];
      const maxVal = allTicks[allTicks.length - 1];

      // Calculate positions in log space
      const logMin = Math.log10(Math.max(minVal, 1e-10));
      const logMax = Math.log10(Math.max(maxVal, 1e-10));
      const logStep = (logMax - logMin) / (targetCount - 1);

      const filtered = [];
      for (let i = 0; i < targetCount; i++) {
        const targetLogValue = logMin + i * logStep;

        // Find closest tick to this target log value
        let closestTick = allTicks[0];
        let minDistance = Math.abs(Math.log10(allTicks[0]) - targetLogValue);

        for (const tick of allTicks) {
          const distance = Math.abs(Math.log10(Math.max(tick, 1e-10)) - targetLogValue);
          if (distance < minDistance) {
            minDistance = distance;
            closestTick = tick;
          }
        }

        // Avoid duplicates
        if (filtered.length === 0 || closestTick !== filtered[filtered.length - 1]) {
          filtered.push(closestTick);
        }
      }

      return filtered;
    },
    drawDssimPlot(metric) {
      const containerId = `metric-plot-${metric.id}`;
      const container = d3.select(`#${containerId}`);
      if (!container.node()) return;
      container.selectAll("*").remove();
      const points = Object.entries(metric.results || {})
        .filter(([, res]) => res && res.type === 'scalar')
        .map(([sourceId, res]) => ({ sourceId, value: Number(res.value) }))
        .filter(d => Number.isFinite(d.value));
      if (!points.length) return;
      const margin = { top: 40, right: 50, bottom: 70, left: 100 }; // Publication-quality margins
      const width = Math.max(300, container.node().clientWidth || 400) - margin.left - margin.right;
      const height = 360 - margin.top - margin.bottom;
      const svg = container.append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)
        .style("background-color", "white");
      const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);
      const x = d3.scaleBand().domain(points.map(p => p.sourceId)).range([0, width]).padding(0.2);
      const y = d3.scaleLinear().domain([0, d3.max(points, d => d.value)]).nice().range([height, 0]);

      // X-axis with publication-quality styling
      g.append("g")
        .attr("transform", `translate(0,${height})`)
        .call(d3.axisBottom(x).tickFormat(d => this.truncateAxisLabel(d)).tickSize(6).tickPadding(8))
        .call(axis => {
          axis.selectAll("text")
            .style("font-size", "15px")
            .style("font-weight", "500")
            .attr("transform", "rotate(-25)")
            .style("text-anchor", "end")
            .append("title")
            .text(d => d);
          axis.select(".domain").style("stroke-width", "2px");
          axis.selectAll(".tick line").style("stroke-width", "2px");
        });

      // Y-axis with publication-quality styling
      g.append("g")
        .call(d3.axisLeft(y).ticks(5).tickSize(6).tickPadding(8))
        .call(axis => {
          axis.selectAll("text")
            .style("font-size", "16px")
            .style("font-weight", "500");
          axis.select(".domain").style("stroke-width", "2px");
          axis.selectAll(".tick line").style("stroke-width", "2px");
        });
      g.selectAll("rect")
        .data(points)
        .enter()
        .append("rect")
        .attr("x", d => x(d.sourceId))
        .attr("y", d => y(d.value))
        .attr("width", x.bandwidth())
        .attr("height", d => height - y(d.value))
        .attr("fill", "#0d6efd")
        .append("title")
        .text(d => `${d.sourceId}: ${this.formatNumber(d.value)}`);
    },
    drawCriticalPointsPlot(metric) {
      const containerId = `metric-plot-${metric.id}`;
      const container = d3.select(`#${containerId}`);
      if (!container.node()) return;
      container.selectAll("*").remove();
      const selectedFields = (metric.plotFields || []).map(p => p.value);
      const fieldLabels = {};
      (metric.plotFields || []).forEach(p => { fieldLabels[p.value] = p.label; });
      
      const rows = Object.entries(metric.results || {})
        .filter(([sourceId, res]) => sourceId !== 'original' && res && res.type === 'critical_points')
        .sort((a, b) => a[0].localeCompare(b[0])) // Sort sources alphabetically
        .map(([sourceId, res]) => ({
          sourceId,
          values: selectedFields.map(field => {
            if (field === 'faults.num_false_min') return res.faults?.num_false_min ?? 0;
            if (field === 'faults.num_false_max') return res.faults?.num_false_max ?? 0;
            if (field === 'faults.num_false_labels') return res.faults?.num_false_labels ?? 0;
            return 0;
          })
        }));
      if (!rows.length) return;
      const categories = selectedFields;
      const margin = { top: 40, right: 50, bottom: 70, left: 110 }; // Publication-quality margins
      const width = Math.max(300, container.node().clientWidth || 400) - margin.left - margin.right;
      const height = 360 - margin.top - margin.bottom;
      const svg = container.append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)
        .style("background-color", "white");
      const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);
      const x0 = d3.scaleBand().domain(rows.map(r => r.sourceId)).range([0, width]).padding(0.2);
      const x1 = d3.scaleBand().domain(categories).range([0, x0.bandwidth()]).padding(0.1);
      const maxVal = d3.max(rows, r => d3.max(r.values));
      const y = d3.scaleLinear().domain([0, maxVal || 1]).nice().range([height, 0]);
      const color = d3.scaleOrdinal().domain(categories).range(d3.schemeTableau10);
      // X-axis with publication-quality styling
      g.append("g")
        .attr("transform", `translate(0,${height})`)
        .call(d3.axisBottom(x0).tickFormat(d => this.truncateAxisLabel(d)).tickSize(6).tickPadding(8))
        .call(axis => {
          axis.selectAll("text")
            .style("font-size", "15px")
            .style("font-weight", "500")
            .attr("transform", "rotate(-25)")
            .style("text-anchor", "end")
            .append("title")
            .text(d => d);
          axis.select(".domain").style("stroke-width", "2px");
          axis.selectAll(".tick line").style("stroke-width", "2px");
        });

      // Y-axis with publication-quality styling
      const yAxis = d3.axisLeft(y).ticks(5).tickFormat(d => this.formatNumber(d)).tickSize(6).tickPadding(8);
      g.append("g")
        .call(yAxis)
        .call(axis => {
          axis.selectAll("text")
            .style("font-size", "16px")
            .style("font-weight", "500");
          axis.select(".domain").style("stroke-width", "2px");
          axis.selectAll(".tick line").style("stroke-width", "2px");
        });
      const group = g.selectAll("g.grp")
        .data(rows)
        .enter()
        .append("g")
        .attr("transform", d => `translate(${x0(d.sourceId)},0)`);
      group.selectAll("rect")
        .data(d => categories.map((c, idx) => ({ key: c, value: d.values[idx], sourceId: d.sourceId })))
        .enter()
        .append("rect")
        .attr("x", d => x1(d.key))
        .attr("y", d => y(d.value))
        .attr("width", x1.bandwidth())
        .attr("height", d => height - y(d.value))
        .attr("fill", d => color(d.key))
        .append("title")
        .text(d => `${d.sourceId} - ${fieldLabels[d.key]}: ${this.formatNumber(d.value)}`);
    },
    drawCriticalPointsValueHistogram(metric) {
      const containerId = `metric-plot-${metric.id}-values`;
      const container = d3.select(`#${containerId}`);
      if (!container.node()) return;
      container.selectAll('*').remove();
      const mode = metric.histogramMode || 'both';

      const sources = Object.entries(metric.results || {})
        .filter(([id, res]) => {
          if (!res || res.type !== 'critical_points') return false;
          // For now, only plot the original dataset as requested
          return id === 'original';
        })
        .map(([id, res]) => ({ sourceId: id, res }));

      if (!sources.length) return;

      const allValues = [];
      const valuesBySource = sources.map(({ sourceId, res }) => {
        const getPointValues = (obj) => {
          if (!obj || !obj.points) return [];
          const pts = obj.points;
          if (obj.format === 'flat') {
            const vals = [];
            for (let i = 0; i < pts.length; i += 4) {
              const val = Number(pts[i + 3]);
              if (Number.isFinite(val)) vals.push(val);
            }
            return vals;
          }
          return pts.map(p => Number(p.value)).filter(v => Number.isFinite(v));
        };

        const minVals = getPointValues(res.minima);
        const maxVals = getPointValues(res.maxima);
        let values = [];
        if (mode === 'min') values = minVals;
        else if (mode === 'max') values = maxVals;
        else values = minVals.concat(maxVals);

        for (let i = 0; i < values.length; i++) {
          allValues.push(values[i]);
        }
        return { sourceId, minVals, maxVals };
      });

      const extent = d3.extent(allValues);
      if (!extent || extent[0] === undefined || extent[1] === undefined) return;
      
      // Ensure the domain is at least a little bit padded
      const pad = (extent[1] - extent[0]) * 0.05 || 0.1;
      const domain = [extent[0] - pad, extent[1] + pad];

      const containerNode = container.node();
      const totalWidth = Math.max(300, containerNode.clientWidth || 600);
      const gap = 12;
      const cols = totalWidth >= 700 ? 2 : 1;
      const cardWidth = Math.floor((totalWidth - gap * (cols - 1)) / cols);

      container
        .style('display', 'flex')
        .style('flex-wrap', 'wrap')
        .style('gap', `${gap}px`);

      valuesBySource.forEach(({ sourceId, minVals, maxVals }) => {
        const card = container.append('div')
          .style('flex', `0 0 ${cardWidth}px`)
          .style('border', '1px solid #e5e7eb')
          .style('border-radius', '6px')
          .style('padding', '8px');

        card.append('div')
          .style('font-size', '16px')
          .style('font-weight', '600')
          .style('margin-bottom', '8px')
          .text(sourceId);

        const margin = { top: 20, right: 20, bottom: 60, left: 80 }; // Publication-quality margins
        const width = cardWidth - margin.left - margin.right - 4;
        const height = 280 - margin.top - margin.bottom;
        const svg = card.append('svg')
          .attr('width', width + margin.left + margin.right)
          .attr('height', height + margin.top + margin.bottom)
          .style("background-color", "white");
        const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

        const bins = d3.bin().domain(domain).thresholds(30);
        const minBins = bins(minVals);
        const maxBins = bins(maxVals);

        const x = d3.scaleLinear().domain(domain).nice().range([0, width]);
        const maxCount = d3.max([
          d3.max(minBins, d => d.length) || 0,
          d3.max(maxBins, d => d.length) || 0
        ]) || 1;
        const y = d3.scaleLinear().domain([0, maxCount]).nice().range([height, 0]);

        // X-axis with publication-quality styling
        g.append('g')
          .attr('transform', `translate(0,${height})`)
          .call(d3.axisBottom(x).ticks(5).tickFormat(d => this.formatNumber(d)).tickSize(6).tickPadding(8))
          .call(axis => {
            axis.selectAll('text')
              .style('font-size', '14px')
              .style('font-weight', '500');
            axis.select(".domain").style("stroke-width", "2px");
            axis.selectAll(".tick line").style("stroke-width", "2px");
          });

        // Y-axis with publication-quality styling
        g.append('g')
          .call(d3.axisLeft(y).ticks(4).tickFormat(d => this.formatNumber(d)).tickSize(6).tickPadding(8))
          .call(axis => {
            axis.selectAll('text')
              .style('font-size', '14px')
              .style('font-weight', '500');
            axis.select(".domain").style("stroke-width", "2px");
            axis.selectAll(".tick line").style("stroke-width", "2px");
          });

        // Axis labels with larger fonts
        g.append('text')
          .attr('text-anchor', 'middle')
          .attr('x', width / 2)
          .attr('y', height + 45)
          .text('Scalar Field Value')
          .style('font-size', '15px')
          .style('font-weight', '600');

        g.append('text')
          .attr('text-anchor', 'middle')
          .attr('transform', 'rotate(-90)')
          .attr('y', -55)
          .attr('x', -height / 2)
          .text('Frequency')
          .style('font-size', '15px')
          .style('font-weight', '600');

        if (mode !== 'max') {
          g.selectAll('rect.minima')
            .data(minBins)
            .enter()
            .append('rect')
            .attr('class', 'minima')
            .attr('x', d => x(d.x0))
            .attr('y', d => y(d.length))
            .attr('width', d => Math.max(1, x(d.x1) - x(d.x0) - 1))
            .attr('height', d => height - y(d.length))
            .attr('fill', '#4e79a7')
            .attr('opacity', mode === 'both' ? 0.55 : 0.7);
        }
        if (mode !== 'min') {
          g.selectAll('rect.maxima')
            .data(maxBins)
            .enter()
            .append('rect')
            .attr('class', 'maxima')
            .attr('x', d => x(d.x0))
            .attr('y', d => y(d.length))
            .attr('width', d => Math.max(1, x(d.x1) - x(d.x0) - 1))
            .attr('height', d => height - y(d.length))
            .attr('fill', '#f28e2b')
            .attr('opacity', mode === 'both' ? 0.5 : 0.7);
        }

        if (mode === 'both') {
          const legend = g.append('g').attr('transform', 'translate(0, -4)');
          legend.append('rect').attr('x', 0).attr('y', 0).attr('width', 8).attr('height', 8).attr('fill', '#4e79a7').attr('opacity', 0.55);
          legend.append('text').attr('x', 12).attr('y', 7).attr('font-size', '9px').text('Min');
          legend.append('rect').attr('x', 44).attr('y', 0).attr('width', 8).attr('height', 8).attr('fill', '#f28e2b').attr('opacity', 0.5);
          legend.append('text').attr('x', 56).attr('y', 7).attr('font-size', '9px').text('Max');
        }
      });
    },

    drawHistogram(metric) {
      const containerId = `histogram-chart-${metric.id}`;
      const container = document.getElementById(containerId);
      if (!container) return;

      const results = metric.results;
      const sources = Object.entries(results).filter(([, res]) => res && res.type === 'histogram');
      if (sources.length === 0) return;

      // Prepare data for Plotly (one trace per source)
      const traces = sources.map(([id, res]) => ({
        x: res.bins.map(b => b.x),
        y: res.bins.map(b => b.count),
        name: id,
        type: 'bar',
        marker: {
          line: {
            width: 0.5
          }
        }
      }));

      const layout = {
        title: {
          text: '',
          font: { size: 18, weight: 600 }
        },
        xaxis: {
          title: {
            text: 'Value',
            font: { size: 18, weight: 600 }
          },
          tickfont: { size: 16, weight: 500 },
          linewidth: 2
        },
        yaxis: {
          title: {
            text: 'Count',
            font: { size: 18, weight: 600 }
          },
          tickfont: { size: 16, weight: 500 },
          linewidth: 2
        },
        barmode: 'group',
        bargap: 0.15,
        bargroupgap: 0.05,
        height: 500,
        margin: { l: 100, r: 50, t: 40, b: 80 },
        plot_bgcolor: 'white',
        paper_bgcolor: 'white',
        legend: {
          font: { size: 15, weight: 500 },
          x: 1,
          xanchor: 'right',
          y: 1
        },
        hovermode: 'closest'
      };

      // Get actual rendered dimensions for export
      const actualWidth = container.clientWidth || 800;

      const config = {
        responsive: true,
        displayModeBar: true,
        displaylogo: false,
        modeBarButtonsToRemove: ['lasso2d', 'select2d'],
        toImageButtonOptions: {
          format: 'png',
          filename: `histogram_${metric.id}`,
          height: 500,
          width: actualWidth,
          scale: 2
        }
      };

      Plotly.newPlot(containerId, traces, layout, config);
    },

    drawPowerSpectrum(metric) {
      const containerId = `ps-chart-${metric.id}`;
      const container = document.getElementById(containerId);
      if (!container) return;

      const results = metric.results;
      const sources = Object.entries(results).filter(([, res]) => res && res.type === 'power_spectrum');
      if (sources.length === 0) return;

      // Filter valid data points
      const allData = [];
      sources.forEach(([, res]) => {
        res.data.forEach(d => allData.push(d));
      });
      const filteredAllData = allData.filter(d => d.k > 0 && d.p > 0);
      if (filteredAllData.length === 0) return;

      // Store full extent for zoom/reset
      const fullX = [Math.min(...filteredAllData.map(d => d.k)), Math.max(...filteredAllData.map(d => d.k))];
      const fullY = [Math.min(...filteredAllData.map(d => d.p)), Math.max(...filteredAllData.map(d => d.p))];
      this.powerSpectrumState.fullX = fullX;
      this.powerSpectrumState.fullY = fullY;

      // Use current view or full extent
      const viewX = this.powerSpectrumState.viewX || fullX;
      const viewY = this.powerSpectrumState.viewY || fullY;

      const colorScale = this.getPowerSpectrumColorScale(sources);

      // Ensure original line is drawn on top by placing it last in traces
      const primarySource = sources.find(([id]) => id === 'original');
      const secondarySources = sources.filter(([id]) => id !== 'original');
      const orderedSources = [...secondarySources, ...(primarySource ? [primarySource] : [])];

      // Prepare traces for Plotly
      const traces = orderedSources.map(([id, res]) => ({
        x: res.data.map(d => d.k),
        y: res.data.map(d => d.p),
        name: id,
        type: 'scatter',
        mode: 'lines',
        line: {
          width: 3,
          color: colorScale(id)
        },
        opacity: 0.75,
        hovertemplate: '<b>%{fullData.name}</b><br>k: %{x:.2e}<br>P(k): %{y:.2e}<extra></extra>'
      }));

      const layout = {
        xaxis: {
          title: {
            text: 'Wavenumber (k)',
            font: { size: 18, weight: 600 }
          },
          type: 'log',
          range: [Math.log10(viewX[0]), Math.log10(viewX[1])],
          tickmode: 'linear',
          dtick: 1,
          tickfont: { size: 16, weight: 500 },
          linewidth: 2,
          minor: {
            ticks: 'outside',
            ticklen: 3,
            showgrid: true,
          },
          gridcolor: '#e0e0e0'
        },
        yaxis: {
          title: {
            text: 'Power P(k)',
            font: { size: 18, weight: 600 }
          },
          type: 'log',
          range: [Math.log10(viewY[0]), Math.log10(viewY[1])],
          tickfont: { size: 16, weight: 500 },
          linewidth: 2,
          tickmode: 'linear',
          dtick: 1,
          exponentformat: 'power',
          minor: {
            ticks: 'outside',
            ticklen: 3,
            showgrid: true,
          },
          gridcolor: '#e0e0e0'
        },
        height: this.powerSpectrumState.chartHeight,
        margin: { l: 120, r: 20, t: 40, b: 40 },
        plot_bgcolor: 'white',
        paper_bgcolor: 'white',
        legend: {
          font: { size: 15, weight: 500 },
          x: 1.02,
          xanchor: 'left',
          y: 1
        },
        hovermode: 'closest',
        dragmode: 'zoom'
      };

      // Get actual rendered dimensions for export
      const actualWidth = container.clientWidth || 1000;

      const config = {
        responsive: true,
        displayModeBar: true,
        displaylogo: false,
        modeBarButtonsToRemove: ['lasso2d', 'select2d'],
        toImageButtonOptions: {
          format: 'png',
          filename: `power_spectrum_${metric.id}`,
          height: this.powerSpectrumState.chartHeight,
          width: actualWidth,
          scale: 2
        }
      };

      Plotly.newPlot(containerId, traces, layout, config);

      // Handle zoom events to update state
      container.on('plotly_relayout', (eventData) => {
        if (eventData['xaxis.range[0]'] !== undefined && eventData['xaxis.range[1]'] !== undefined) {
          const newViewX = [Math.pow(10, eventData['xaxis.range[0]']), Math.pow(10, eventData['xaxis.range[1]'])];
          this.powerSpectrumState.viewX = newViewX;
        }
        if (eventData['yaxis.range[0]'] !== undefined && eventData['yaxis.range[1]'] !== undefined) {
          const newViewY = [Math.pow(10, eventData['yaxis.range[0]']), Math.pow(10, eventData['yaxis.range[1]'])];
          this.powerSpectrumState.viewY = newViewY;
        }
        // Reset on double-click
        if (eventData['xaxis.autorange'] || eventData['yaxis.autorange']) {
          this.powerSpectrumState.viewX = null;
          this.powerSpectrumState.viewY = null;
        }
      });

      // Draw relative error plot
      this.$nextTick(() => this.drawPowerSpectrumRelativeError(metric));
    },

    zoomPowerSpectrum(metric, factor) {
      const containerId = `ps-chart-${metric.id}`;
      const container = document.getElementById(containerId);
      if (!container) return;

      const fullX = this.powerSpectrumState.fullX;
      const fullY = this.powerSpectrumState.fullY;
      if (!fullX || !fullY) return;

      const zoomLogDomain = (domain, fullDomain, zoomFactor) => {
        const logMin = Math.log10(domain[0]);
        const logMax = Math.log10(domain[1]);
        const logCenter = (logMin + logMax) / 2;
        const newSpan = (logMax - logMin) / zoomFactor;
        let newMin = Math.pow(10, logCenter - newSpan / 2);
        let newMax = Math.pow(10, logCenter + newSpan / 2);
        newMin = Math.max(newMin, fullDomain[0]);
        newMax = Math.min(newMax, fullDomain[1]);
        return [newMin, newMax];
      };

      const viewX = this.powerSpectrumState.viewX || fullX;
      const viewY = this.powerSpectrumState.viewY || fullY;

      const newViewX = zoomLogDomain(viewX, fullX, factor);
      const newViewY = zoomLogDomain(viewY, fullY, factor);

      // Update Plotly chart directly
      Plotly.relayout(containerId, {
        'xaxis.range': [Math.log10(newViewX[0]), Math.log10(newViewX[1])],
        'yaxis.range': [Math.log10(newViewY[0]), Math.log10(newViewY[1])]
      });

      this.powerSpectrumState.viewX = newViewX;
      this.powerSpectrumState.viewY = newViewY;
      this.$nextTick(() => this.drawPowerSpectrumRelativeError(metric));
    },

    resetPowerSpectrumView(metric) {
      const containerId = `ps-chart-${metric.id}`;
      const container = document.getElementById(containerId);
      if (!container) return;

      this.powerSpectrumState.viewX = null;
      this.powerSpectrumState.viewY = null;
      this.powerSpectrumState.roi = null;

      // Reset Plotly chart to autoscale
      Plotly.relayout(containerId, {
        'xaxis.autorange': true,
        'yaxis.autorange': true
      });

      this.$nextTick(() => this.drawPowerSpectrumRelativeError(metric));
    },

    clearPowerSpectrumROI(metric) {
      this.powerSpectrumState.roi = null;
      this.powerSpectrumState.viewX = null;
      this.powerSpectrumState.viewY = null;
      this.$nextTick(() => this.drawPowerSpectrum(metric));
    },

    drawPowerSpectrumRelativeError(metric) {
      const containerId = `ps-error-chart-${metric.id}`;
      const container = document.getElementById(containerId);
      if (!container) return;

      const results = metric.results;
      const sources = Object.entries(results).filter(([, res]) => res && res.type === 'power_spectrum');

      // Need at least original and one compressed source
      const originalResult = results['original'];
      if (!originalResult || sources.length < 2) return;

      // Build original data map for fast lookup
      const originalMap = new Map();
      originalResult.data.forEach(d => {
        if (d.k > 0 && d.p > 0) {
          originalMap.set(d.k, d.p);
        }
      });

      // Compute relative errors for each compressed source (in percentage)
      const errorData = [];
      sources.forEach(([id, res]) => {
        if (id === 'original') return;

        res.data.forEach(d => {
          if (d.k > 0 && d.p > 0 && originalMap.has(d.k)) {
            const origP = originalMap.get(d.k);
            const relError = ((d.p - origP) / Math.max(origP, 1e-10)) * 100; // Signed relative error in percentage
            errorData.push({ id, k: d.k, error: relError });
          }
        });
      });

      if (errorData.length === 0) return;

      const viewX = this.powerSpectrumState.viewX || [
        Math.min(...errorData.map(d => d.k)),
        Math.max(...errorData.map(d => d.k))
      ];
      const filteredData = errorData.filter(d => d.k >= viewX[0] && d.k <= viewX[1]);

      if (filteredData.length === 0) return;

      // Group data by source id
      const dataBySource = new Map();
      filteredData.forEach(d => {
        if (!dataBySource.has(d.id)) {
          dataBySource.set(d.id, []);
        }
        dataBySource.get(d.id).push(d);
      });

      // Check if there are negative errors
      const allErrors = filteredData.map(d => d.error);
      const hasNegativeErrors = Math.min(...allErrors) < 0;

      const colorScale = this.getPowerSpectrumColorScale(sources);

      // Prepare traces for Plotly
      const traces = Array.from(dataBySource.entries()).map(([id, values]) => {
        // Sort by k for proper line plotting
        values.sort((a, b) => a.k - b.k);
        return {
          x: values.map(d => d.k),
          y: values.map(d => d.error),
          name: id,
          type: 'scatter',
          mode: 'lines',
          line: { width: 3, color: colorScale(id) },
          hovertemplate: '<b>%{fullData.name}</b><br>k: %{x:.2e}<br>Error: %{y:.2f}%<extra></extra>'
        };
      });

      // Add zero reference line if there are negative errors
      const shapes = hasNegativeErrors ? [{
        type: 'line',
        x0: viewX[0],
        y0: 0,
        x1: viewX[1],
        y1: 0,
        line: {
          color: '#666',
          width: 2,
          dash: 'dash'
        }
      }] : [];

      const layout = {
        xaxis: {
          title: {
            text: 'Wavenumber (k)',
            font: { size: 18, weight: 600 }
          },
          type: 'log',
          range: [Math.log10(viewX[0]), Math.log10(viewX[1])],
          tickmode: 'linear',
          dtick: 1,
          tickfont: { size: 16, weight: 500 },
          linewidth: 2,
          minor: {
            ticks: 'outside',
            ticklen: 3,
            showgrid: true,
          },
          gridcolor: '#e0e0e0'
        },
        yaxis: {
          title: {
            text: 'Spectrum Relative Error (%)',
            font: { size: 18, weight: 600 }
          },
          type: hasNegativeErrors ? 'linear' : 'log',
          tickfont: { size: 16, weight: 500 },
          linewidth: 2,
          gridcolor: '#e0e0e0'
        },
        shapes: shapes,
        height: this.powerSpectrumState.errorChartHeight,
        margin: { l: 120, r: 20, t: 30, b: 40 },
        plot_bgcolor: 'white',
        paper_bgcolor: 'white',
        legend: {
          font: { size: 15, weight: 500 },
          x: 1.02,
          xanchor: 'left',
          y: 1
        },
        hovermode: 'closest'
      };

      // Get actual rendered dimensions for export
      const actualWidth = container.clientWidth || 1000;

      const config = {
        responsive: true,
        displayModeBar: true,
        displaylogo: false,
        modeBarButtonsToRemove: ['lasso2d', 'select2d'],
        toImageButtonOptions: {
          format: 'png',
          filename: `power_spectrum_error_${metric.id}`,
          height: this.powerSpectrumState.errorChartHeight,
          width: actualWidth,
          scale: 2
        }
      };

      Plotly.newPlot(containerId, traces, layout, config);
    },

    getPowerSpectrumColorScale(sources) {
      return d3.scaleOrdinal(d3.schemeTableau10).domain(sources.map(([id]) => id));
    },

    drawCorrelation(metric) {
      const containerId = `corr-chart-${metric.id}`;
      const container = d3.select(`#${containerId}`);
      if (!container.node()) return;
      container.selectAll("*").remove();

      const results = metric.results;
      const sources = Object.entries(results).filter(([, res]) => res && res.type === 'correlation');
      if (sources.length === 0) return;

      const margin = { top: 40, right: 50, bottom: 70, left: 100 }; // Publication-quality margins
      const width = container.node().clientWidth - margin.left - margin.right;
      const height = 400 - margin.top - margin.bottom;

      const svg = container.append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)
        .style("background-color", "white")
        .append("g")
        .attr("transform", `translate(${margin.left},${margin.top})`);

      const allData = [];
      sources.forEach(([, res]) => {
        res.data.forEach(d => allData.push(d));
      });

      const x = d3.scaleLinear()
        .domain(d3.extent(allData, d => d.lag))
        .range([0, width]);

      const y = d3.scaleLinear()
        .domain([-1, 1])
        .range([height, 0]);

      // X-axis with publication-quality styling
      svg.append("g")
        .attr("transform", `translate(0,${height})`)
        .call(d3.axisBottom(x).ticks(8).tickSize(6).tickPadding(8))
        .call(axis => {
          axis.selectAll("text")
            .style("font-size", "16px")
            .style("font-weight", "500");
          axis.select(".domain").style("stroke-width", "2px");
          axis.selectAll(".tick line").style("stroke-width", "2px");
        });

      // Y-axis with publication-quality styling
      svg.append("g")
        .call(d3.axisLeft(y).ticks(5).tickSize(6).tickPadding(8))
        .call(axis => {
          axis.selectAll("text")
            .style("font-size", "16px")
            .style("font-weight", "500");
          axis.select(".domain").style("stroke-width", "2px");
          axis.selectAll(".tick line").style("stroke-width", "2px");
        });

      // Zero line
      svg.append("line")
        .attr("x1", 0).attr("y1", y(0))
        .attr("x2", width).attr("y2", y(0))
        .attr("stroke", "#ccc")
        .attr("stroke-width", 2)
        .attr("stroke-dasharray", "6,4");

      // Axis labels with larger fonts
      svg.append("text")
        .attr("text-anchor", "middle")
        .attr("x", width/2)
        .attr("y", height + 55)
        .text("Lag")
        .style("font-size", "18px")
        .style("font-weight", "600");

      svg.append("text")
        .attr("text-anchor", "middle")
        .attr("transform", "rotate(-90)")
        .attr("y", -70)
        .attr("x", -height/2)
        .text("Autocorrelation")
        .style("font-size", "18px")
        .style("font-weight", "600");

      const color = d3.scaleOrdinal(d3.schemeTableau10).domain(sources.map(s => s[0]));

      sources.forEach(([id, res]) => {
        const line = d3.line()
          .x(d => x(d.lag))
          .y(d => y(d.value));

        svg.append("path")
          .datum(res.data)
          .attr("fill", "none")
          .attr("stroke", color(id))
          .attr("stroke-width", 3)
          .attr("d", line);

        svg.selectAll(`.dot-${id}`)
          .data(res.data)
          .enter().append("circle")
          .attr("cx", d => x(d.lag))
          .attr("cy", d => y(d.value))
          .attr("r", 4)
          .attr("fill", color(id))
          .attr("stroke", "white")
          .attr("stroke-width", 1.5);
      });

      // Legend with publication-quality styling
      const legend = svg.append("g").attr("transform", `translate(${width - 130}, 10)`);
      sources.forEach(([id], i) => {
        const lg = legend.append("g").attr("transform", `translate(0, ${i * 26})`);
        lg.append("rect")
          .attr("width", 18)
          .attr("height", 18)
          .attr("fill", color(id))
          .attr("stroke", "#333")
          .attr("stroke-width", 1);
        lg.append("text")
          .attr("x", 24)
          .attr("y", 13)
          .text(id)
          .style("font-size", "15px")
          .style("font-weight", "500")
          .attr("alignment-baseline", "middle");
      });
    },


    visualizeCriticalPoints(criticalPointsData, sourceId = 'original') {
      this.$store.commit('setCriticalPoints', {
        source: sourceId,
        data: criticalPointsData
      });
      if (criticalPointsData?.segmentation) {
        this.$store.commit('setSegmentation', {
          source: sourceId,
          data: criticalPointsData.segmentation
        });
      }

      // Switch to Data Visualization tab
      this.$nextTick(() => {
        const datavisTab = document.getElementById('datavis-tab');
        if (datavisTab) {
          datavisTab.click();
        }
      });

      this.$store.commit('setStatus', {
        type: 'success',
        message: `Critical points visualization activated for ${sourceId}. Switched to Data Visualization tab.`
      });
    },

    visualizeAllCriticalPoints(metric) {
      if (!metric || !metric.results) return;

      let count = 0;
      Object.entries(metric.results).forEach(([sourceId, data]) => {
        if (data && data.type === 'critical_points') {
          this.$store.commit('setCriticalPoints', {
            source: sourceId,
            data: data
          });
          if (data.segmentation) {
            this.$store.commit('setSegmentation', {
              source: sourceId,
              data: data.segmentation
            });
          }
          count++;
        }
      });

      if (count === 0) return;

      // Switch to Data Visualization tab
      this.$nextTick(() => {
        const datavisTab = document.getElementById('datavis-tab');
        if (datavisTab) {
          datavisTab.click();
        }
      });

        this.$store.commit('setStatus', {
        type: 'success',
        message: `Visualizing critical points for ${count} sources. Switched to Data Visualization tab.`
      });
    },


    // Compression visualization methods
    normalizeData(data, key) {
      if (!data || !data.length) return [];
      const values = data.map((d) => parseFloat(d[key]) || 0);

      const extent = d3.extent(values);
      const min = extent[0] ?? 0;
      const max = extent[1] ?? 1;

      return data.map((d) => ({
        ...d,
        [key]: max === min ? 0 : (parseFloat(d[key]) - min) / (max - min),
      }));
    },

    formatConfig(config) {
      if (!config) return "None";

      return Object.entries(config).map(([key, value]) => {
              let formattedKey = key.replace(/^.*?:/, "") // remove `sz3:` prefix
                                  .replace("_str", "") // remove `_str`
                                  .replace("_mode", "") // remove `_mode`
                                  .replace("_algo", "") // remove `_algo`
                                  .replace("_", " ") // replace `_` to ` `
                                  .replace(/\b\w/g, c => c.toUpperCase()); // Capitalize the first letter
              return `<strong>${formattedKey}:</strong> ${value}`;
      }).join("<br>"); // add linebreak
    },
    formatMetricKey(key) {
      if (!key) return '';
      const [category, metric] = key.split(':');
      const nice = (s) => (s || '')
        .replace(/_/g, ' ')
        .replace(/\b\w/g, c => c.toUpperCase());
      if (!metric) return nice(category);
      return `${nice(category)}: ${nice(metric)}`;
    },
    formatAxisLabel(key) {
      if (!key) return '';
      let raw = key;
      if (raw.startsWith('config:')) raw = raw.replace(/^config:/, '');
      const last = raw.includes(':') ? raw.split(':').pop() : raw;
      const cleaned = (last || '')
        .replace(/_/g, ' ')
        .replace(/\b\w/g, c => c.toUpperCase());
      if (cleaned.toLowerCase() === 'psnr') return 'PSNR';
      if (cleaned.toLowerCase() === 'dssim') return 'DSSIM';
      if (cleaned.toLowerCase() === 'mse') return 'MSE';
      if (cleaned.toLowerCase() === 'rmse') return 'RMSE';
      return cleaned;
    },
    formatNumber(value) {
      const num = Number(value);
      if (!Number.isFinite(num)) return '-';
      const abs = Math.abs(num);
      if (abs >= 1e6 || (abs > 0 && abs < 1e-4)) {
        return num.toExponential(2);
      }
      if (Number.isInteger(num)) return num.toString();
      if (abs >= 1000) return num.toFixed(0);
      if (abs >= 1) return num.toFixed(2).replace(/\.?0+$/, '');
      return num.toPrecision(2);
    },
    toSuperscript(num) {
      const superscripts = {
        '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
        '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
        '-': '⁻'
      };
      return String(num).split('').map(c => superscripts[c] || c).join('');
    },
    formatAsPowerOf10(value) {
      const num = Number(value);
      if (!Number.isFinite(num) || num === 0) return '0';
      const exponent = Math.log10(Math.abs(num));
      const roundedExp = Math.round(exponent);
      // Always show as 10^n for log scale plots
      return `10${this.toSuperscript(roundedExp)}`;
    },
    filterToPowersOf10(ticks) {
      // Filter ticks to only include values that are exact powers of 10
      return ticks.filter(tick => {
        if (tick === 0) return false;
        const exponent = Math.log10(Math.abs(tick));
        const roundedExp = Math.round(exponent);
        // Keep only ticks very close to powers of 10
        return Math.abs(exponent - roundedExp) < 0.01;
      });
    },
    getBaseForSource(sourceId) {
      if (!sourceId) return null;
      if (this.baseConfigurations && this.baseConfigurations[sourceId]) return sourceId;
      const comp = this.comparisonData?.[sourceId];
      if (comp?.base_name) return comp.base_name;
      const derived = this.derivedConfigurations || {};
      const baseNames = Object.keys(derived);
      for (const baseName of baseNames) {
        if (derived[baseName] && derived[baseName][sourceId]) return baseName;
      }
      if (this.baseConfigurations) {
        const baseIds = Object.keys(this.baseConfigurations);
        for (const baseId of baseIds) {
          if (sourceId.startsWith(`${baseId}-`)) return baseId;
        }
      }
      return null;
    },
    getConfigParamsForSource(sourceId) {
      const comp = this.comparisonData?.[sourceId];
      const config = comp?.compressor_config || {};
      return Object.entries(config).map(([key, value]) => ({
        key,
        label: this.formatMetricKey(key),
        value: this.formatNumber(value),
      }));
    },
    getComparisonValue(sourceId, key) {
      const comp = this.comparisonData?.[sourceId];
      if (!comp) return undefined;
      if (key.startsWith('config:')) {
        const cfgKey = key.replace(/^config:/, '');
        return comp?.compressor_config?.[cfgKey];
      }
      if (this.useLocalMetrics && comp?.local_metrics && comp.local_metrics[key] !== undefined) {
        return comp.local_metrics[key];
      }
      return comp?.metrics?.[key];
    },
    getLegendLabel(groupKey, groupValue) {
      if (!groupValue) return '';
      if (groupKey !== 'baseName') return groupValue;
      return groupValue;
    },
    addComparison() {
      if (!this.compressionMetricOptions.length) return;
      const id = `cmp-${this.comparisonCounter++}`;
      const rateOpt = this.compressionMetricOptions.find(opt => {
        const label = (opt.label || '').toLowerCase();
        const val = (opt.value || '').toLowerCase();
        return label.includes('bit rate') || val.includes('bit_rate') || val.includes('bitrate');
      });
      const psnrOpt = this.compressionMetricOptions.find(opt => {
        const label = (opt.label || '').toLowerCase();
        const val = (opt.value || '').toLowerCase();
        return label.includes('psnr') || val.includes('psnr');
      });
      const xKey = rateOpt?.value || this.compressionMetricOptions[0]?.value || '';
      const yKey = psnrOpt?.value || this.compressionMetricOptions[1]?.value || xKey;
      this.compressionComparisons.push({
        id,
        xKey,
        yKey,
        groupByBase: false,
      });
      this.$nextTick(() => this.drawComparisonCharts());
    },
    removeComparison(id) {
      this.compressionComparisons = this.compressionComparisons.filter(c => c.id !== id);
      this.$nextTick(() => this.drawComparisonCharts());
    },
    drawComparisonCharts() {
      if (!this.comparisonData) return;
      this.compressionComparisons.forEach(comp => {
        this.drawComparisonChart(comp);
      });
      this.$nextTick(() => {
        this.updateComparisonHighlighting();
      });
    },
    buildComparisonExportSvg(sourceSvg, legendEl) {
      const svgNS = 'http://www.w3.org/2000/svg';
      const width = sourceSvg.width.baseVal.value || sourceSvg.clientWidth || 800;
      const height = sourceSvg.height.baseVal.value || sourceSvg.clientHeight || 400;
      const legendHeight = legendEl ? Math.ceil(legendEl.getBoundingClientRect().height) : 0;
      const padding = legendHeight ? 4 : 0;
      const totalHeight = height + legendHeight + padding;

      const exportSvg = document.createElementNS(svgNS, 'svg');
      exportSvg.setAttribute('xmlns', svgNS);
      exportSvg.setAttribute('width', width);
      exportSvg.setAttribute('height', totalHeight);
      exportSvg.setAttribute('viewBox', `0 0 ${width} ${totalHeight}`);

      if (legendEl) {
        const items = Array.from(legendEl.querySelectorAll('div'))
          .map(item => {
            const swatch = item.querySelector('span');
            const labelNode = item.querySelectorAll('span')[1];
            const color = swatch ? swatch.style.backgroundColor : '#999';
            const label = labelNode ? labelNode.textContent.trim() : '';
            return { color, label };
          }) 
          .filter(item => item.label);

        const legendGroup = document.createElementNS(svgNS, 'g');
        const xStart = 0;
        const yStart = 0;
        const swatchSize = 16;
        const gap = 12;
        const rowHeight = 32;
        const paddingX = 10;
        const paddingY = 10;
        let x = xStart + paddingX;
        let y = yStart + paddingY;

        const approxTextWidth = (text) => Math.max(20, text.length * 14);
        items.forEach(item => {
          const labelWidth = approxTextWidth(item.label);
          const itemWidth = swatchSize + 8 + labelWidth + gap;
          if (x + itemWidth > width - paddingX) {
            x = xStart + paddingX;
            y += rowHeight;
          }

          const swatch = document.createElementNS(svgNS, 'rect');
          swatch.setAttribute('x', x);
          swatch.setAttribute('y', y + 1);
          swatch.setAttribute('width', swatchSize);
          swatch.setAttribute('height', swatchSize);
          swatch.setAttribute('rx', 2);
          swatch.setAttribute('ry', 2);
          swatch.setAttribute('fill', item.color || '#999');
          legendGroup.appendChild(swatch);

          const text = document.createElementNS(svgNS, 'text');
          text.setAttribute('x', x + swatchSize + 8);
          text.setAttribute('y', y + 15);
          text.setAttribute('font-size', '24');
          text.setAttribute('fill', '#222');
          text.textContent = item.label;
          legendGroup.appendChild(text);

          x += itemWidth;
        });

        exportSvg.appendChild(legendGroup);
      }

      const plotGroup = document.createElementNS(svgNS, 'g');
      plotGroup.setAttribute('transform', `translate(0, ${legendHeight + padding})`);
      plotGroup.appendChild(sourceSvg.cloneNode(true));
      exportSvg.appendChild(plotGroup);
      return exportSvg;
    },
    updateComparisonHighlighting() {
      this.compressionComparisons.forEach(comp => {
        const container = document.getElementById(`comparison-${comp.id}`);
        if (!container) return;
        const sel = this.comparisonGroupSelection?.[comp.id];
        d3.select(container).selectAll('circle')
          .attr('opacity', d => {
            if (!sel) return 1;
            const groupKey = comp.groupByBase ? 'baseName' : 'sourceId';
            return (d[groupKey] || d.sourceId) === sel ? 1 : 0.2;
          });
      });
    },
    drawComparisonChart(comp) {
      const container = document.getElementById(`comparison-${comp.id}`);
      if (!container) return;
      container.innerHTML = '';

      // Collect data points
      const points = [];
      Object.entries(this.comparisonData || {}).forEach(([sourceId, data]) => {
        const xVal = Number(this.getComparisonValue(sourceId, comp.xKey));
        const yVal = Number(this.getComparisonValue(sourceId, comp.yKey));
        if (!Number.isFinite(xVal) || !Number.isFinite(yVal)) return;
        const baseName = this.getBaseForSource(sourceId);
        points.push({
          sourceId,
          compressorId: data?.compressor_id || sourceId,
          baseName,
          x: xVal,
          y: yVal,
        });
      });
      if (!points.length) return;

      // Determine grouping
      const groupKey = comp.groupByBase ? 'baseName' : 'sourceId';
      const groups = Array.from(new Set(points.map(d => d[groupKey] || d.sourceId)))
        .filter(Boolean)
        .sort((a, b) => a.localeCompare(b));

      const legendLabelMap = new Map();
      groups.forEach(group => {
        const label = this.getLegendLabel(groupKey, group);
        legendLabelMap.set(group, label || group);
      });

      // Store group map for interactions
      const groupMap = {};
      groups.forEach(group => {
        groupMap[group] = points.filter(p => (p[groupKey] || p.sourceId) === group).map(p => p.sourceId);
      });
      this.comparisonGroupMap = { ...this.comparisonGroupMap, [comp.id]: groupMap };

      // Prepare traces (one per group)
      const traces = [];

      if (comp.groupByBase) {
        // Group points and create line+markers traces
        groups.forEach(group => {
          const groupPoints = points.filter(p => (p[groupKey] || p.sourceId) === group);
          const sorted = [...groupPoints].sort((a, b) => a.x - b.x);
          const label = legendLabelMap.get(group) || group;

          traces.push({
            name: label,
            x: sorted.map(d => d.x),
            y: sorted.map(d => d.y),
            text: sorted.map(d => d.sourceId),
            type: 'scatter',
            mode: 'lines+markers',
            line: { width: 3 },
            marker: {
              size: this.comparisonMarkerSize,
              opacity: this.comparisonMarkerOpacity,
              line: { width: 2, color: 'white' }
            },
            hovertemplate: '<b>%{text}</b><br>' +
                          this.formatMetricKey(comp.xKey) + ': %{x}<br>' +
                          this.formatMetricKey(comp.yKey) + ': %{y}<br>' +
                          '<extra></extra>'
          });
        });
      } else {
        // Just scatter points without lines
        groups.forEach(group => {
          const groupPoints = points.filter(p => (p[groupKey] || p.sourceId) === group);
          const label = legendLabelMap.get(group) || group;

          traces.push({
            name: label,
            x: groupPoints.map(d => d.x),
            y: groupPoints.map(d => d.y),
            text: groupPoints.map(d => d.sourceId),
            type: 'scatter',
            mode: 'markers',
            marker: {
              size: this.comparisonMarkerSize,
              opacity: this.comparisonMarkerOpacity,
              line: { width: 2, color: 'white' }
            },
            hovertemplate: '<b>%{text}</b><br>' +
                          this.formatMetricKey(comp.xKey) + ': %{x}<br>' +
                          this.formatMetricKey(comp.yKey) + ': %{y}<br>' +
                          '<extra></extra>'
          });
        });
      }

      // Calculate dynamic margins
      const xExtent = [Math.min(...points.map(d => d.x)), Math.max(...points.map(d => d.x))];
      const yExtent = [Math.min(...points.map(d => d.y)), Math.max(...points.map(d => d.y))];
      const ySample = Math.abs(yExtent[1]) > Math.abs(yExtent[0]) ? yExtent[1] : yExtent[0];
      const ySampleStr = this.formatNumber(ySample);
      const estimatedYWidth = ySampleStr.length * 14;
      const dynamicMarginLeft = Math.max(80, estimatedYWidth + 30);

      const layout = {
        xaxis: {
          title: {
            text: this.formatAxisLabel(comp.xKey),
            font: { size: 24, weight: 600 }
          },
          tickfont: { size: 20, weight: 500 },
          linewidth: 2.5,
          gridcolor: '#e0e0e0',
          rangemode: xExtent[0] >= 0 ? 'tozero' : 'normal'
        },
        yaxis: {
          title: {
            text: this.formatAxisLabel(comp.yKey),
            font: { size: 24, weight: 600 }
          },
          tickfont: { size: 20, weight: 500 },
          linewidth: 2.5,
          gridcolor: '#e0e0e0',
          rangemode: yExtent[0] >= 0 ? 'tozero' : 'normal'
        },
        height: this.comparisonChartHeight,
        margin: { l: dynamicMarginLeft, r: 40, t: 40, b: 60 },
        plot_bgcolor: 'white',
        paper_bgcolor: 'white',
        showlegend: this.comparisonShowLegend,
        legend: {
          font: { size: 15, weight: 500 },
          x: 1.02,
          xanchor: 'left',
          y: 1
        },
        hovermode: 'closest'
      };

      // Get actual rendered dimensions for export
      const actualWidth = container.clientWidth || 1000;

      const config = {
        responsive: true,
        displayModeBar: true,
        displaylogo: false,
        modeBarButtonsToRemove: ['lasso2d', 'select2d'],
        toImageButtonOptions: {
          format: 'png',
          filename: `comparison_${comp.id}`,
          height: this.comparisonChartHeight,
          width: actualWidth,
          scale: 2
        }
      };

      Plotly.newPlot(container, traces, layout, config);

      // Handle hover events for updating comparisonHoverPoint
      container.on('plotly_hover', (data) => {
        if (data.points && data.points.length > 0) {
          const point = data.points[0];
          const sourceId = point.text;
          this.comparisonHoverPoint = {
            ...this.comparisonHoverPoint,
            [comp.id]: {
              sourceId: sourceId,
              params: this.getConfigParamsForSource(sourceId),
            }
          };
        }
      });

      container.on('plotly_unhover', () => {
        const nextHover = { ...this.comparisonHoverPoint };
        delete nextHover[comp.id];
        this.comparisonHoverPoint = nextHover;
      });
    },

    drawBarCharts() {
      if (!this.comparisonData || Object.keys(this.comparisonData).length === 0) {
        return;
      }

      const categories = {};

      // Data processing logic
      const selectedKeys = this.selectedCompressionKeys;
      const entries = Object.entries(this.comparisonData);
      entries.forEach(([name, data]) => {
        if (data.metrics) {
          Object.entries(data.metrics).forEach(([key, value]) => {
            if (selectedKeys.size && !selectedKeys.has(key)) return;

            // Replicate the categorization logic from compressionMetricRows
            const parts = key.split(':');
            let category = 'other';
            let subMetric = key;

            if (parts.length > 1) {
              category = parts[0];
              subMetric = parts.slice(1).join(':');
            } else {
              if (['overall_compression_ratio', 'num_edits', 'edit_overhead'].includes(key) || key.startsWith('false_')) {
                category = 'qoi';
              }
            }

            if (!categories[category]) {
              categories[category] = [];
            }
            categories[category].push({
              compressor: name,
              compressor_id: data.compressor_id,
              metric: subMetric,
              value: isNaN(value) || value === "Infinity" || value === null ? null : parseFloat(value),
              rawValue: value,
              compressor_config: data.compressor_config,
            });
          });
        }
      });

      if (Object.keys(categories).length === 0) {
        return;
      }

      Object.entries(categories).forEach(([category, data]) => {
        const containerId = `stat-${category}`;
        const container = document.getElementById(containerId);
        if (!container) return;

        // Filter: Only include compressors that actually have data for this category
        const relevantCompressors = [...new Set(data.map(d => d.compressor))].sort();

        // Include metrics with any finite value (including zeros)
        const metrics = [...new Set(data.map((d) => d.metric))].filter(metric =>
          data.some(item => item.metric === metric && Number.isFinite(item.value))
        );
        if (metrics.length === 0) return; // Skip this category if no valid metrics

        // Check if we need log scale
        const finiteValues = data.map(d => d.value).filter(v => Number.isFinite(v));
        const hasNonPositive = finiteValues.some(v => v <= 0);

        // Prepare traces (one per compressor)
        const traces = relevantCompressors.map(compressor => {
          const yValues = metrics.map(metric => {
            const item = data.find(d => d.metric === metric && d.compressor === compressor);
            return item && Number.isFinite(item.value) ? item.value : null;
          });

          const customdata = metrics.map(metric => {
            const item = data.find(d => d.metric === metric && d.compressor === compressor);
            return item ? {
              rawValue: item.rawValue,
              config: this.formatConfig(item.compressor_config)
            } : null;
          });

          return {
            name: compressor,
            x: metrics,
            y: yValues,
            customdata: customdata,
            type: 'bar',
            hovertemplate: '<b>%{fullData.name}</b><br>' +
                          'Metric: %{x}<br>' +
                          'Value: %{customdata.rawValue}<br>' +
                          '<extra></extra>',
            marker: {
              line: { width: 0.5, color: '#fff' }
            }
          };
        });

        const layout = {
          title: {
            text: category,
            font: { size: 18, weight: 600 },
            y: 0.98
          },
          xaxis: {
            title: '',
            tickangle: -45,
            tickfont: { size: 16, weight: 500 },
            linewidth: 2
          },
          yaxis: {
            title: '',
            type: hasNonPositive ? 'linear' : 'log',
            tickfont: { size: 16, weight: 500 },
            linewidth: 2,
            gridcolor: '#e9ecef'
          },
          barmode: 'group',
          bargap: 0.2,
          bargroupgap: 0.05,
          height: 540,
          margin: { l: 120, r: 40, t: 90, b: 100 },
          plot_bgcolor: 'white',
          paper_bgcolor: 'white',
          legend: {
            font: { size: 12 },
            orientation: 'h',
            y: 1.15,
            x: 0.5,
            xanchor: 'center'
          },
          hovermode: 'closest'
        };

        // Get actual rendered dimensions for export
        const actualWidth = container.clientWidth || 1000;

        const config = {
          responsive: true,
          displayModeBar: true,
          displaylogo: false,
          modeBarButtonsToRemove: ['lasso2d', 'select2d'],
          toImageButtonOptions: {
            format: 'png',
            filename: `comparison_${category}`,
            height: 600,
            width: actualWidth,
            scale: 2
          }
        };

        Plotly.newPlot(containerId, traces, layout, config);
      });
    },
    refreshCompressionMetrics() {
      this.drawBarCharts();
      this.drawComparisonCharts();
    },
    exportMetrics() {
      if (!this.comparisonData) return;
      const exportData = {};
      Object.entries(this.comparisonData).forEach(([key, value]) => {
        const item = { ...value };
        delete item.decp_data;
        exportData[key] = item;
      });
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(exportData, null, 2));
      const downloadAnchorNode = document.createElement('a');
      downloadAnchorNode.setAttribute("href", dataStr);
      downloadAnchorNode.setAttribute("download", "fzvis_metrics_export.json");
      document.body.appendChild(downloadAnchorNode);
      downloadAnchorNode.click();
      downloadAnchorNode.remove();
    },
    importMetrics(event) {
      const file = event.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const importedData = JSON.parse(e.target.result);
          this.$store.commit('setComparisonData', importedData);
          this.$store.commit('setStatus', { type: 'success', message: 'Metrics imported successfully.' });
        } catch (error) {
          console.error('Error importing metrics:', error);
          this.$store.commit('setStatus', { type: 'danger', message: 'Failed to import metrics: invalid JSON.' });
        }
      };
      reader.readAsText(file);
      event.target.value = ''; // Reset file input
    },
  },

};
</script>

<template>
  <div class="container-fluid py-3 h-100 d-flex flex-column">
    <!-- Sub-tabs for Compression vs Analysis -->
    <ul class="nav nav-pills mb-3" role="tablist">
      <li class="nav-item" role="presentation">
        <button
          class="nav-link"
          :class="{ active: activeSubTab === 'compression' }"
          @click="activeSubTab = 'compression'"
          type="button"
        >
          <i class="bi bi-boxes me-1"></i>Compression Metrics
          <i
            v-if="comparisonData"
            class="bi bi-arrow-clockwise ms-2 refresh-icon"
            title="Refresh View"
            role="button"
            @click.stop="refreshCompressionMetrics"
          ></i>
        </button>
      </li>
      <li class="nav-item" role="presentation">
        <button
          class="nav-link"
          :class="{ active: activeSubTab === 'analysis' }"
          @click="activeSubTab = 'analysis'"
          type="button"
        >
          <i class="bi bi-graph-up me-1"></i>Data Analysis
        </button>
      </li>
    </ul>

    <!-- Compression Metrics Content -->
    <div v-show="activeSubTab === 'compression'" class="flex-grow-1 overflow-auto">
      <div class="d-flex justify-content-end gap-2 mb-2">
        <button
          type="button"
          class="btn btn-sm btn-outline-secondary"
          @click="$refs.importInput.click()"
        >
          <i class="bi bi-upload me-1"></i>Import
        </button>
        <input
          type="file"
          ref="importInput"
          @change="importMetrics"
          accept=".json"
          class="d-none"
        />
        <button
          type="button"
          class="btn btn-sm btn-outline-secondary"
          @click="exportMetrics"
          :disabled="!comparisonData"
        >
          <i class="bi bi-download me-1"></i>Export
        </button>
      </div>

      <div v-if="!comparisonData" class="alert alert-warning">
        <i class="bi bi-exclamation-triangle me-2"></i>No compression metrics available. Run a compressor to see comparison data.
      </div>
      <div v-else>
        <div class="d-flex flex-wrap align-items-center gap-2 mb-2">
          <button
            type="button"
            class="btn btn-sm btn-outline-primary"
            @click="addComparison"
            :disabled="compressionMetricOptions.length < 1"
          >
            <i class="bi bi-plus-circle me-1"></i>Add Comparison
          </button>
          <div class="form-check form-switch ms-2">
            <input
              class="form-check-input"
              type="checkbox"
              id="toggleRawCompression"
              v-model="showRawCompression"
            >
            <label class="form-check-label" for="toggleRawCompression">
              Show Raw Metrics
            </label>
          </div>
          <div v-if="hasLocalMetrics" class="form-check form-switch ms-3">
            <input
              class="form-check-input"
              type="checkbox"
              id="toggleLocalMetrics"
              v-model="useLocalMetrics"
            >
            <label class="form-check-label fw-bold text-primary" for="toggleLocalMetrics">
              <i class="bi bi-bounding-box me-1"></i>Use ROI Metrics
            </label>
          </div>
        </div>


        <div v-if="compressionComparisons.length" class="mb-3">
          <div
            v-for="comp in compressionComparisons"
            :key="comp.id"
            class="card mb-2"
          >
            <div class="card-body py-2">
              <div class="d-flex flex-wrap align-items-center gap-2">
                <div class="input-group input-group-sm" style="max-width: 280px;">
                  <span class="input-group-text">X</span>
                  <select class="form-select" v-model="comp.xKey" @change="drawComparisonCharts">
                    <option v-for="opt in compressionMetricOptions" :key="opt.value" :value="opt.value">
                      {{ opt.label }}
                    </option>
                  </select>
                </div>
                <div class="input-group input-group-sm" style="max-width: 280px;">
                  <span class="input-group-text">Y</span>
                  <select class="form-select" v-model="comp.yKey" @change="drawComparisonCharts">
                    <option v-for="opt in compressionMetricOptions" :key="opt.value" :value="opt.value">
                      {{ opt.label }}
                    </option>
                  </select>
                </div>
                <div class="form-check form-switch">
                  <input class="form-check-input" type="checkbox" :id="`group-${comp.id}`" v-model="comp.groupByBase" @change="drawComparisonCharts">
                  <label class="form-check-label" :for="`group-${comp.id}`">Group by base</label>
                </div>
                <div class="form-check form-switch">
                  <input class="form-check-input" type="checkbox" :id="`legend-${comp.id}`" v-model="comparisonShowLegend">
                  <label class="form-check-label" :for="`legend-${comp.id}`">Show legend</label>
                </div>
                <div class="d-flex align-items-center gap-2" style="min-width: 220px;">
                  <label class="small text-muted mb-0" :for="`marker-size-${comp.id}`">Dot size</label>
                  <input
                    :id="`marker-size-${comp.id}`"
                    v-model.number="comparisonMarkerSize"
                    type="range"
                    class="form-range m-0"
                    min="6"
                    max="36"
                    step="1"
                    @input="drawComparisonCharts"
                  >
                  <span class="small fw-semibold marker-size-value">{{ comparisonMarkerSize }}</span>
                </div>
                <div class="d-flex align-items-center gap-2" style="min-width: 220px;">
                  <label class="small text-muted mb-0" :for="`chart-height-${comp.id}`">Height</label>
                  <input
                    :id="`chart-height-${comp.id}`"
                    v-model.number="comparisonChartHeight"
                    type="range"
                    class="form-range m-0"
                    min="300"
                    max="1000"
                    step="50"
                    @input="drawComparisonCharts"
                  >
                  <span class="small fw-semibold marker-size-value">{{ comparisonChartHeight }}</span>
                </div>
                <div class="d-flex align-items-center gap-2" style="min-width: 220px;">
                  <label class="small text-muted mb-0" :for="`marker-opacity-${comp.id}`">Opacity</label>
                  <input
                    :id="`marker-opacity-${comp.id}`"
                    v-model.number="comparisonMarkerOpacity"
                    type="range"
                    class="form-range m-0"
                    min="0.1"
                    max="1.0"
                    step="0.05"
                    @input="drawComparisonCharts"
                  >
                  <span class="small fw-semibold marker-size-value">{{ comparisonMarkerOpacity.toFixed(2) }}</span>
                </div>
                <button class="btn btn-sm btn-outline-danger ms-auto" @click="removeComparison(comp.id)">
                  Remove
                </button>
              </div>
              <div :id="`comparison-${comp.id}`" class="mt-2"></div>
              <div v-if="comparisonHoverPoint[comp.id]" class="mt-2 small">
                <div class="fw-semibold">
                  Config: {{ comparisonHoverPoint[comp.id].sourceId }}
                </div>
                <div class="d-flex flex-wrap gap-2">
                  <span
                    v-for="param in comparisonHoverPoint[comp.id].params"
                    :key="`${comparisonHoverPoint[comp.id].sourceId}-${param.key}`"
                    class="badge bg-light text-dark border"
                  >
                    {{ param.label }}={{ param.value }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="showRawCompression" class="table-responsive mb-3">
          <div class="d-flex flex-wrap align-items-center gap-2 mb-2">
            <input
              type="text"
              class="form-control form-control-sm"
              style="max-width: 260px;"
              v-model="rawMetricFilterText"
              placeholder="Filter by config or metric"
            >
            <select class="form-select form-select-sm" style="max-width: 200px;" v-model="rawMetricCategory">
              <option value="all">All categories</option>
              <option v-for="cat in compressionMetricCategories" :key="cat" :value="cat">
                {{ formatMetricKey(cat) }}
              </option>
            </select>
          </div>
          <div v-if="Object.keys(groupedCompressionRows).length === 0" class="text-muted small">
            No metrics match the current filters.
          </div>
          <div v-for="(rows, category) in groupedCompressionRows" :key="category" class="mb-3">
            <div class="fw-semibold mb-1">{{ formatMetricKey(category) }}</div>
            <table class="table table-sm table-striped">
              <thead>
                <tr>
                  <th>Config</th>
                  <th>Compressor</th>
                  <th>Metric</th>
                  <th class="text-end">Value</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in rows" :key="`${row.sourceId}-${row.key}`">
                  <td>{{ row.sourceId }}</td>
                  <td>{{ row.compressorId }}</td>
                  <td>{{ row.label }}</td>
                  <td class="text-end">{{ formatNumber(row.value) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Charts -->
        <div v-if="compressionCategoriesList.length === 0" class="text-muted small">
          No metric data to display.
        </div>
        <div v-else class="d-flex flex-column gap-3">
          <div
            v-for="category in compressionCategoriesList"
            :key="category"
            class="card"
          >
            <div class="card-header d-flex flex-wrap align-items-center gap-2">
              <span class="fw-semibold">{{ formatMetricKey(category) }}</span>
              <div class="ms-auto" style="min-width: 260px;">
                <multiselect
                  v-model="compressionMetricSelection[category]"
                  :options="availableCompressionMetricSelections[category]"
                  :multiple="true"
                  :searchable="true"
                  :close-on-select="false"
                  :clear-on-select="false"
                  :preserve-search="true"
                  label="label"
                  track-by="value"
                  placeholder="Select metrics"
                  @update:modelValue="refreshCompressionMetrics"
                />
              </div>
            </div>
            <div class="card-body">
              <div :id="`stat-${category}`" class="container-fluid"></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Dataset Analysis Content -->
    <div v-show="activeSubTab === 'analysis'" class="flex-grow-1 overflow-auto">
      <div class="analysis-section">
        <!-- Dataset Status Alert -->
        <div v-if="!canCompute" class="alert alert-warning d-flex align-items-center mb-3" role="alert">
          <i class="bi bi-exclamation-triangle-fill me-2"></i>
          <div>
            <strong>No dataset loaded.</strong> Please load a dataset  before computing metrics.
          </div>
        </div>

        <!-- Dataset Info -->
        <div v-else class="alert alert-success d-flex align-items-center mb-3" role="alert">
          <i class="bi bi-check-circle-fill me-2"></i>
          <div>
            <strong>Dataset loaded:</strong> {{ dataset.name || 'Unnamed' }}
            <span class="ms-2 text-muted small">
              ({{ dataset.dimensions.join(' × ') }}, {{ dataset.precision }})
            </span>
          </div>
        </div>

        <!-- Header -->
        <div class="d-flex justify-content-between align-items-center mb-3">
          <h6 class="mb-0">
            <i class="bi bi-graph-up me-2"></i>Quantities of Interest Analysis
          </h6>
          <button
            class="btn btn-sm btn-outline-secondary"
            @click="clearAllMetrics"
            :disabled="activeMetrics.length === 0"
          >
            <i class="bi bi-trash me-1"></i>Clear All
          </button>
        </div>

        <!-- Sources Selection -->
        <div class="card mb-3">
          <div class="card-header bg-light py-2 d-flex justify-content-between align-items-center">
            <h6 class="mb-0 small">Data Sources to Analyze</h6>
            <div class="d-flex align-items-center gap-2">
              <button
                type="button"
                class="btn btn-sm"
                :class="allSelectableSourcesSelected ? 'btn-outline-danger' : 'btn-outline-primary'"
                :disabled="!hasSelectableSources"
                @click="toggleAllSources"
              >
                {{ allSelectableSourcesSelected ? 'Deselect all' : 'Select all' }}
              </button>
              <span class="badge bg-secondary">{{ selectedSources.length }} selected</span>
            </div>
          </div>
          <div class="card-body py-2">
            <div class="d-flex flex-wrap gap-2">
              <button
                v-for="source in availableSources"
                :key="source.id"
                class="btn btn-sm"
                :class="selectedSources.includes(source.id) ? 'btn-success' : 'btn-outline-secondary'"
                :disabled="source.id === 'original'"
                @click="toggleSource(source.id)"
                :title="source.id === 'original' ? 'Original data is always required for comparison' : ''"
              >
                <i class="bi" :class="selectedSources.includes(source.id) ? 'bi-check-circle-fill' : 'bi-circle'"></i>
                <span class="ms-1">{{ source.name }}</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Metrics Palette -->
        <div class="card mb-3">
          <div class="card-header bg-light py-2">
            <h6 class="mb-0 small">Available QoIs</h6>
          </div>
          <div class="card-body">
            <div class="row g-2">
              <div
                v-for="metric in availableMetrics"
                :key="metric.id"
                class="col-md-6 col-lg-4"
              >
                <div
                  class="metric-card p-2 border rounded cursor-pointer d-flex"
                  :class="{ 'border-primary': isMetricActive(metric.id) }"
                  @click="toggleMetric(metric)"
                >
                  <div class="d-flex align-items-start w-100">
                    <i :class="metric.icon" class="me-2 mt-1 flex-shrink-0"></i>
                    <div class="flex-grow-1">
                      <div class="fw-semibold small">{{ metric.name }}</div>
                      <div class="text-muted metric-description">{{ metric.description }}</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Active Metrics -->
        <div v-if="activeMetrics.length === 0" class="text-center text-muted py-5">
          <i class="bi bi-graph-up" style="font-size: 3rem;"></i>
          <p class="mt-3">No metrics activated yet. Click on a metric above to activate it.</p>
        </div>

        <div v-else class="metrics-container">
          <div
            v-for="metric in activeMetrics"
            :key="metric.id"
            class="card mb-3"
          >
            <div class="card-header d-flex justify-content-between align-items-center py-2">
              <div class="d-flex align-items-center">
                <i :class="metric.icon" class="me-2"></i>
                <span class="fw-semibold small">{{ metric.name }}</span>
              </div>
              <div class="d-flex gap-2 align-items-center">
                <button
                  class="btn btn-sm btn-outline-primary"
                  @click="computeMetric(metric)"
                  :disabled="!canCompute || metric.computing"
                >
                  <span v-if="metric.computing" class="spinner-border spinner-border-sm me-1"></span>
                  <i v-else class="bi bi-play-fill me-1"></i>
                  {{ metric.computing ? 'Computing...' : 'Compute' }}
                </button>
                <!-- Visualize button for critical points -->
                <button
                  v-if="metric.id === 'critical_points' && Object.keys(metric.results).length > 0"
                  class="btn btn-sm btn-success"
                  @click="visualizeAllCriticalPoints(metric)"
                >
                  <i class="bi bi-eye me-1"></i>Visualize
                </button>
                <span v-if="!canCompute" class="text-muted small">
                  <i class="bi bi-info-circle me-1"></i>Load dataset first
                </span>
              </div>
            </div>
            <div class="card-body">
              <!-- Metric Configuration -->
              <div v-if="metric.parameters && metric.parameters.length > 0" class="mb-3">
                <h6 class="small text-muted mb-2">Parameters</h6>
                <div class="row g-2">
                  <div
                    v-for="param in metric.parameters"
                    :key="param.name"
                    class="col-md-6"
                  >
                    <label v-if="param.type !== 'boolean'" class="form-label small mb-1">{{ param.label }}</label>
                    <input
                      v-if="param.type === 'number'"
                      type="number"
                      class="form-control form-control-sm"
                      v-model.number="param.value"
                      :min="param.min"
                      :max="param.max"
                      :step="param.step"
                    />
                    <select
                      v-else-if="param.type === 'select'"
                      class="form-select form-select-sm"
                      v-model="param.value"
                    >
                      <option v-for="opt in param.options" :key="opt" :value="opt">{{ opt }}</option>
                    </select>
                    <div v-else-if="param.type === 'boolean'" class="form-check form-switch">
                      <input
                        class="form-check-input"
                        type="checkbox"
                        :id="`metric-${metric.id}-${param.name}`"
                        v-model="param.value"
                      />
                      <label class="form-check-label small" :for="`metric-${metric.id}-${param.name}`">
                        {{ param.label }}
                      </label>
                    </div>
                    <input
                      v-else
                      type="text"
                      class="form-control form-control-sm"
                      v-model="param.value"
                    />
                  </div>
                </div>
              </div>

              <!-- Results Display -->
              <div v-if="Object.keys(metric.results).length > 0" class="metric-result">
                <h6 class="small text-muted mb-3">Comparison Results</h6>
                <div v-if="metric.id === 'dssim' || metric.id === 'critical_points'" class="mb-3">
                  <div class="btn-group btn-group-sm">
                    <button
                      class="btn"
                      :class="metric.viewMode === 'raw' ? 'btn-primary' : 'btn-outline-primary'"
                      @click="setMetricView(metric, 'raw')"
                    >
                      Raw
                    </button>
                    <button
                      class="btn"
                      :class="metric.viewMode === 'plot' ? 'btn-primary' : 'btn-outline-primary'"
                      @click="setMetricView(metric, 'plot')"
                    >
                      Plot
                    </button>
                  </div>
                </div>
                <div v-if="metric.viewMode === 'plot' && (metric.id === 'dssim' || metric.id === 'critical_points')" :id="`metric-plot-${metric.id}`" class="mb-3"></div>
                <div v-if="metric.id === 'critical_points' && metric.viewMode === 'plot'" class="mb-3">
                  <label class="form-label small fw-semibold">Select Fault Metrics</label>
                  <multiselect
                    v-model="metric.plotFields"
                    :options="criticalPointPlotOptions"
                    :multiple="true"
                    :searchable="true"
                    :close-on-select="false"
                    :clear-on-select="false"
                    label="label"
                     track-by="value"
                    placeholder="Select metrics"
                    @update:modelValue="drawCriticalPointsPlot(metric)"
                  />
                </div>
                <div v-if="metric.id === 'critical_points' && metric.viewMode === 'plot'" class="mb-3 d-flex flex-wrap align-items-center gap-3">
                  <div>
                    <label class="form-label small fw-semibold mb-1">Value Histogram</label>
                    <select class="form-select form-select-sm" v-model="metric.histogramMode" @change="drawCriticalPointsValueHistogram(metric)">
                      <option value="min">Local Min</option>
                      <option value="max">Local Max</option>
                      <option value="both">Min + Max</option>
                    </select>
                  </div>
                </div>
                <div v-if="metric.id === 'critical_points' && metric.viewMode === 'plot'" class="mb-3">
                  <div class="small text-muted mb-1">Critical Point Value Distribution</div>
                  <div :id="`metric-plot-${metric.id}-values`"></div>
                </div>
                
                <!-- Statistics Comparison Table (Custom for stats) -->
                <div v-if="metric.id === 'statistics'" class="result-table overflow-auto">
                  <table class="table table-sm table-bordered mb-0 small">
                    <thead class="bg-light">
                      <tr>
                        <th>Metric</th>
                        <th v-for="sourceId in selectedSources" :key="sourceId" class="text-center">
                          {{ sourceId }}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      <!-- Get all unique headers from all results -->
                      <tr v-for="headerIdx in [0, 1, 2, 3, 4, 5, 6, 7]" :key="headerIdx">
                        <template v-if="metric.results['original'] && metric.results['original'].rows[headerIdx]">
                          <td class="fw-bold">{{ metric.results['original'].rows[headerIdx][0] }}</td>
                          <td v-for="sourceId in selectedSources" :key="sourceId" class="text-center">
                            {{ metric.results[sourceId] ? metric.results[sourceId].rows[headerIdx][1] : '-' }}
                          </td>
                        </template>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <!-- Power Spectrum Comparison Chart -->
                <div v-else-if="metric.id === 'power_spectrum'" class="result-chart">
                  <div class="d-flex align-items-center gap-2 mb-2 flex-wrap">
                    <button class="btn btn-sm btn-outline-primary" @click="zoomPowerSpectrum(metric, 1.6)">
                      <i class="bi bi-zoom-in me-1"></i>Zoom In
                    </button>
                    <button class="btn btn-sm btn-outline-primary" @click="zoomPowerSpectrum(metric, 1 / 1.6)">
                      <i class="bi bi-zoom-out me-1"></i>Zoom Out
                    </button>
                    <button class="btn btn-sm btn-outline-secondary" @click="resetPowerSpectrumView(metric)">
                      <i class="bi bi-arrow-counterclockwise me-1"></i>Reset
                    </button>
                    <button
                      v-if="powerSpectrumState.roi"
                      class="btn btn-sm btn-outline-danger"
                      @click="clearPowerSpectrumROI(metric)"
                    >
                      <i class="bi bi-x-circle me-1"></i>Clear ROI
                    </button>
                    <div class="d-flex align-items-center gap-2 ms-2">
                      <label class="small mb-0">Height:</label>
                      <input
                        type="number"
                        v-model.number="powerSpectrumState.chartHeight"
                        @change="drawPowerSpectrum(metric)"
                        class="form-control form-control-sm"
                        style="width: 80px;"
                        min="200"
                        max="1000"
                        step="50"
                      />
                    </div>
                    <div v-if="powerSpectrumState.roi" class="ms-auto text-muted small">
                      ROI: {{ powerSpectrumState.roi[0].toPrecision(3) }} - {{ powerSpectrumState.roi[1].toPrecision(3) }}
                    </div>
                    <div v-else class="ms-auto text-muted small">
                      Drag to select ROI
                    </div>
                  </div>
                  <div :id="`ps-chart-${metric.id}`" class="w-100" :style="`height: ${powerSpectrumState.chartHeight}px;`"></div>

                  <!-- Power Spectrum Relative Error Chart -->
                  <div class="mt-3">
                    <div class="d-flex align-items-center gap-2 mb-2">
                      <h6 class="text-muted small mb-0">Spectrum Relative Error</h6>
                      <div class="d-flex align-items-center gap-2 ms-auto">
                        <label class="small mb-0">Height:</label>
                        <input
                          type="number"
                          v-model.number="powerSpectrumState.errorChartHeight"
                          @change="drawPowerSpectrumRelativeError(metric)"
                          class="form-control form-control-sm"
                          style="width: 80px;"
                          min="200"
                          max="800"
                          step="50"
                        />
                      </div>
                    </div>
                    <div :id="`ps-error-chart-${metric.id}`" class="w-100" :style="`height: ${powerSpectrumState.errorChartHeight}px;`"></div>
                  </div>
                </div>

                <!-- Correlation Comparison Chart -->
                <div v-else-if="metric.id === 'correlation'" class="result-chart">
                  <div :id="`corr-chart-${metric.id}`" class="w-100" style="height: 400px;"></div>
                </div>

                <!-- Histogram Comparison Chart -->
                <div v-else-if="metric.id === 'histogram'" class="result-chart">
                  <div :id="`histogram-chart-${metric.id}`" class="w-100" style="height: 400px;"></div>
                </div>

                <!-- Default Multi-Source Display for other types -->
                <div
                  v-else-if="metric.id !== 'dssim' && metric.id !== 'critical_points' || metric.viewMode === 'raw'"
                  class="sources-results"
                >
                  <div
                    v-for="sourceId in selectedSources.filter(s => !(metric.id === 'dssim' && s === 'original'))"
                    :key="sourceId"
                    class="mb-3 p-2 border rounded"
                  >
                    <div class="d-flex justify-content-between align-items-center mb-2">
                      <span class="badge bg-secondary">{{ sourceId }}</span>
                    </div>

                    <div v-if="!metric.results[sourceId]" class="text-muted x-small py-2 text-center">
                      <div v-if="metric.computing" class="d-flex align-items-center justify-content-center gap-2">
                        <span class="spinner-border spinner-border-sm text-primary" role="status"></span>
                        <span class="fst-italic">Computing...</span>
                      </div>
                      <span v-else>Not computed. Click "Compute" to run.</span>
                    </div>

                    <!-- Scalar Result -->
                    <div v-else-if="metric.results[sourceId].type === 'scalar'" class="result-scalar">
                      <div class="alert alert-info mb-0 py-1 small">
                        <strong>{{ metric.results[sourceId].label }}:</strong> {{ metric.results[sourceId].value }}
                      </div>
                    </div>

                    <!-- Table Result -->
                    <div v-else-if="metric.results[sourceId].type === 'table'" class="result-table">
                      <table class="table table-sm table-bordered mb-0 x-small">
                        <thead>
                          <tr>
                            <th v-for="header in metric.results[sourceId].headers" :key="header">{{ header }}</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr v-for="(row, idx) in metric.results[sourceId].rows" :key="idx">
                            <td v-for="(cell, cidx) in row" :key="cidx">{{ cell }}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>

                    <!-- Critical Points Result -->
                    <div v-else-if="metric.results[sourceId].type === 'critical_points'" class="result-critical-points x-small">
                        <div class="d-flex flex-column gap-1">
                          <div class="d-flex gap-3">
                             <div><strong>Minima:</strong> {{ metric.results[sourceId].minima.count }}</div>
                             <div><strong>Maxima:</strong> {{ metric.results[sourceId].maxima.count }}</div>
                             <div v-if="metric.results[sourceId].saddles"><strong>Saddles:</strong> {{ metric.results[sourceId].saddles.count }}</div>
                          </div>
                          <div v-if="metric.results[sourceId].faults" class="mt-2 pt-2 border-top text-danger">
                            <div class="fw-bold mb-1">Topology Faults:</div>
                            <div class="d-flex gap-3">
                              <div><strong>False Min:</strong> {{ metric.results[sourceId].faults.num_false_min }}</div>
                              <div><strong>False Max:</strong> {{ metric.results[sourceId].faults.num_false_max }}</div>
                              <div><strong>False Segmentation Labels:</strong> {{ metric.results[sourceId].faults.num_false_labels }}</div>
                            </div>
                          </div>
                        </div>
                    </div>

                    <!-- Image Result -->
                    <div v-else-if="metric.results[sourceId].type === 'image'" class="result-image">
                      <img :src="metric.results[sourceId].src" class="img-fluid" :alt="metric.name" />
                    </div>

                    <!-- Text Result -->
                    <div v-else-if="metric.results[sourceId].type === 'text'" class="result-text">
                      <pre class="bg-light p-2 rounded small mb-0">{{ metric.results[sourceId].content }}</pre>
                    </div>
                  </div>
                </div>
              </div>

              <div v-else-if="!metric.computing" class="text-muted small">
                <i class="bi bi-info-circle me-1"></i>Click "Compute" to calculate this metric
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.metric-card {
  cursor: pointer;
  transition: all 0.2s ease;
  min-height: 70px;
}

.metric-card:hover {
  background-color: #f8f9fa;
  border-color: #0d6efd !important;
}

.metric-description {
  font-size: 0.7rem;
  line-height: 1.3;
}

.metrics-container {
  animation: fadeIn 0.3s ease;
}

.comparison-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  margin-top: 8px;
}

.comparison-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 6px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.03);
}

.comparison-legend-swatch {
  width: 10px;
  height: 10px;
  border-radius: 3px;
  display: inline-block;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.result-image img {
  max-width: 100%;
  border-radius: 4px;
  border: 1px solid #dee2e6;
}

.result-text pre {
  max-height: 300px;
  overflow-y: auto;
}

.cursor-pointer {
  cursor: pointer;
}

.x-small {
  font-size: 0.75rem;
}

.btn-xs {
  padding: 0.1rem 0.25rem;
  font-size: 0.7rem;
  border-radius: 0.15rem;
}

.btn-xs i {
  font-size: 0.7rem;
}

.refresh-icon {
  color: #0d6efd;
  opacity: 0.8;
  transition: opacity 0.15s ease;
}

.nav-link.active .refresh-icon {
  color: #ffffff;
  opacity: 0.9;
}

.refresh-icon:hover {
  opacity: 1;
}
</style>

<style src="vue-multiselect/dist/vue-multiselect.min.css"></style>
