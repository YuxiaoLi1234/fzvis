<template>
    <div id="data_vis">
        <canvas id="dataCanvas" width="400" height="400"></canvas>
    <canvas id="colorbarCanvas" width="400" height="20"></canvas>
    <div id="colorMapControls">
        <!-- 在此处动态添加颜色控制点的界面 -->
    </div>
    <button id="addPoint">Add Control Point</button>
        <div id="controller">
            <input type="range" min="-10" max="10" value="0" class="sliceIndex"/>
        </div>
        <div id="controlPanel">
        <label for="opacity">Opacity:</label>
        <input type="range" id="opacity" min="0" max="1" step="0.01">
    </div>
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
            const min = d3.min(that.input_data.flat())
            const max = d3.max(that.input_data.flat())

            const q1 = calculatePercentile(that.input_data.flat(), 25);
            const q2 = calculatePercentile(that.input_data.flat(), 50);
            const q3 = calculatePercentile(that.input_data.flat(), 75);
            this.draw(min,max,q1,q2,q3)
        })

        
    },
    draw:function(min,max,q1,q2,q3){
        // 假设这是你的100x100数组
const data = this.input_data;

// 定义一些颜色控制点
// 这里的value应该是介于数据的最小值和最大值之间
// const minValue = Math.min(...data.flat());

// // 计算最大值
// const maxValue = Math.max(...data.flat());

// // 对数组进行排序
// const sortedData = data.slice().sort((a, b) => a - b);

// // 计算第25百分位数（四分之一位数）
// const q1 = sortedData[Math.floor(sortedData.length * 0.25)];

// // 计算第50百分位数（中位数）
// const median = sortedData[Math.floor(sortedData.length * 0.5)];

// // 计算第75百分位数（四分之三位数）
// const q3 = sortedData[Math.floor(sortedData.length * 0.75)];

const colorControlPoints = [
    { value: min, color: { r: 0, g: 0, b: 255 } },   // 蓝色
    { value: q1, color: { r: 0, g: 255, b: 0 } },  // 绿色
    { value: median, color: { r: 255, g: 255, b: 0 } }, // 黄色
    { value: q2, color: { r: 255, g: 165, b: 0 } }, // 橙色
    { value: q3, color: { r: 255, g: 0, b: 0 } },  // 红色
    
];

// 生成100x100的随机数据


// 线性插值计算颜色
function interpolateColor(value) {
    let lower = colorControlPoints[0];
    let upper = colorControlPoints[colorControlPoints.length - 1];

    // 找到插值区间
    for (let i = 0; i < colorControlPoints.length - 1; i++) {
        if (value >= colorControlPoints[i].value && value < colorControlPoints[i + 1].value) {
            lower = colorControlPoints[i];
            upper = colorControlPoints[i + 1];
            break;
        }
    }

    // 计算插值比例
    const t = (value - lower.value) / (upper.value - lower.value);

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
const canvas = document.createElement('canvas');
const context = canvas.getContext('2d');
canvas.width = 100;
canvas.height = 100;
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
const colorbarHeight = 20; // colorbar的高度

// 绘制colorbar
function drawColorbar() {
    const gradient = colorbarContext.createLinearGradient(0, 0, colorbarWidth, 0);
    
    // 添加控制点颜色
    for (const point of colorControlPoints) {
        // 使用正确的CSS颜色格式
        gradient.addColorStop(point.value / 255, `rgb(${point.color.r}, ${point.color.g}, ${point.color.b})`);
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
        colorbarContext.arc(x, y, 5, 0, Math.PI * 2);
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
        if (distance <= 5) {
            isDragging = true;
            selectedControlPoint = point;
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
</style>