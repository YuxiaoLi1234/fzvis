<template>
  <div id="data_vis">
    <div id="zoomWarning" style="display: none; color: red; font-size: 14px; position: absolute; top: 10px; right: 10px; z-index: 1000;">
        Cannot zoom in further. Minimum zoom size reached!
    </div>

    <div id="controls" class="d-flex flex-wrap align-items-center p-2 gap-2">
      <select id="colormapSelect" class="form-select w-auto" aria-label="colormap">
        <option value="Rainbow">Rainbow</option>
        <option value="Viridis">Viridis</option>
        <option value="Plasma">Plasma</option>
        <option value="Inferno">Inferno</option>
      </select>
      <input type="number" id="slice_id" class="form-control" style="max-width: 120px" placeholder="Slice ID" v-model="slice_id"/>
      <button id="input-button" class="btn btn-outline-primary" @click="vis_input">Input Mode<i class="bi bi-box-arrow-in-left ms-1"></i></button>
      <button id="output-button" class="btn btn-outline-primary" @click="vis_output">Output Mode<i class="bi bi-box-arrow-in-right ms-1"></i></button>
      <button id="error-button" class="btn btn-outline-primary" @click="vis_error">Error Map<i class="bi bi-bug ms-1"></i>
      </button>
      <button id="reset-button" class="btn btn-outline-primary" @click="resetView">Reset<i class="bi bi-arrow-clockwise ms-1"></i></button>
      <button id="undo-button" class="btn btn-outline-dark" @click="undoZoom" :disabled="historyStack.length === 0">Undo<i class="bi bi-arrow-counterclockwise"></i></button>
    </div>

    <!-- <div class="visualization-area">
      <div id="svgCanvasContainer">
        <svg id="svgCanvas"></svg>
      </div>
      <svg id="colorbarCanvas"></svg>
    </div> -->

  </div>
</template>

<script>
import * as d3 from 'd3'
import emitter from './eventBus.js';

