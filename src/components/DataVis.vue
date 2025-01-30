<template>
  <div id="data_vis">
    <div id="zoomWarning" style="display: none; color: red; font-size: 14px; position: absolute; top: 10px; right: 10px; z-index: 1000;">
        Cannot zoom in further. Minimum zoom size reached!
    </div>
      <div id="controls">
        <select id="colormapSelect" class="control-select">
          <option value="Rainbow">Rainbow</option>
          <option value="Viridis">Viridis</option>
          <option value="Plasma">Plasma</option>
          <option value="Inferno">Inferno</option>
        </select>
        <input type="number" id="slice_id" class="control-input" placeholder="Slice ID" v-model="slice_id"/>
        <button id="input-button" class="control-button" @click="vis_input">Input Mode</button>
        <button id="output-button" class="control-button" @click="vis_output">Output Mode</button>
        <button id="reset-button" class="control-button" @click="resetView">Reset</button>
        
      </div>
      
      

      <div class="visualization-area">
        <div id="svgCanvasContainer">
          <svg id="svgCanvas"></svg>
        </div>
        <svg id="colorbarCanvas"></svg>
      </div>


  </div>
  
  

</template>
<style scoped>
@import "@/assets/DataVis.css";
</style>
<script>
import * as d3 from 'd3'
import emitter from './eventBus.js';

