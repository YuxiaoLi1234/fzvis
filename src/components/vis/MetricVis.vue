<script>
import * as d3 from "d3";
import { mapState } from 'vuex';
import axios from 'axios';

export default {
  name: "MetricVis",

  data() {
    return {
      tooltip: null,
      activeSubTab: 'analysis', // 'compression' or 'analysis'
      // Analysis-related data
      activeMetrics: {},
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
          id: 'power_spectrum',
          name: 'Power Spectrum',
          icon: 'bi bi-graph-up-arrow text-primary',
          description: 'Compute and visualize frequency domain characteristics',
          parameters: [],
        },
      ],
    };
  },
  
  computed: {
    ...mapState(['dataset']),
    comparisonData() {
      return this.$store.state.comparisonData;
    },
    canCompute() {
      return this.dataset && this.dataset.content;
    },
  },
  
  watch: {
    // Watch for changes in comparisonData to redraw charts
    comparisonData: {
      handler(newData) {
        if (newData) {
          setTimeout(() => {
            this.$nextTick(() => {
              this.drawBarCharts();
            });
          }, 300);
        }
      },
      deep: true,
    },
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
      return !!this.activeMetrics[metricId];
    },

    toggleMetric(metricTemplate) {
      if (this.isMetricActive(metricTemplate.id)) {
        // Remove metric if already active
        delete this.activeMetrics[metricTemplate.id];
      } else {
        // Add metric if not active
        const metric = {
          ...metricTemplate,
          parameters: metricTemplate.parameters ? 
            JSON.parse(JSON.stringify(metricTemplate.parameters)) : [],
          computing: false,
          result: null,
        };
        this.activeMetrics[metricTemplate.id] = metric;
      }
    },

    clearAllMetrics() {
      this.activeMetrics = {};
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
      metric.result = null;

      try {
        const params = {};
        if (metric.parameters) {
          metric.parameters.forEach(p => {
            params[p.name] = p.value;
          });
        }

        params.dimensions = this.dataset.dimensions;
        params.precision = this.dataset.precision;

        // Prefer fast path using data_key; fallback to upload-and-compute
        let dataKey = this.dataset.data_key;
        if (!dataKey && this.dataset.content instanceof ArrayBuffer) {
          dataKey = await this.computeDataKey();
          this.$store.commit('setFileData', { 
            dataset: { ...this.dataset, data_key: dataKey } 
          });
        }

        let response;
        if (dataKey) {
          // Try fast path
          const fastForm = new FormData();
          fastForm.append('metric_type', metric.id);
          fastForm.append('parameters', JSON.stringify(params));
          fastForm.append('data_key', dataKey);
          try {
            response = await axios.post('/api/analysis/compute', fastForm);
          } catch (err) {
            const serverMsg = err?.response?.data?.error;
            if (err?.response?.status === 404 && serverMsg === 'DATA_KEY_NOT_FOUND') {
              // Fallback: upload and compute, also store under the same key
              const uploadForm = new FormData();
              uploadForm.append('metric_type', metric.id);
              uploadForm.append('parameters', JSON.stringify(params));
              uploadForm.append('data_key', dataKey);
              const blob = new Blob([this.dataset.content], { type: 'application/octet-stream' });
              uploadForm.append('data', blob, this.dataset.name || 'data.bin');
              response = await axios.post('/api/analysis/compute/upload', uploadForm, {
                headers: { 'Content-Type': 'multipart/form-data' },
              });
              // Persist the data_key in store for subsequent calls
              if (response?.data?.data_key) {
                this.$store.commit('setFileData', { dataset: { ...this.dataset, data_key: response.data.data_key } });
              } else if (dataKey) {
                this.$store.commit('setFileData', { dataset: { ...this.dataset, data_key: dataKey } });
              }
            } else {
              throw err;
            }
          }
        }

        // If fast path was not possible or not used, do direct compute upload (legacy)
        if (!response) {
          const formData = new FormData();
          formData.append('metric_type', metric.id);
          formData.append('parameters', JSON.stringify(params));
          const blob = new Blob([this.dataset.content], { type: 'application/octet-stream' });
          formData.append('data', blob, this.dataset.name || 'data.bin');
          response = await axios.post('/api/analysis/compute', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
          });
        }

        metric.result = response?.data?.result;

        this.$store.commit('setStatus', { 
          type: 'success', 
          message: `${metric.name} computed successfully` 
        });
        this.$store.commit('addHistory', { 
          kind: 'analysis', 
          text: `Computed ${metric.name}`, 
          timestamp: Date.now() 
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

    // Compression visualization methods
    normalizeData(data, key) {
      const values = data.map((d) => parseFloat(d[key]) || 0);
      const min = Math.min(...values);
      const max = Math.max(...values);
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

    drawBarCharts() {
      const that = this;
      if (!this.comparisonData || Object.keys(this.comparisonData).length === 0) {
        return;
      }

      const categories = {};
      const compressorNames = [];

      // Data processing logic
      Object.entries(this.comparisonData).forEach(([name, data]) => {
        compressorNames.push(name);
        if (data.metrics) {
          Object.entries(data.metrics).forEach(([key, value]) => {
            const [category, subMetric] = key.split(":");
            if (!categories[category]) {
              categories[category] = [];
            }
            categories[category].push({
              compressor: name,
              compressor_id: data.compressor_id,
              metric: subMetric,
              value: isNaN(value) || value === "Infinity" || value === null ? 0 : parseFloat(value),
              compressor_config: data.compressor_config,
            });
          });
        }
      });

      const statDiv = d3.select("#stat");
      statDiv.selectAll("*").remove();

      if (Object.keys(categories).length === 0) {
        statDiv.append("p").attr("class", "text-muted").text("No metric data to display.");
        return;
      }

      const containerWidth = document.getElementById("stat").clientWidth;
      const compressors = [...new Set(compressorNames)];

      // Use a more modern color scheme
      const colorScale = d3.scaleOrdinal().domain(compressors).range(d3.schemeTableau10);

      // Improved Tooltip
      if (this.tooltip == null) {
        this.tooltip = d3
          .select("body")
          .append("div")
          .attr("class", "tooltip")
          .style("position", "absolute")
          .style("background", "rgba(255, 255, 255, 0.95)")
          .style("color", "#333")
          .style("border", "1px solid #ddd")
          .style("box-shadow", "0 3px 8px rgba(0,0,0,0.15)")
          .style("padding", "8px 12px")
          .style("border-radius", "8px")
          .style("font-size", "12px")
          .style("pointer-events", "none")
          .style("opacity", 0)
          .style("transition", "opacity 0.2s");
      }
      const tooltip = this.tooltip;

      Object.entries(categories).forEach(([category, data]) => {
        const width = Math.max(0, containerWidth * 0.96);
        const height = 350;
        const margin = { top: 80, right: 20, bottom: 30, left: 50 }; // Increased top margin for legend

        // Filter metrics to only those with at least one value > 0
        const metrics = [...new Set(data.map((d) => d.metric))].filter(metric =>
          data.some(item => item.metric === metric && item.value > 0)
        );
        if (metrics.length === 0) return; // Skip this category if no valid metrics

        const svg = statDiv
          .append("svg")
          .attr("width", width)
          .attr("height", height + margin.top + margin.bottom)
          .append("g")
          .attr("transform", `translate(${margin.left}, ${margin.top})`);

        const chartWidth = width - margin.left - margin.right;
        const chartHeight = height - margin.top - margin.bottom;

        const x0 = d3.scaleBand().domain(metrics).range([0, chartWidth]).padding(0.2);
        const x1 = d3.scaleBand().domain(compressors).range([0, x0.bandwidth()]).padding(0.05);
        
        const minValue = d3.min(data, d => d.value);
        const y = d3.scaleLog()
          .domain([minValue > 0 ? minValue * 0.9 : 1e-9, d3.max(data, d => d.value)])
          .nice()
          .range([chartHeight, 0]);

        // Add Y-axis gridlines
        svg.append("g")
          .attr("class", "grid")
          .call(d3.axisLeft(y).ticks(5, "~s").tickSize(-chartWidth).tickFormat(""))
          .selectAll("line")
          .attr("stroke", "#e9ecef");
        svg.select(".domain").remove();

        // Add X axis
        svg.append("g")
          .attr("transform", `translate(0, ${chartHeight})`)
          .call(d3.axisBottom(x0))
          .selectAll("text")
          .style("text-anchor", "end")
          .attr("dx", "-0.8em")
          .attr("dy", "0.15em")
          .attr("transform", "rotate(-45)")
          .style("font-size", "14px");

        // Add Y axis
        svg.append("g").call(d3.axisLeft(y).ticks(5, "~s")).style("font-size", "14px");

        // Draw bars with transitions
        svg.selectAll(".category")
          .data(metrics)
          .enter()
          .append("g")
          .attr("transform", (d) => `translate(${x0(d)}, 0)`)
          .selectAll("rect")
          .data((d) => compressors.map((c) => data.find((item) => item.metric === d && item.compressor === c) || { value: 0, compressor: c, metric: d }))
          .enter()
          .append("rect")
          .attr("rx", 3) // Rounded corners
          .attr("x", (d) => x1(d.compressor))
          .attr("y", chartHeight) // Start from bottom
          .attr("width", x1.bandwidth())
          .attr("height", 0) // Start with no height
          .attr("fill", (d) => colorScale(d.compressor))
          .transition() // Animate bars
          .duration(750)
          .attr("y", (d) => d.value > 0 ? y(d.value) : chartHeight)
          .attr("height", (d) => d.value > 0 ? Math.max(0, chartHeight - y(d.value)) : 0);

        // Re-select bars to attach mouse events after transition
        svg.selectAll("rect")
          .on("mouseover", function (event, d) {
            if (!d || d.value === 0) return;
            tooltip.style("opacity", 1)
              .html(`
                <div style="font-weight: bold; margin-bottom: 5px;">${d.compressor}</div>
                <strong>Metric:</strong> ${d.metric}<br>
                <strong>Value:</strong> ${d.value.toExponential(4)}<br>
                <hr style="margin: 4px 0;">
                <div style="font-size: 11px; max-height: 100px; overflow-y: auto;">
                  ${that.formatConfig(d.compressor_config)}
                </div>
              `);
            d3.select(this).attr("stroke", "black").attr("stroke-width", 1.5);
          })
          .on("mousemove", function (event) {
            tooltip.style("left", `${event.pageX + 15}px`).style("top", `${event.pageY - 28}px`);
          })
          .on("mouseout", function () {
            tooltip.style("opacity", 0);
            d3.select(this).attr("stroke", "none");
          });

        // Figure title
        svg.append("text")
          .attr("x", chartWidth / 2)
          .attr("y", -50) // Adjusted y for legend
          .attr("text-anchor", "middle")
          .style("font-size", "18px")
          .style("font-weight", "600")
          .style("fill", "#343a40")
          .text(category);

        // Add scrollable legend
        const legend = svg.append("foreignObject")
          .attr("x", 0)
          .attr("y", -45) // Position legend below title
          .attr("width", Math.max(0, chartWidth))
          .attr("height", 45);

        const legendDiv = legend.append("xhtml:div")
          .style("width", "100%")
          .style("height", "100%")
          .style("overflow-x", "auto")
          .style("overflow-y", "hidden")
          .style("display", "flex")
          .style("align-items", "center")
          .style("white-space", "nowrap");

        compressors.forEach((comp) => {
          const item = legendDiv.append("xhtml:div")
            .style("display", "inline-flex")
            .style("align-items", "center")
            .style("margin-right", "15px")
            .style("font-size", "12px");

          item.append("xhtml:span")
            .style("width", "12px")
            .style("height", "12px")
            .style("border-radius", "3px")
            .style("background-color", colorScale(comp))
            .style("margin-right", "5px");

          item.append("xhtml:span")
            .text(comp);
        });
      });
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
      <div v-if="!comparisonData" class="alert alert-warning">
        <i class="bi bi-exclamation-triangle me-2"></i>No compression metrics available. Run a compressor to see comparison data.
      </div>
      <div v-else>
        <button
          class="btn btn-outline-primary d-flex align-items-center mb-2"
          type="button"
          @click="drawBarCharts">
          <span class="me-2">Refresh View</span>
          <i class="bi bi-arrow-clockwise"></i>
        </button>
        <!-- Charts -->
        <div id="stat" class="container"></div>
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
            :disabled="Object.keys(activeMetrics).length === 0"
          >
            <i class="bi bi-trash me-1"></i>Clear All
          </button>
        </div>

        <!-- Metrics Palette -->
        <div class="card mb-3">
          <div class="card-header bg-light py-2">
            <h6 class="mb-0 small">Available Metrics</h6>
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
        <div v-if="Object.keys(activeMetrics).length === 0" class="text-center text-muted py-5">
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
                    <label class="form-label small mb-1">{{ param.label }}</label>
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
              <div v-if="metric.result" class="metric-result">
                <h6 class="small text-muted mb-2">Results</h6>
                
                <!-- Scalar Result -->
                <div v-if="metric.result.type === 'scalar'" class="result-scalar">
                  <div class="alert alert-info mb-0 py-2">
                    <strong>{{ metric.result.label }}:</strong> {{ metric.result.value }}
                  </div>
                </div>

                <!-- Table Result -->
                <div v-else-if="metric.result.type === 'table'" class="result-table">
                  <table class="table table-sm table-bordered mb-0">
                    <thead>
                      <tr>
                        <th v-for="header in metric.result.headers" :key="header">{{ header }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(row, idx) in metric.result.rows" :key="idx">
                        <td v-for="(cell, cidx) in row" :key="cidx">{{ cell }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <!-- Image Result -->
                <div v-else-if="metric.result.type === 'image'" class="result-image">
                  <img :src="metric.result.src" class="img-fluid" :alt="metric.name" />
                </div>

                <!-- Text Result -->
                <div v-else-if="metric.result.type === 'text'" class="result-text">
                  <pre class="bg-light p-2 rounded small mb-0">{{ metric.result.content }}</pre>
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
</style>
