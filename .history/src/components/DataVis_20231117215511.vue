<template>
    <div id="data_vis">
        
            
            <canvas id="canvas" width="200" height="200"></canvas>
            <canvas id="colorbarCanvas" width="400" height="200"></canvas>
            
        
        
    
    
        
        <svg id="data_svg">

        </svg>
        
        <!-- <t-slider id ='slider' v-model="value1" :show-tooltip="true" :inputNumberProps="inputNumberProps" v-on:change="update"/> -->
        

        <!-- color -->
        <!-- <t-space id='color' size="5px">
        <t-space direction="vertical" size="5px" class="item">
            
            <t-color-picker v-model="color1" format="HEX" :color-modes="['monochrome']" v-on:change="update"/>
        </t-space>
        <t-space direction="vertical" size="5px" class="item">
            
            <t-color-picker v-model="color2" format="HEX" :color-modes="['monochrome']" v-on:change="update"/>
        </t-space>
        </t-space> -->

    </div>
</template>

<script>
import * as d3 from 'd3'
import parameters from '../../js/get_data.js';
// import { ref, unref, onMounted, onBeforeUnmount, watchEffect } from 'vue';
  


export default {
  name:'DataVis',
  data(){
      return{
          parameters:parameters,
          input_data:'',
          value1: 23,
          inputNumberProps: { theme: 'column'},
          svg:'',
          margin:40,
          width:(window.innerWidth*0.28)/1.05,
          height:(window.innerHeight)*0.7/1.05,
          color1: '#FFA500',
          color2: '#006400',
          rects:null,
      };
  },
  async created(){
    await this.data_vis()
    
  },
  methods:{
    data_vis:function(){

        
        const that = this
        function calculatePercentile(array, percentile) {
            const sortedArray = array.flat().sort((a, b) => a - b);
            const index = Math.floor((percentile / 100) * sortedArray.length);
            return sortedArray[index];
        }

        d3.json('./data/inputdata.json').then((d)=>{
            that.input_data = d[23]
            const min1 = d3.min(that.input_data.flat())
            const max1 = d3.max(that.input_data.flat())
            this.input_data = this.input_data.map((d)=>d.map(i=>(i-min1)/(max1-min1)))
            const min = d3.min(that.input_data.flat())
            const max = d3.max(that.input_data.flat())
            const q1 = calculatePercentile(that.input_data.flat(), 25);
            const q2 = calculatePercentile(that.input_data.flat(), 50);
            const q3 = calculatePercentile(that.input_data.flat(), 75);
            // document.getElemntById("#dataCanvas").setAttribute("width","75px")
            this.draw(min,max,q1,q2,q3)
            console.log(min,max,q1,q2,q3)
        })

        
    },
    draw:function(min,max,q1,q2,q3){
        // 假设这是你的100x100数组
const data = this.input_data;



const colorControlPoints = [
    { value: max*255, color: { r: 0, g: 0, b: 255 } },   // 蓝色
    { value: q3*255, color: { r: 0, g: 255, b: 0 } },  // 绿色
    { value: q2*255, color: { r: 255, g: 255, b: 0 } }, // 黄色
    { value: q1*255, color: { r: 255, g: 165, b: 0 } }, // 橙色
    { value: min*255, color: { r: 255, g: 0, b: 0 } },  // 红色s
];

// 生成100x100的随机数据


// 线性插值计算颜色
function interpolateColor(value) {
    let lower = colorControlPoints[0];
    let upper = colorControlPoints[colorControlPoints.length - 1];

    // 找到插值区间
    for (let i = 0; i < colorControlPoints.length - 1; i++) {
        if (value >= colorControlPoints[i].value/255 && value < colorControlPoints[i + 1].value/255) {
            lower = colorControlPoints[i];
            upper = colorControlPoints[i + 1];
            break;
        }
    }

    // 计算插值比例
    const t = (value - lower.value/255) / (upper.value/255 - lower.value/255);

    // 线性插值颜色
    return {
        r: lower.color.r + (upper.color.r - lower.color.r) * t,
        g: lower.color.g + (upper.color.g - lower.color.g) * t,
        b: lower.color.b + (upper.color.b - lower.color.b) * t
    };
}

// 将数据映射到颜色
function mapDataToColor(data) {
    return data.map(row => row.map(value => interpolateColor(value)));
}

// 创建一个canvas元素来绘制映射结果
const canvas = document.getElementById('canvas');
const context = canvas.getContext('2d');
canvas.width = 200;
canvas.height = 200;
canvas.id = 'canvas1'

document.body.appendChild(canvas);

// 绘制数据映射结果
function drawData(data) {
    const colorData = mapDataToColor(data);
    for (let i = 0; i < colorData.length; i++) {
        for (let j = 0; j < colorData[i].length; j++) {
            const color = colorData[i][j];
            context.fillStyle = `rgb(${color.r}, ${color.g}, ${color.b})`;
            context.fillRect(j, i, 1, 1);
        }
    }
}
drawData(data);
// 开始绘制

// 获取colorbar的canvas元素
const colorbarCanvas = document.getElementById('colorbarCanvas');
const colorbarContext = colorbarCanvas.getContext('2d');
const colorbarWidth = 200; // colorbar的宽度
const colorbarHeight = 80; // colorbar的高度

// 绘制colorbar
function drawColorbar() {
    const gradient = colorbarContext.createLinearGradient(0, 0, colorbarWidth, 0);
    
    // 添加控制点颜色
    
    for (const point of colorControlPoints) {
        // 使用正确的CSS颜色格式
        gradient.addColorStop(point.value/255, `rgb(${point.color.r}, ${point.color.g}, ${point.color.b})`);
    }

    colorbarContext.fillStyle = gradient;
    colorbarContext.fillRect(0, 0, colorbarWidth, colorbarHeight);
}

// 绘制控制点
function drawControlPoints() {
    for (const point of colorControlPoints) {
        const x = point.value / 255 * colorbarWidth;
        const y = colorbarHeight / 2;
        
        // 绘制小圆表示控制点
        colorbarContext.beginPath();
        colorbarContext.arc(x, y, 10, 0, Math.PI * 2);
        colorbarContext.fillStyle = 'black';
        colorbarContext.fill();
    }
}

// // 在colorbar上绘制控制点
// drawColorbar();
// drawControlPoints();

// 在colorbar上绘制控制点
drawColorbar();
drawControlPoints();



// 定义拖动状态
let isDragging = false;
let selectedControlPoint = null;

// 添加鼠标事件监听器
colorbarCanvas.addEventListener('mousedown', (e) => {
    const mouseX = e.clientX - colorbarCanvas.getBoundingClientRect().left;
    const mouseY = e.clientY - colorbarCanvas.getBoundingClientRect().top;

    // 检查是否点击了控制点
    for (const point of colorControlPoints) {
        const x = point.value / 255 * colorbarWidth;
        const y = colorbarHeight / 2;
        const distance = Math.sqrt((x - mouseX) ** 2 + (y - mouseY) ** 2);
        if (distance <= 10) {
            isDragging = true;
            selectedControlPoint = point;
            console.log(selectedControlPoint)
            break;
        }
    }
});

    colorbarCanvas.addEventListener('mousemove', (e) => {
        if (isDragging && selectedControlPoint) {
            const mouseX = e.clientX - colorbarCanvas.getBoundingClientRect().left;
            // 限制控制点的移动范围在colorbar内部
            const newX = Math.min(Math.max(mouseX, 0), colorbarWidth);
            selectedControlPoint.value = (newX / colorbarWidth) * 255;

            // 重新绘制colorbar和数据可视化
            drawColorbar();
            drawControlPoints();
            redrawDataVisualization();
        }
    });

    colorbarCanvas.addEventListener('mouseup', () => {
        isDragging = false;
        selectedControlPoint = null;
    });

// ...

// 重新绘制数据可视化结果
function redrawDataVisualization() {
    // 获取新的数据映射
    const colorData = mapDataToColor(data);

    // 清空canvas
    context.clearRect(0, 0, canvas.width, canvas.height);

    // 绘制新的数据映射
    for (let i = 0; i < colorData.length; i++) {
        for (let j = 0; j < colorData[i].length; j++) {
            const color = colorData[i][j];
            context.fillStyle = `rgb(${color.r}, ${color.g}, ${color.b})`;
            context.fillRect(j, i, 1, 1);
        }
    }
}

// 初始化数据可视化
function initVisualization() {
    // 绘制数据映射结果
    drawData(data);
}

// 初始化
initVisualization();

    },
    drawd3:function(min,max,q1,q2,q3){
        const data = this.input_data;
        const data1 = new Array(100).fill(0).map(() => new Array(100).fill(0).map(() => Math.random()));
        console.log(data1,this.input_data)
        const width = 200, height = 200;
            const colorbarWidth = 200, colorbarHeight = 20;

            // 颜色控制点
            let colorControlPoints = [
                { value: max, color: d3.rgb(0, 0, 255), id: 'max' },
                { value: q3, color: d3.rgb(0, 255, 0), id: 'q3' },
                { value: q2, color: d3.rgb(255, 255, 0), id: 'q2' },
                { value: q1, color: d3.rgb(255, 165, 0), id: 'q1' },
                { value: min, color: d3.rgb(255, 0, 0), id: 'min' }
            ];

            // 创建颜色比例尺
            const colorScale = d3.scaleLinear()
                .domain(colorControlPoints.map(d => d.value))
                .range(colorControlPoints.map(d => d.color));

            // 创建SVG元素
            const svg = d3.select('data_svg')
                .attr('width', width)
                .attr('height', height);

            // 绘制热图
            function drawHeatmap() {
                svg.selectAll('rect').remove();
                svg.selectAll('rect')
                    .data(data.flat())
                    .enter().append('rect')
                    .attr('x', (d, i) => (i % 100))
                    .attr('y', (d, i) => Math.floor(i / 100))
                    .attr('width', 1)
                    .attr('height', 1)
                    .attr('fill', d => colorScale(d));
            }

            // 创建颜色条
            const colorbarSvg = d3.select('body').append('svg')
                .attr('width', colorbarWidth)
                .attr('height', colorbarHeight);

            // 绘制颜色条
            function drawColorbar() {
                colorbarSvg.selectAll('rect').remove();
                colorbarSvg.selectAll('circle').remove();

                const gradient = colorbarSvg.append('defs')
                    .append('linearGradient')
                    .attr('id', 'gradient');

                colorControlPoints.forEach(point => {
                    gradient.append('stop')
                        .attr('offset', point.value)
                        .attr('stop-color', point.color.toString());
                });

                colorbarSvg.append('rect')
                    .attr('width', colorbarWidth)
                    .attr('height', colorbarHeight)
                    .style('fill', 'url(#gradient)');

                // 绘制控制点
                colorControlPoints.forEach(point => {
                    colorbarSvg.append('circle')
                        .attr('class', 'control-point')
                        .attr('cx', point.value * colorbarWidth)
                        .attr('cy', colorbarHeight / 2)
                        .attr('r', 5)
                        .attr('fill', point.color)
                        .attr('id', point.id)
                        .call(d3.drag().on('drag', dragged));
                });
            }

            // 拖动控制点
            function dragged(event, d) {
                d.value = Math.max(0, Math.min(1, event.x / colorbarWidth));
                colorControlPoints = colorControlPoints.map(p => {
                    if (p.id === d.id) return { ...p, value: d.value };
                    return p;
                });

                // 更新比例尺和重新绘制
                colorScale.domain(colorControlPoints.map(p => p.value));
                drawHeatmap();
                drawColorbar();
            }

            drawHeatmap();
            drawColorbar();
    },
    // draw_slice:function(data,index){
    //     // let index=1
    //     let group = this.svg.append("g");
    //     let newArray = data.flat(Infinity)
    //     const this_min = Math.min(...newArray)
    //     const this_max = Math.max(...newArray)
    //     const number = data.length
    //     // console.log(data.length)
    //     // console.log(this_min,this_max)
    //     // const scale_x = d3.scaleLinear().domain([0,data.length]).range([0.5*margin,width-0.5*margin])
    //     // const scale_y = d3.scaleLinear().domain([0,data[0].length]).range([width-0.5*margin,0.5*margin])
    //     let colorscale = d3.scaleLinear().domain([this_min,this_max]).range(['#FFA500','#006400'])
    //     // draw each slice first
    //     // for(let j =0;j<data.length;j++){
    //         let g = group
    //                 .append("g")
    //                 .selectAll() // make path 
    //                 .data(newArray)
    //                 .enter()
                    
    //                 .append("rect")
    //                 .attr('class','rects')
    //                 .attr('x',(d,i)=>this.margin+(i % number)*.86/4)
    //                 .attr('y',(d,i)=>this.margin+(parseInt(i / number)*.86/4))
    //                 .attr('fill',d=>colorscale(d))
    //                 .attr('width',0.4/4)
    //                 .attr('height',0.4/4)
    //                 .attr('opacity',.95)
    //         g.attr('transform',`translate(${index%3*120},${parseInt(index/3)*120})`)
    //     // }

    //     },
    update:function(){
        // console.log(this.color1)
        const data = this.input_data[this.value1].flat(Infinity)
        const this_min = Math.min(...data)
        const this_max = Math.max(...data)
        let colorscale = d3.scaleLinear().domain([this_min,this_max]).range([this.color1,this.color2])
        
        this.rects.style("fill",(d,i)=>colorscale(data[i]))
    },
}
}
</script>

<style scoped>
#data_vis{
    border:2px solid #a7b2ac;
    border-radius: 4px;
    position:absolute;
    top:28%;
    left:.7%;
    width: 28%;
    height: 70%;
}
#data_svg{
    position: absolute;
    top:10%;
    left:-2%
}
#slider{
    position: absolute;
    top:92%;
    left:10%;
    width:88%
}

#color{
    position: absolute;
    top:-1%;
    left:10%;
}
.item h5 {
  font-weight: normal;
}
#colorbarCanvas{
    position:absolute;
    top:75%;
    left:20%;
    width:100%;
    z-index:101
}
#dataCanvas{
    position:absolute;
    left:130px; 
    top:100px;
    /* z-index:101; */
}
#canvas1{
    position:absolute;
    left:50px; 
    top:350px;
    width:25%
    
}
</style>