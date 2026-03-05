<script>
import * as d3 from "d3";
import { mapState } from 'vuex';
import { requestWithFallback } from '@/utils/datasetUtils';

export default {
  name: "MetricVis",

  data() {
    return {
      tooltip: null,
      activeSubTab: 'analysis', // 'compression' or 'analysis'
      // Analysis-related data
      selectedSources: ['original'], // Default to original
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
        {
          id: 'critical_points',
          name: 'Critical Points',
          icon: 'bi bi-grid text-warning',
          description: 'Compute critical points (minima, maxima, and saddles)',
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
    availableSources() {
      const sources = [{ id: 'original', name: 'Original Data' }];
      if (this.comparisonData) {
        Object.keys(this.comparisonData).forEach(key => {
          sources.push({ id: key, name: key });
        });
      }
      return sources;
    }
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
    // Sync selectedSources when availableSources change (e.g. node removed)
    availableSources: {
      handler(newSources) {
        const availableIds = newSources.map(s => s.id);
        // Remove sources that are no longer available
        this.selectedSources = this.selectedSources.filter(id => availableIds.includes(id));
        
        // Also remove results from active metrics for these sources
        Object.values(this.activeMetrics).forEach(metric => {
          if (metric.results) {
            Object.keys(metric.results).forEach(sourceId => {
              if (sourceId !== 'original' && !availableIds.includes(sourceId)) {
                delete metric.results[sourceId];
              }
            });
          }
        });
      },
      deep: true
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
          results: {}, // Map of sourceId -> result
        };
        this.activeMetrics[metricTemplate.id] = metric;
      }
    },

    toggleSource(sourceId) {
      if (sourceId === 'original') return; // Original is always selected

      const idx = this.selectedSources.indexOf(sourceId);
      if (idx > -1) {
        this.selectedSources.splice(idx, 1);
      } else {
        this.selectedSources.push(sourceId);
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

        let originalDataKey = this.dataset.data_key;

        // Create a copy and sort to ensure 'original' is first
        const sortedSources = [...this.selectedSources].sort((a, b) => {
          if (a === 'original') return -1;
          if (b === 'original') return 1;
          return 0;
        });

        // Loop through selected sources
        for (const sourceId of sortedSources) {
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
              console.log(`[MetricVis] Result stored for ${sourceId}:`, metric.results[sourceId]);
            }
          }
        }

        this.$store.commit('setStatus', { 
          type: 'success', 
          message: `${metric.name} computed for selected sources` 
        });
        
        // Redraw charts for visualizations
        this.$nextTick(() => {
          Object.keys(this.activeMetrics).forEach(id => {
            if (id === 'histogram') this.drawHistogram(this.activeMetrics[id]);
            else if (id === 'power_spectrum') this.drawPowerSpectrum(this.activeMetrics[id]);
            else if (id === 'correlation') this.drawCorrelation(this.activeMetrics[id]);
          });
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

    drawHistogram(metric) {
      const containerId = `histogram-chart-${metric.id}`;
      const container = d3.select(`#${containerId}`);
      if (!container.node()) return;
      container.selectAll("*").remove();

      const results = metric.results;
      const sources = Object.entries(results).filter(([, res]) => res && res.type === 'histogram');
      if (sources.length === 0) return;

      const margin = { top: 30, right: 30, bottom: 40, left: 60 };
      const width = container.node().clientWidth - margin.left - margin.right;
      const height = 300 - margin.top - margin.bottom;

      const svg = container.append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)
        .append("g")
        .attr("transform", `translate(${margin.left},${margin.top})`);

      // Combine all bin data to find domains
      const allBins = [];
      sources.forEach(([, res]) => {
        res.bins.forEach(b => allBins.push(b));
      });

      // Calculate typical bin width for domain padding and bar width
      let maxBinDist = 0;
      sources.forEach(([, res]) => {
        if (res.bins.length > 1) {
          maxBinDist = Math.max(maxBinDist, res.bins[1].x - res.bins[0].x);
        }
      });
      
      const xExtent = d3.extent(allBins, b => b.x);
      // Pad domain if we have a bin width estimate
      if (maxBinDist > 0) {
        xExtent[0] -= maxBinDist / 2;
        xExtent[1] += maxBinDist / 2;
      }

      const x = d3.scaleLinear()
        .domain(xExtent)
        .range([0, width]);

      const y = d3.scaleLinear()
        .domain([0, d3.max(allBins, b => b.count)])
        .nice()
        .range([height, 0]);

      svg.append("g")
        .attr("transform", `translate(0,${height})`)
        .call(d3.axisBottom(x).ticks(10));

      svg.append("g")
        .call(d3.axisLeft(y).ticks(5, "~s"));
      
      // X axis label
      svg.append("text")
        .attr("text-anchor", "middle")
        .attr("x", width / 2)
        .attr("y", height + 35)
        .text("Value")
        .style("font-size", "12px");

      const color = d3.scaleOrdinal(d3.schemeTableau10).domain(sources.map(s => s[0]));

      // Calculate total width available for each bin
      let totalBinWidth = 5;
      if (sources[0][1].bins.length > 1) {
        totalBinWidth = Math.abs(x(sources[0][1].bins[1].x) - x(sources[0][1].bins[0].x));
      } else {
        totalBinWidth = width / (metric.parameters.find(p => p.name === 'bins')?.value || 50);
      }

      // Create a sub-scale for sources within each bin
      const x1 = d3.scaleBand()
        .domain(sources.map(s => s[0]))
        .range([0, totalBinWidth])
        .padding(0.05);

      sources.forEach(([id, res]) => {
        svg.append("g")
          .attr("class", `bars-${id}`)
          .selectAll("rect")
          .data(res.bins)
          .enter()
          .append("rect")
          .attr("x", d => x(d.x) - totalBinWidth / 2 + x1(id))
          .attr("y", d => y(d.count))
          .attr("width", x1.bandwidth())
          .attr("height", d => height - y(d.count))
          .attr("fill", color(id))
          .attr("stroke", color(id))
          .attr("stroke-width", 0.5)
          .on("mouseover", function() {
            d3.select(this).attr("stroke-width", 1.5).attr("fill", d3.rgb(color(id)).brighter(0.5));
          })
          .on("mouseout", function() {
            d3.select(this).attr("stroke-width", 0.5).attr("fill", color(id));
          });
      });

      // Add legend
      const legend = svg.append("g").attr("transform", `translate(${width - 120}, 0)`);
      sources.forEach(([id], i) => {
        const lg = legend.append("g").attr("transform", `translate(0, ${i * 20})`);
        lg.append("rect").attr("width", 12).attr("height", 12).attr("fill", color(id));
        lg.append("text").attr("x", 16).attr("y", 10).text(id).style("font-size", "11px").attr("alignment-baseline", "middle");
      });
    },

    drawPowerSpectrum(metric) {
      const containerId = `ps-chart-${metric.id}`;
      const container = d3.select(`#${containerId}`);
      if (!container.node()) return;
      container.selectAll("*").remove();

      const results = metric.results;
      const sources = Object.entries(results).filter(([, res]) => res && res.type === 'power_spectrum');
      if (sources.length === 0) return;

      const margin = { top: 30, right: 30, bottom: 40, left: 60 };
      const width = container.node().clientWidth - margin.left - margin.right;
      const height = 300 - margin.top - margin.bottom;

      const svg = container.append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)
        .append("g")
        .attr("transform", `translate(${margin.left},${margin.top})`);

      const allData = [];
      sources.forEach(([, res]) => {
        res.data.forEach(d => allData.push(d));
      });

      const x = d3.scaleLog()
        .domain(d3.extent(allData, d => d.k))
        .range([0, width]);

      const y = d3.scaleLog()
        .domain(d3.extent(allData, d => d.p))
        .range([height, 0]);

      svg.append("g")
        .attr("transform", `translate(0,${height})`)
        .call(d3.axisBottom(x).ticks(5, "~s"));

      svg.append("g")
        .call(d3.axisLeft(y).ticks(5, "~s"));
      
      // Labels
      svg.append("text").attr("text-anchor", "middle").attr("x", width/2).attr("y", height + 35).text("Wavenumber (k)").style("font-size", "12px");
      svg.append("text").attr("text-anchor", "middle").attr("transform", "rotate(-90)").attr("y", -45).attr("x", -height/2).text("Power P(k)").style("font-size", "12px");

      const color = d3.scaleOrdinal(d3.schemeTableau10).domain(sources.map(s => s[0]));

      sources.forEach(([id, res]) => {
        const line = d3.line()
          .x(d => x(d.k))
          .y(d => y(d.p));

        svg.append("path")
          .datum(res.data)
          .attr("fill", "none")
          .attr("stroke", color(id))
          .attr("stroke-width", 2)
          .attr("d", line);
      });

      const legend = svg.append("g").attr("transform", `translate(${width - 120}, 0)`);
      sources.forEach(([id], i) => {
        const lg = legend.append("g").attr("transform", `translate(0, ${i * 20})`);
        lg.append("rect").attr("width", 12).attr("height", 12).attr("fill", color(id));
        lg.append("text").attr("x", 16).attr("y", 10).text(id).style("font-size", "11px").attr("alignment-baseline", "middle");
      });
    },

    drawCorrelation(metric) {
      const containerId = `corr-chart-${metric.id}`;
      const container = d3.select(`#${containerId}`);
      if (!container.node()) return;
      container.selectAll("*").remove();

      const results = metric.results;
      const sources = Object.entries(results).filter(([, res]) => res && res.type === 'correlation');
      if (sources.length === 0) return;

      const margin = { top: 30, right: 30, bottom: 40, left: 60 };
      const width = container.node().clientWidth - margin.left - margin.right;
      const height = 300 - margin.top - margin.bottom;

      const svg = container.append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)
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

      svg.append("g")
        .attr("transform", `translate(0,${height})`)
        .call(d3.axisBottom(x).ticks(10));

      svg.append("g")
        .call(d3.axisLeft(y).ticks(5));
      
      // Zero line
      svg.append("line")
        .attr("x1", 0).attr("y1", y(0))
        .attr("x2", width).attr("y2", y(0))
        .attr("stroke", "#eee")
        .attr("stroke-dasharray", "4");

      svg.append("text").attr("text-anchor", "middle").attr("x", width/2).attr("y", height + 35).text("Lag").style("font-size", "12px");
      svg.append("text").attr("text-anchor", "middle").attr("transform", "rotate(-90)").attr("y", -45).attr("x", -height/2).text("Autocorrelation").style("font-size", "12px");

      const color = d3.scaleOrdinal(d3.schemeTableau10).domain(sources.map(s => s[0]));

      sources.forEach(([id, res]) => {
        const line = d3.line()
          .x(d => x(d.lag))
          .y(d => y(d.value));

        svg.append("path")
          .datum(res.data)
          .attr("fill", "none")
          .attr("stroke", color(id))
          .attr("stroke-width", 2)
          .attr("d", line);
        
        svg.selectAll(`.dot-${id}`)
          .data(res.data)
          .enter().append("circle")
          .attr("cx", d => x(d.lag))
          .attr("cy", d => y(d.value))
          .attr("r", 3)
          .attr("fill", color(id));
      });

      const legend = svg.append("g").attr("transform", `translate(${width - 120}, 0)`);
      sources.forEach(([id], i) => {
        const lg = legend.append("g").attr("transform", `translate(0, ${i * 20})`);
        lg.append("rect").attr("width", 12).attr("height", 12).attr("fill", color(id));
        lg.append("text").attr("x", 16).attr("y", 10).text(id).style("font-size", "11px").attr("alignment-baseline", "middle");
      });
    },


    visualizeCriticalPoints(criticalPointsData, sourceId = 'original') {
      // Store critical points data in Vuex so HelloVtk can access it
      this.$store.commit('setCriticalPoints', { 
        source: sourceId, 
        data: criticalPointsData 
      });
      
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
          console.log(`[MetricVis] Visualizing CPs for ${sourceId}:`, data);
          this.$store.commit('setCriticalPoints', { 
            source: sourceId, 
            data: data 
          });
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

        <!-- Sources Selection -->
        <div class="card mb-3">
          <div class="card-header bg-light py-2 d-flex justify-content-between align-items-center">
            <h6 class="mb-0 small">Data Sources to Analyze</h6>
            <span class="badge bg-secondary">{{ selectedSources.length }} selected</span>
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
              <div v-if="Object.keys(metric.results).length > 0" class="metric-result">
                <h6 class="small text-muted mb-3">Comparison Results</h6>
                
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
                  <div :id="`ps-chart-${metric.id}`" class="w-100" style="height: 300px;"></div>
                </div>

                <!-- Correlation Comparison Chart -->
                <div v-else-if="metric.id === 'correlation'" class="result-chart">
                  <div :id="`corr-chart-${metric.id}`" class="w-100" style="height: 300px;"></div>
                </div>

                <!-- Histogram Comparison Chart -->
                <div v-else-if="metric.id === 'histogram'" class="result-chart">
                  <div :id="`histogram-chart-${metric.id}`" class="w-100" style="height: 300px;"></div>
                </div>

                <!-- Default Multi-Source Display for other types -->
                <div v-else class="sources-results">
                  <div v-for="sourceId in selectedSources" :key="sourceId" class="mb-3 p-2 border rounded">
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
</style>
