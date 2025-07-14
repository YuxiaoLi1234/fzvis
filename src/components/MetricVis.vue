<template>
  <div class="container py-3">
    <div v-if="!comparisonData" class="alert alert-danger">
      No metrics data available to visualize.
    </div>
    <button v-else
      class="btn btn-outline-primary d-flex align-items-center mb-2"
      type="button"
      @click="drawBarCharts">
      <span class="me-2">Refresh View</span>
      <i class="bi bi-arrow-clockwise"></i>
    </button>
    <!-- Charts -->
    <div id="stat" class="container"></div>
  </div>
</template>

<script>

import * as d3 from "d3";

export default {
  name: "MetricVis",

  data() {
    return {
      tooltip:null,
    };
  },
  
  computed: {
    comparisonData() {
      return this.$store.state.comparisonData;
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

  methods: {
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
        const width = containerWidth * 0.96;
        const height = 350;
        const margin = { top: 80, right: 20, bottom: 30, left: 50 }; // Increased top margin for legend

        const svg = statDiv
          .append("svg")
          .attr("width", width)
          .attr("height", height + margin.top + margin.bottom)
          .append("g")
          .attr("transform", `translate(${margin.left}, ${margin.top})`);

        const metrics = [...new Set(data.map((d) => d.metric))];
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
          .attr("width", chartWidth)
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
