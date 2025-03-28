<template>
    <div>
        <!-- 控件区 -->
        <div id="radar-controls">
            <button 
                id="radar-control-button" 
                :disabled="!dataReceived" 
                @click="drawBarCharts">
                Generate Metrics Comparison
            </button>
        </div>

        <!-- 图表区 -->
        <div id="stat"></div>
    </div>
</template>
<style scoped>
    @import "@/assets/StatA.css";
</style>
<script>

import * as d3 from "d3";
import emitter from './eventBus';

export default {
    data() {
        return {
            tooltip:null,
            dataReceived: false,
            rawData: null, // 用于存储接收到的原始数据
        };
    },
    mounted() {
        // 监听事件
        emitter.on("myEvent", (data) => {
                console.log("Received data:", data);
                this.rawData = data;
                this.dataReceived = true;
            });
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

        return Object.entries(config)
            .map(([key, value]) => {
                let formattedKey = key.replace(/^.*?:/, "") // 去掉 `sz3:` 这种前缀
                                    .replace("_str", "") // 移除 `_str`
                                    .replace("_mode", "") // 移除 `_mode`
                                    .replace("_algo", "") // 移除 `_algo`
                                    .replace("_", " ") // 替换 `_` 为 ` `
                                    .replace(/\b\w/g, c => c.toUpperCase()); // 首字母大写

                return `<strong>${formattedKey}:</strong> ${value}`;
            })
            .join("<br>"); // 用 `<br>` 让不同配置换行
        },

        drawBarCharts() {
            const that = this;
            if (!this.rawData || !this.rawData.metrics) {
                alert("No data available to visualize.");
                return;
            }
            console.log(this.rawData)
            const { compressor_config, compressor_id, metrics, compressor_name} = this.rawData;
            
            // 按分类整理数据
            if(compressor_name[0] == "Original Data") compressor_name.shift()
            const categories = {};
            metrics.forEach((metric, idx) => {
                console.log(idx)
                for (const [key, value] of Object.entries(metric)) {
                        const [category, subMetric] = key.split(":");
                        if (!categories[category]) categories[category] = [];
                            categories[category].push({
                                compressor: compressor_name[idx],
                                compressor_id: compressor_id[idx],
                                metric: subMetric,
                                value: isNaN(value) || value === "Infinity" || value === "null" ? 0 : parseFloat(value),
                                compressor_config: compressor_config[idx]
                            });
                        }
            });

            // 清空画布
            const statDiv = d3.select("#stat");
            statDiv.selectAll("*").remove();

            const containerWidth = document.getElementById("stat").clientWidth;

            // 获取所有压缩器并去重
            const compressors = [...new Set(compressor_name)];

            // 颜色比例尺
            const colorScale = d3.scaleOrdinal().domain(compressors).range(d3.schemeCategory10);

            // 每个分类一个面板
            if (this.tooltip == null) {
                this.tooltip = d3
                .select("body")
                .append("div")
                .attr("class", "tooltip")
                .style("position", "absolute")
                .style("background", "rgba(0, 0, 0, 0.8)")
                .style("color", "white")
                .style("padding", "5px 10px")
                .style("border-radius", "5px")
                .style("font-size", "12px")
                .style("pointer-events", "none")
                .style("opacity", 0);
            }

            const tooltip = this.tooltip;
            Object.entries(categories).forEach(([category, data]) => {
                const width = containerWidth * 0.95; // 根据父容器调整宽度
                const height = 400;
                const margin = { top: 50, right: 20, bottom: 80, left: 100 };

                const svg = statDiv
                .append("svg")
                .attr("width", width)
                .attr("height", height + 50) // 给图例留出空间
                .append("g")
                .attr("transform", `translate(${margin.left}, ${margin.top})`);

                const metrics = [...new Set(data.map((d) => d.metric))];

                // 横轴和纵轴比例尺
                const x0 = d3.scaleBand().domain(metrics).range([0, width - margin.left - margin.right]).padding(0.2);
                const x1 = d3.scaleBand().domain(compressors).range([0, x0.bandwidth()]).padding(0.1);
                // const y = d3.scaleLinear().domain([0, d3.max(data, (d) => d.value)]).nice().range([height - margin.top - margin.bottom, 0]);
                const y = d3.scaleLog()
                            .domain([Math.max(1, d3.min(data, d => d.value)), d3.max(data, d => d.value)]) // 避免 log(0)
                            .nice()
                            .range([height - margin.top - margin.bottom, 0]);
                
                // 添加横轴
                svg
                .append("g")
                .attr("transform", `translate(0, ${height - margin.top - margin.bottom})`)
                .call(d3.axisBottom(x0))
                .selectAll("text")
                .style("text-anchor", "end")
                .attr("dx", "-0.8em")
                .attr("dy", "0.15em")
                .attr("transform", "rotate(-45)")
                .style("font-size", "14px")

                // 添加纵轴
                // svg.append("g").call(d3.axisLeft(y));

                svg.append("g")
                    .call(d3.axisLeft(y).ticks(5, "~s"))
                    .style("font-size", "14px")
            
                
            
                svg
                .selectAll(".category")
                .data(metrics)
                .enter()
                .append("g")
                .attr("transform", (d) => `translate(${x0(d)}, 0)`)
                .selectAll("rect")
                .data((d) => compressors.map((c) => data.find((item) => item.metric === d && item.compressor === c)))
                .enter()
                .append("rect")
                .attr("x", (d) => x1(d.compressor))
                .attr("y", (d) => y(d.value))
                .attr("width", x1.bandwidth())
                .attr("height", (d) => Math.max(0, height - margin.top - margin.bottom - y(d.value)))
                .attr("fill", (d) => colorScale(d.compressor))
                .on("mouseover", function (event, d) {
                    console.log(d.compressor)
                    tooltip.style("opacity", 1)
                        .html(`
                            <strong>Compressor Name:</strong> ${d.compressor}<br>
                            <strong>Compressor Type:</strong> ${d.compressor_id}<br>
                            <strong>Metric:</strong> ${d.metric}<br>
                            <strong>Value:</strong> ${d.value.toFixed(4)}<br>
                            
                            <strong>Configuration:</strong> <br>
                            ${that.formatConfig(d.compressor_config)}
                        `)
                    d3.select(this).attr("opacity", 0.7); // 变暗高亮
                })
                .on("mousemove", function (event) {
                    tooltip.style("left", `${event.pageX + 15}px`) .style("top", `${event.pageY + 15}px`);
                })
                .on("mouseout", function () {
                    tooltip.style("opacity", 0);
                    d3.select(this).attr("opacity", 1); // 还原颜色
                });

                // 添加分类标题
                svg
                .append("text")
                .attr("x", (width - margin.left - margin.right) / 2)
                .attr("y", -10)
                .attr("text-anchor", "middle")
                .style("font-size", "16px")
                .style("font-weight", "bold")
                .text(category);

                // 添加图例
                const legend = svg
                .append("g")
                .attr("transform", `translate(0, ${height - margin.top + 20})`);

                compressors.forEach((comp, idx) => {
                    const legendItem = legend
                        .append("g")
                        .attr("transform", `translate(${idx * 150}, 0)`); // 图例项间距

                    legendItem
                        .append("rect")
                        .attr("width", 15)
                        .attr("height", 15)
                        .attr("fill", colorScale(comp));

                    legendItem
                        .append("text")
                        .attr("x", 20)
                        .attr("y", 12)
                        .text(comp)
                        .style("font-size", "16px")
                        .style("text-anchor", "start");
                    });
                });
        },
    },
};
</script>