export default {
name:'DataVis',
data(){
    return{
      tooltip:null,
      colormap:'',
      slice_id:null,
      mode:"input",
      width:null,
      height:null,
      depth:null,
      controlPoints: [], 
      globalMin: null, 
      globalMax: null, 
      normalize: true,
      original_data: null,
      decp_data:[],
      zoomData:null,
      drawZoom:false,
      compressor_name:[]
    };
},
async mounted(){

  await emitter.on('inputdata', (data) => {
      this.width = data['width'];
      this.height = data['height'];
      this.depth = data['depth'];
      this.input_data = Object.values(data["input_data"]);  
      this.decp_data = data["decp_data"];  
      this.compressor_name = data["compressor_name"];  
      console.log(this.decp_data)
      
  })

},
computed: {
},
watch: {
},
methods:{
  vis_input: function () {
  
      this.mode = "input";
      this.drawZoom = false;
      this.draw_data = this.input_data
      this.data_vis(this.input_data);
      this.defaultcolormap();
      this.draw();
      
  },

  vis_output: function () {
    
    this.mode = "decp";
    this.drawZoom = false;
    this.draw_data = this.decp_data
    this.data_vis(this.decp_data); // 注意这里直接传递多个数据集
    this.defaultcolormap();
    this.draw();
    
  },

  data_vis: function () {
      let datasets = [];
      let globalMin = Infinity;
      let globalMax = -Infinity;

      if (this.mode === "input") {
        // 展平并提取当前切片
        const flatData = this.input_data.flat().flat();
        const slice = flatData.slice(
          this.slice_id * this.width * this.height,
          (this.slice_id + 1) * this.width * this.height
        );

        // 转换为二维数组
        const reshapedSlice = [];
        for (let i = 0; i < this.height; i++) {
          reshapedSlice.push(slice.slice(i * this.width, (i + 1) * this.width));
        }
        datasets = [reshapedSlice];
      } else {
        for (let i = 0; i < this.decp_data.length; i++) {
          // 展平并提取当前切片
          const flatData = this.decp_data[i].flat().flat();
          const slice = flatData.slice(
            this.slice_id * this.width * this.height,
            (this.slice_id + 1) * this.width * this.height
          );

          // 转换为二维数组
          const reshapedSlice = [];
          for (let j = 0; j < this.height; j++) {
            reshapedSlice.push(slice.slice(j * this.width, (j + 1) * this.width));
          }
          datasets.push(reshapedSlice);
        }
      }

      // 计算全局最小值和最大值
      datasets.forEach((data) => {
        const min = d3.min(data.flat()); // 计算展平后的最小值
        const max = d3.max(data.flat()); // 计算展平后的最大值
        if (min < globalMin) globalMin = min;
        if (max > globalMax) globalMax = max;
      });
      
      // 如果需要归一化
      if (this.normalize) {
        datasets = datasets.map((data) =>
          data.map((row) =>
            row.map((value) => (value - globalMin) / (globalMax - globalMin))
          )
        );
      }

      // 更新全局变量
      this.draw_data = datasets;
      
      this.original_data = JSON.parse(JSON.stringify(this.draw_data)); // 深拷贝原始数据
      this.globalMin = globalMin;
      this.globalMax = globalMax;
      
      // 初始化控制点（根据 colormap 计算初始值）
      const colormap = [
        { r: 0, g: 0, b: 255 },
        { r: 0, g: 255, b: 0 },
        { r: 255, g: 0, b: 0 },
      ]; // 示例颜色映射

      this.controlPoints = colormap.map((color, i) => ({
        offset: i / (colormap.length - 1), // 均匀分布
        value: globalMin + (i / (colormap.length - 1)) * (globalMax - globalMin),
        color,
      }));
      console.log("controlpoints:",this.controlPoints)
  },

  draw: function (dataToDraw = null) {
    // const svgDiv = d3.select("#svgCanvasContainer");
    const svgCanvas = d3.select("#svgCanvas");
    svgCanvas.selectAll("*").remove();

    const canvasWidth = document.getElementById("svgCanvasContainer").clientWidth; // 容器宽度
    const canvasHeight = document.getElementById("svgCanvasContainer").clientHeight; // 容器高度
    const margin = { top: 10, right: 0, bottom: 10, left: 0 };

    const datasets = dataToDraw || this.draw_data; // 数据集
    const numDatasets = datasets.length;

    const dataWidth = datasets[0][0].length; // 数据的宽度
    const dataHeight = datasets[0].length; // 数据的高度

    const gap = 20; // 数据集间隙
    const textPadding = 30; // 文本编号区域的高度
    const maxColumns = 5; // 每行最多显示三个数据集
    const columns = Math.min(maxColumns, numDatasets); // 实际列数
    const rows = Math.ceil(numDatasets / columns); // 根据数据集数量计算行数

    const maxDatasetWidth = (canvasWidth - (columns - 1) * gap) / columns; // 单个数据集最大宽度
    const maxDatasetHeight = (canvasHeight - (rows - 1) * gap) / rows; // 单个数据集最大宽度
    const cellSize = Math.min(maxDatasetWidth / dataWidth, maxDatasetHeight / dataHeight); // 单元格大小
    const rowHeight = dataHeight * cellSize + textPadding; // 每一行的高度
    const totalHeight = rows * rowHeight + (rows - 1) * gap; // 总高度

    
    svgCanvas.attr("width", canvasWidth)
              .attr("height", Math.max(totalHeight, canvasHeight))  // 给图例留出空间
              .append("g")
              .style("overflow", "visible")
              .attr("transform", `translate(${margin.left}, ${margin.top})`);

    
    datasets.forEach((data, datasetIndex) => {
        const col = datasetIndex % maxColumns; // 当前列
        const row = Math.floor(datasetIndex / maxColumns); // 当前行

        // 计算水平偏移量，使每行居中
        const totalRowWidth = columns * (dataWidth * cellSize) + (columns - 1) * gap; // 当前行总宽度
        const rowStartX = (canvasWidth - totalRowWidth) / 2; // 居中的起始位置

        const startX = rowStartX + col * (dataWidth * cellSize + gap); // 当前矩阵的横向偏移
        const startY = row * (rowHeight + gap); // 当前矩阵的纵向偏移

        // 绘制矩阵
        for (let i = 0; i < data.length; i++) {
            for (let j = 0; j < data[i].length; j++) {
                const value = data[i][j];
                svgCanvas
                    .append("rect")
                    .attr("x", startX + j * cellSize)
                    .attr("y", startY + i * cellSize)
                    .attr("width", cellSize)
                    .attr("height", cellSize)
                    .attr("fill", this.colorScale(value));
            }
        }

        
        svgCanvas
            .append("text")
            .attr("x", startX + (dataWidth * cellSize) / 2) 
            .attr("y", startY + dataHeight * cellSize + textPadding / 2) 
            .attr("text-anchor", "middle")
            .attr("font-size", "12px")
            .attr("fill", "black")
            .text(this.compressor_name[datasetIndex]);
    });

    this.addZoomInteraction(); // 添加缩放交互
},

  resetView: function () {
    this.draw_data = this.original_data; // 恢复初始数据
    this.drawZoom = false;
    this.draw(); // 绘制全局视图
    this.addZoomInteraction();
  },

  addZoomInteraction: function () {
    const svgCanvas = d3.select("#svgCanvas");
    const canvasWidth = parseFloat(svgCanvas.attr("width"));
    const canvasHeight = parseFloat(svgCanvas.attr("height"));

    let isDragging = false;
    let startX, startY; // 框选起点
    const selection = svgCanvas
      .append("rect")
      .attr("class", "selection")
      .style("stroke", "blue")
      .style("stroke-width", 2)
      .style("fill", "rgba(0, 0, 255, 0.1)")
      .style("display", "none");

    
    

    svgCanvas
      .on("mousedown", (event) => {
        const [x, y] = d3.pointer(event);
        isDragging = true;
        startX = x;
        startY = y;

        selection
          .style("display", "block")
          .attr("x", x)
          .attr("y", y)
          .attr("width", 0)
          .attr("height", 0);
      })
      .on("mousemove", (event) => {
        if (isDragging) {
          const [x, y] = d3.pointer(event);
          selection
            .attr("x", Math.min(x, startX))
            .attr("y", Math.min(y, startY))
            .attr("width", Math.abs(x - startX))
            .attr("height", Math.abs(y - startY));
        }
      })
      .on("mouseup", (event) => {
        if (isDragging) {
          const [endX, endY] = d3.pointer(event);
          isDragging = false;

          selection.style("display", "none");

          
          const dataWidth = this.width;
          const dataHeight = this.height;
          const gap = 10; // 数据集间隙
          const numDatasets = this.draw_data.length;
          const maxColumns = 5; // 每行最多显示三个数据集
          const columns = Math.min(maxColumns, numDatasets); // 实际列数
          const rows = Math.ceil(numDatasets / columns); // 根据数据集数量计算行数

          const maxDatasetWidth = (canvasWidth - (columns - 1) * gap) / columns; // 单个数据集最大宽度
          const maxDatasetHeight = (canvasHeight - (rows - 1) * gap) / rows; // 单个数据集最大宽度
          const cellSize = Math.min(maxDatasetWidth / dataWidth, maxDatasetHeight / dataHeight); // 单元格大小
        
          const firstRectX = d3.select("#svgCanvas rect").attr("x");
          const firstRectY = d3.select("#svgCanvas rect").attr("y");
          console.log(firstRectX)
          const selectedDatasetIndex =
            Math.floor(startY / (maxDatasetHeight + gap)) * maxColumns +
            Math.floor(startX / (maxDatasetWidth + gap));
          console.log(selectedDatasetIndex)
          if (selectedDatasetIndex >= this.draw_data.length) return;

          // const datasetStartX = (col * (dataWidth * cellSize + gap)) + (canvasWidth - totalRowWidth) / 2; // 水平偏移量
          // const datasetStartY = row * (rowHeight + gap); // 垂直偏移量
          
          const datasetStartX = (selectedDatasetIndex % maxColumns) * (maxDatasetWidth + gap) + firstRectX;
          const datasetStartY = Math.floor(selectedDatasetIndex / maxColumns) * (maxDatasetHeight + gap) + firstRectY;

          const relativeXStart = Math.max(0, Math.floor((Math.min(startX, endX) - datasetStartX) / cellSize));
          const relativeXEnd = Math.min(
            this.width,
            Math.ceil((Math.max(startX, endX) - datasetStartX) / cellSize)
          );
          const relativeYStart = Math.max(0, Math.floor((Math.min(startY, endY) - datasetStartY) / cellSize));
          const relativeYEnd = Math.min(
            this.height,
            Math.ceil((Math.max(startY, endY) - datasetStartY) / cellSize)
          );
          console.log("startX:", startX, "endX:", endX, "datasetStartX:", datasetStartX, "cellSize:", cellSize);

          console.log(relativeXEnd, relativeXStart, relativeYEnd, relativeYStart)
          if (relativeXEnd - relativeXStart <= 0 || relativeYEnd - relativeYStart <= 0) {
            alert("Zoomed area is too small! Please select a larger area.");
            return;
          }

          const zoomedData = this.draw_data.map((data) =>
            data.slice(relativeYStart, relativeYEnd).map((row) =>
              row.slice(relativeXStart, relativeXEnd)
            )
          );
          this.zoomedData = zoomedData
          this.draw_data = zoomedData;
          this.draw(zoomedData);
        }
      });
  },




  drawColorbar: function () {
    const gradientId = "colorGradient";
    const colorbarCanvas = d3.select("#colorbarCanvas");
    colorbarCanvas.selectAll("*").remove();

    const canvasWidth = parseFloat(colorbarCanvas.style("width"));
    const canvasHeight = parseFloat(colorbarCanvas.style("height"));

    const defs = colorbarCanvas.append("defs");
    const gradient = defs
      .append("linearGradient")
      .attr("id", gradientId)
      .attr("x1", "0%")
      .attr("y1", "0%")
      .attr("x2", "100%")
      .attr("y2", "0%");

    this.controlPoints.forEach((point) => {
      gradient
        .append("stop")
        .attr("offset", `${point.offset * 100}%`)
        .attr("stop-color", `rgb(${point.color.r}, ${point.color.g}, ${point.color.b})`);
    });

    colorbarCanvas
      .append("rect")
      .attr("x", 0)
      .attr("y", 0)
      .attr("width", canvasWidth)
      .attr("height", canvasHeight)
      .attr("fill", `url(#${gradientId})`);

    this.addColorbarInteractions(colorbarCanvas);
  },
  updateColorScale: function () {
    this.colorScale = d3
      .scaleLinear()
      .domain(this.controlPoints.map((d) => d.value))
      .range(this.controlPoints.map((d) => `rgb(${d.color.r}, ${d.color.g}, ${d.color.b})`));
  },

  addColorbarInteractions: function (colorbarCanvas) {
    
        const canvasWidth = parseFloat(colorbarCanvas.style("width"));
        const canvasHeight = parseFloat(colorbarCanvas.style("height"));
        if (!this.tooltip) {
            this.tooltip = d3
              .select("body")
              .append("div")
              .attr("class", "tooltip")
              .style("position", "absolute")
              .style("background", "rgba(0, 0, 0, 0.7)")
              .style("color", "white")
              .style("padding", "5px 10px")
              .style("border-radius", "5px")
              .style("font-size", "12px")
              .style("pointer-events", "none")
              .style("opacity", 0); // 初始隐藏
      }
      const tooltip = this.tooltip; // 全局唯一的 tooltip
        
      const drag = d3.drag()
                  .on("start", (event) => {
                    d3.select(event.sourceEvent.target).attr("r", 10); // 拖拽开始时放大控制点
                  })
                  .on("drag", (event, d) => {
                      const newOffset = Math.max(0, Math.min(1, event.x / canvasWidth));
                      d.offset = newOffset;
                      d.value = this.globalMin + newOffset * (this.globalMax - this.globalMin); // 更新值

                      this.updateColorScale(); // 更新比例尺
                      this.drawColorbar(); // 重绘颜色条
                      if(this.drawZoom) this.draw(this.zoomData);
                      else this.draw();
                      

                      // 同步更新 Tooltip 的位置和值
                      tooltip
                        .style("left", `${event.x + 15}px`)
                        .style("top", `${event.y + 15}px`)
                        .html(`Value: ${(parseFloat(d.offset.toFixed(4)) * 100).toFixed(2)}%`);
                  })
                  .on("end", (event) => {
                      d3.select(event.sourceEvent.target).attr("r", 5); // 拖拽结束后恢复大小
                  });

        const circles = colorbarCanvas
                        .selectAll("circle")
                        .data(this.controlPoints, (d) => d.offset);

        circles.enter()
                .append("circle")
                .attr("cx", (d) => d.offset * canvasWidth)
                .attr("cy", canvasHeight / 2)
                .attr("r", 5)
                .attr("fill", "white")
                .attr("stroke", "black")
                .on("mouseover", function (event, d) {
                  d3.select("#colorbarCanvas").style("z-index", 200);
                  d3.select(this).transition().duration(100).attr("r", 8); // 放大控制点

                  tooltip
                    .style("opacity", 1) // 显示 Tooltip
                    .style("left", `${event.pageX + 15}px`) // 初始位置
                    .style("top", `${event.pageY + 15}px`) // 初始位置
                    .html(`Value: ${(parseFloat(d.offset.toFixed(4)) * 100).toFixed(2)}%`);
                })
                .on("mousemove", function (event) {
                  tooltip
                    .style("left", `${event.pageX + 15}px`) // 跟随鼠标移动
                    .style("top", `${event.pageY + 15}px`);
                })
                .on("mouseout", function () {
                  d3.select("#colorbarCanvas").style("z-index", "101");
                  d3.select(this).transition().duration(100).attr("r", 5); // 恢复控制点大小
                  tooltip.style("opacity", 0); // 隐藏 Tooltip
                })
                .call(drag)
                .on("contextmenu", (event, d) => {
                  
                  event.preventDefault();
                  this.controlPoints = this.controlPoints.filter((point) => point !== d); // 删除控制点

                  this.updateColorScale(); // 更新比例尺
                  this.drawColorbar(); // 重绘颜色条
                  if(this.drawZoom) this.draw(this.zoomData);
                  else this.draw();
                  
                });

      colorbarCanvas.on("click", (event) => {
        const clickX = event.offsetX;
        const offset = clickX / parseFloat(colorbarCanvas.style("width")); 
        const value = this.globalMin + offset * (this.globalMax - this.globalMin); 

        console.log(clickX, parseFloat(colorbarCanvas.style("width")), offset, value)
        // 动态插值颜色
        const interpolatedColor = d3.color(this.colorScale(value));
        const newColor = {
          r: interpolatedColor.r,
          g: interpolatedColor.g,
          b: interpolatedColor.b,
        };

        // 新增控制点
        this.controlPoints.push({ offset, value, color: newColor });
        this.controlPoints.sort((a, b) => a.offset - b.offset); 

        this.updateColorScale(); 
        this.drawColorbar(); 
        if(this.drawZoom) this.draw(this.zoomData);
        else this.draw();
        
      });

      circles.exit().remove();
  },

  onChange: function () {
    const colormapSelect = document.getElementById("colormapSelect");
    const selectedColormap = colormapSelect.value || "Rainbow";

    if (this.defaultColormaps[selectedColormap]) {
      console.log(selectedColormap)
      this.colormap = this.parseLinearGradient(
        this.defaultColormaps[selectedColormap]
      );

      // 更新控制点
      this.updateControlPointsFromColormap();

      // 更新颜色条和数据可视化
      this.drawColorbar();
      if(this.drawZoom) this.draw(this.zoomData);
      else this.draw();
      
      
    }
  },
  defaultcolormap: function () {

    this.defaultColormaps = {
      Rainbow:
        "linear-gradient(to right, #8B00FF, #0000FF, #00FFFF, #008000, #FFFF00, #FF0000)",
      Viridis:
        "linear-gradient(to right, #440154, #48186a, #472d7b, #424086, #3b528b, #33638d, #2c728e, #26828e, #21918e, #1e9e8e, #28ae8e, #3bbc8e, #51cc8f, #69db8f, #80ea8f, #98f999)",
      Plasma:
        "linear-gradient(to right, #0d0887, #46039f, #7201a8, #9c179e, #bd3786, #d85763, #ed7953, #fca636, #f0f921)",
      Inferno:
        "linear-gradient(to right, #000004, #160b39, #420a68, #6a176e, #932667, #bb3654, #dd513a, #f3771d, #fdb724)",
    };

    const colormapSelect = document.getElementById("colormapSelect");
    Object.keys(this.defaultColormaps).forEach((colormapName) => {
      const option = document.createElement("option");
      option.value = colormapName;
      option.text = colormapName;
      colormapSelect.appendChild(option);
    });

    // 默认选择 Rainbow
    colormapSelect.value = "Rainbow";
    this.colormap = this.parseLinearGradient(this.defaultColormaps["Rainbow"]);

    // 初始化控制点
    this.updateControlPointsFromColormap();

    colormapSelect.addEventListener("change", this.onChange.bind(this));
  },
  parseLinearGradient: function (gradient) {
      return gradient.match(/#[0-9A-Fa-f]{6}/g).map((color) => this.hexToRgb(color));
  },

  hexToRgb: function (hex) {
      const r = parseInt(hex.slice(1, 3), 16);
      const g = parseInt(hex.slice(3, 5), 16);
      const b = parseInt(hex.slice(5, 7), 16);
      return { r, g, b };
  },

  updateControlPointsFromColormap: function () {
    const numColors = this.colormap.length;

    // 重新设置控制点
    this.controlPoints = this.colormap.map((color, i) => ({
      offset: i / (numColors - 1), // 均匀分布
      value: this.globalMin + (i / (numColors - 1)) * (this.globalMax - this.globalMin),
      color,
    }));

    // 更新颜色比例尺
    this.updateColorScale();
    this.drawColorbar(); // 重绘颜色条
  },
}
}
</script>