export default {
  name:'DataVis',
  data() {
    return {
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
      compressor_name:[],
      historyStack: [],
      configurations: null,
    };
  },


  async mounted(){
    
    await emitter.on("file-input", async (data) => {
        const { metadata, content } = data;

        this.width = metadata['width'];
        this.height = metadata['height'];
        this.depth = metadata['depth'];

        // Check if content is ArrayBuffer
        console.log("content:", content);
        console.log(content instanceof ArrayBuffer);
        if (!content || !(content instanceof ArrayBuffer)) {
            console.error("Invalid data content!");
            return;
        }

        // Parse the binary data
        if (metadata.precision === 'f') {
            this.input_data = Array.from(new Float32Array(content));
        } else if (metadata.precision === 'd') {
            this.input_data = Array.from(new Float64Array(content));
        } else {
            console.error("Unsupported precision type!");
            return;
        }

        this.mode = "input";
        this.drawZoom = false;
        this.draw_data = this.input_data;
        this.data_vis(this.input_data);
        this.defaultcolormap();
        this.draw();
    });

    await emitter.on('inputdata', (data) => {
        this.width = data['width'];
        this.height = data['height'];
        this.depth = data['depth'];
        this.input_data = Object.values(data["input_data"]);  
        this.decp_data = data["decp_data"];  
        this.compressor_name = data["compressor_name"];  
    })

    await emitter.on('compressor_configuration', (data) => {
        console.log(data)
        this.configurations = data
        
    })

  },
  methods:{
      vis_error: function () {
        if (!this.input_data || !this.decp_data.length) {
          console.error("Input data or decompressed data is missing.");
          return;
        }

        this.mode = "error";
        this.drawZoom = false;

        let error_maps = [];

        for (let i = 0; i < this.decp_data.length; i++) {
          let error_map = this.decp_data[i].map((row, rowIndex) =>
            row.map((val, colIndex) => Math.abs(val - this.input_data[rowIndex][colIndex]))
          );
          error_maps.push(error_map);
        }

        console.log(error_maps)
        this.draw_data = error_maps;
        this.data_vis(error_maps);
        this.defaultcolormap();
        this.draw();
      },

      vis_input: function () {
      
          this.mode = "input";
          this.drawZoom = false;
          this.draw_data = this.input_data
          console.log(this.draw_data)
          this.data_vis(this.input_data);
          this.defaultcolormap();
          this.draw();
          
      },

      vis_output: function () {

        if (!this.input_data || !this.decp_data.length) {
            console.error("Input data or decompressed data is missing.");
            return;
        }

        this.mode = "decp";
        
        this.drawZoom = false;
        let datasets = [this.input_data]; // 先加入 input_data
        if(this.compressor_name[0] != "Original Data") this.compressor_name.unshift("Original Data"); // 在 compressor_name 开头插入 "Original Data"

        this.decp_data.forEach((data) => {
            datasets.push(data);
        });
        
        this.draw_data = datasets;
        this.data_vis();
        this.defaultcolormap();
        this.draw();
      },


      data_vis: function () {
          let datasets = [];
          let globalMin = Infinity;
          let globalMax = -Infinity;

          if (this.mode === "input") {
            // 展平并提取当前切片

            let flatData;
            
            flatData = this.input_data.flat().flat();
            
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

          } else if (this.mode === "decp" || this.mode == "error") {
            for (let i = 0; i < this.draw_data.length; i++) {
              const flatData = this.draw_data[i].flat().flat();
              const slice = flatData.slice(
                this.slice_id * this.width * this.height,
                (this.slice_id + 1) * this.width * this.height
              );
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
            console.log(min, max)
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
          
        
          this.controlPoints = [
              { r: 0, g: 0, b: 255 },
              { r: 0, g: 255, b: 0 },
              { r: 255, g: 0, b: 0 },
          ].map((color, i) => ({
              offset: i / 2,
              value: globalMin + (i / 2) * (globalMax - globalMin),
              color,
          }));
          

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

        const gap = 10; // 数据集间隙
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

        datasets.forEach((data, datasetIndex) => {
            const col = datasetIndex % maxColumns; // 当前列
            const row = Math.floor(datasetIndex / maxColumns); // 当前行

            // 计算水平偏移量，使每行居中
            const totalRowWidth = columns * (dataWidth * cellSize) + (columns - 1) * gap; // 当前行总宽度
            const rowStartX = (canvasWidth - totalRowWidth) / 2; // 居中的起始位置

            const startX = rowStartX + col * (dataWidth * cellSize + gap); // 当前矩阵的横向偏移
            const startY = row * (rowHeight + gap); // 当前矩阵的纵向偏移

            // 绘制矩阵
            const rects = svgCanvas
            .selectAll(`.data-rect-${datasetIndex}`)
            .data(data.flat())
            .enter()
            .append("rect")
            .attr("x", (d, i) => startX + (i % dataWidth) * cellSize)
            .attr("y", (d, i) => startY + Math.floor(i / dataWidth) * cellSize)
            .attr("value", (d)=>d)
            .attr("width", cellSize)
            .attr("height", cellSize)
            .attr("fill", (d) => this.colorScale(d))
            .attr("class", `data-rect-${datasetIndex}`);

            if (this.mode === "decp" || this.mode === "error") {
                rects
                .on("mouseover", (event) => {
                    
                      d3.select(event.target).style("stroke", "yellow").style("stroke-width", 2); 
                      const value  = d3.select(event.target).attr("value")
                      
                      let compressorConfig = this.compressor_name[datasetIndex] || "Unknown";
                      console.log(compressorConfig, datasetIndex)
                      if(this.mode == "error") {
                        compressorConfig = this.compressor_name[0] == "Original Data"? this.compressor_name[datasetIndex + 1]:this.compressor_name[datasetIndex] || "Unknown";
                        // console.log(this.compressor_name, datasetIndex, this.compressor_name[datasetIndex])
                      }
                      
                      console.log(compressorConfig, datasetIndex)
                      let errorBoundType, errorBoundValue;
                      if(compressorConfig!="Original Data"){
                        if(this.configurations[compressorConfig]["compressor_config"]["pressio:abs"]){
                          errorBoundType = "ABS";
                          errorBoundValue = this.configurations[compressorConfig]["compressor_config"].pressio_abs
                        }
                        else{
                          const errorBoundEntry = Object.entries(this.configurations[compressorConfig]["compressor_config"]).find(([key]) =>
                            key.includes("error_bound")
                          );

            
                          errorBoundType = errorBoundEntry[0].split(":")[1].split("_error_bound")[0].toUpperCase();
                          errorBoundValue =errorBoundEntry[1];
                        }
                    }
                      
                      
                      const compressorType = this.configurations?.[compressorConfig]?.compressor_id || "N/A";
                      if(compressorConfig=="Original Data"){
                        this.tooltip
                        .style("opacity", 1)
                        .html(`
                          <strong>Original Data</strong> <br>
                          <strong>Value:</strong> ${value} <br>
                          `);
                      }
                      else{
                        this.tooltip
                        .style("opacity", 1)
                        .html(`
                          <strong>Compressor:</strong> ${compressorConfig} <br>
                          <strong>Type:</strong> ${compressorType} <br>
                          <strong>Error Bound Type: </strong> ${errorBoundType} <br>
                          <strong>Error Bound Value: </strong> ${errorBoundValue} <br>
                          <strong>Value:</strong> ${value} <br>
                          `);
                        }
                    
                  })
                .on("mousemove", (event) => {
                  this.tooltip
                    .style("left", `${event.pageX + 15}px`)
                    .style("top", `${event.pageY + 15}px`);
                })
                .on("mouseout", (event) => {
                  d3.select(event.target).style("stroke", "none"); 
                  this.tooltip.style("opacity", 0);
                });
            }
            if(this.mode == "decp"){
              svgCanvas
                .append("text")
                .attr("x", startX + (dataWidth * cellSize) / 2) 
                .attr("y", startY + dataHeight * cellSize + textPadding / 2) 
                .attr("text-anchor", "middle")
                .attr("font-size", "12px")
                .attr("fill", datasetIndex === 0 ? "blue" : "black")
                .text(this.compressor_name[datasetIndex]);
            }
            else if(this.mode == "input"){

              svgCanvas
                .append("text")
                .attr("x", canvasWidth / 4) 
                .attr("y", canvasHeight / 2) 
                .attr("text-anchor", "middle")
                .attr("font-size", "20px")
                .attr("fill", "black")
                .text("Original Data");
            }else{
              svgCanvas
                .append("text")
                .attr("x", startX + (dataWidth * cellSize) / 2) 
                .attr("y", startY + dataHeight * cellSize + textPadding / 2) 
                .attr("text-anchor", "middle")
                .attr("font-size", "12px")
                .attr("fill", "black")
                .text(this.compressor_name[datasetIndex+1]);
            }
            
        });

        this.addZoomInteraction(); // 添加缩放交互
      },

      resetView: function () {
        this.historyStack = [];
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
          let startX, startY;
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
                const gap = 10; 
                const numDatasets = this.draw_data.length;
                const maxColumns = 5; 
                const columns = Math.min(maxColumns, numDatasets); 
                const rows = Math.ceil(numDatasets / columns); 
                
                const maxDatasetWidth = (canvasWidth - (columns - 1) * gap) / columns;
                const maxDatasetHeight = (canvasHeight - (rows - 1) * gap) / rows; 
                const cellSize = Math.min(maxDatasetWidth / dataWidth, maxDatasetHeight / dataHeight); 
                
                const svgCanvas = d3.select("#svgCanvas");

                // 1️⃣ 确保鼠标坐标是相对 `svgCanvas` 的
                const [x, y] = d3.pointer(event, svgCanvas.node());
                console.log("Mouse Position - X:", x, "Y:", y);

                // 2️⃣ 获取第一个 `rect` 作为数据集的起始参考点
                const firstRect = d3.select("#svgCanvas rect").node();
                const firstRectX = firstRect ? parseFloat(firstRect.getAttribute("x")) : 0;
                const firstRectY = firstRect ? parseFloat(firstRect.getAttribute("y")) : 0;
                console.log("First Rect Position - X:", firstRectX, "Y:", firstRectY);

                // 3️⃣ 计算相对坐标 (考虑 `firstRect` 的偏移)
                const relativeStartX = x;
                const relativeStartY = y;

                // 4️⃣ 计算选中的数据集索引
                const selectedDatasetIndex =
                  Math.floor(relativeStartY / (maxDatasetHeight + gap)) * maxColumns +
                  Math.floor(relativeStartX / (maxDatasetWidth + gap));

                console.log("Selected Dataset Index:", selectedDatasetIndex);
                
                if (selectedDatasetIndex >= this.draw_data.length) return;

                let datasetStartX, datasetStartY;
                if(selectedDatasetIndex == 0 ){
                  datasetStartX = (selectedDatasetIndex % maxColumns) * (maxDatasetWidth + gap) + firstRectX
                  datasetStartY = Math.floor(selectedDatasetIndex / maxColumns) * (maxDatasetHeight + gap) + firstRectY
                  
                }
                else{
                  datasetStartX = (selectedDatasetIndex % maxColumns) * (maxDatasetWidth)
                  datasetStartY = Math.floor(selectedDatasetIndex / maxColumns) * (maxDatasetHeight)
                }
                
                console.log("data position is:", startX, datasetStartX, datasetStartY)
                const relativeXStart = Math.max(0, Math.floor(startX - datasetStartX) / cellSize);
                const relativeXEnd = Math.min(
                  this.width,
                  Math.ceil((endX - datasetStartX) / cellSize)
                );
                
                const relativeYStart = Math.max(0, Math.floor(startY - datasetStartY) / cellSize);
                const relativeYEnd = Math.min(
                  this.height,
                  Math.ceil((endY - datasetStartY) / cellSize)
                );
                console.log("position is:", relativeXStart, relativeXEnd, relativeYStart, relativeYEnd)

                if (relativeXEnd - relativeXStart <= 0 || relativeYEnd - relativeYStart <= 0) {
                  alert("Zoomed area is too small! Please select a larger area.");
                  return;
                }

                // 🔹 在缩放前存储当前数据，便于撤销
                this.historyStack.push(JSON.parse(JSON.stringify(this.draw_data))); 

                const zoomedData = this.draw_data.map((data) =>
                  data.slice(relativeYStart, relativeYEnd).map((row) =>
                    row.slice(relativeXStart, relativeXEnd)
                  )
                );

                this.zoomedData = zoomedData;
                this.draw_data = zoomedData;
                this.draw(zoomedData);
              }
            });
      },

      undoZoom: function () {
          if (this.historyStack.length > 0) {
              this.draw_data = this.historyStack.pop(); // 取出最后一次缩放前的视图
              this.draw(this.draw_data); // 重新绘制
          } else {
              alert("No more zoom levels to undo!");
          }
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


