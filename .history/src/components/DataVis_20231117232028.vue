<template>
    <div id="data_vis">
        <div id="legendContainer"></div>
            
            <canvas id="canvas" width="200" height="200"></canvas>
            <canvas id="colorbarCanvas" width="400" height="200"></canvas>
        
    

            <select id="colormapSelect">
    
</select>

        
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
          colormap:'',
          canvas:'',
          context:'',
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
        

        d3.json('./data/inputdata.json').then((d)=>{
            that.input_data = d[23]
            const min1 = d3.min(that.input_data.flat())
            const max1 = d3.max(that.input_data.flat())
            this.input_data = this.input_data.map((d)=>d.map(i=>(i-min1)/(max1-min1)))
            this.canvas = document.getElementById('canvas');
            this.context = this.canvas.getContext('2d');
            this.canvas.width = 200;
            this.canvas.height = 200;
            this.canvas.id = 'canvas1'
            document.body.appendChild(this.canvas);
            
            // document.getElemntById("#dataCanvas").setAttribute("width","75px")
            this.defaultcolormap()
            // this.draw(min,max,q1,q2,q3)
            // console.log(min,max,q1,q2,q3)
            
        })

        
    },
    draw:function(){
        function calculatePercentile(array, percentile) {
            const sortedArray = array.flat().sort((a, b) => a - b);
            const index = Math.floor((percentile / 100) * sortedArray.length);
            return sortedArray[index];
        }
        const that = this
        // 假设这是你的100x100数组
        const canvas = that.canvas
        const context = that.context
        const data = that.input_data;
        const min = d3.min(that.input_data.flat())
        const max = d3.max(that.input_data.flat())
        const q1 = calculatePercentile(that.input_data.flat(), 25);
        const q2 = calculatePercentile(that.input_data.flat(), 50);
        const q3 = calculatePercentile(that.input_data.flat(), 75);

function hexToRgb(hex) {
    // 去掉可能包含的 '#' 符号
    hex = hex.replace(/^#/, '');

    // 将十六进制颜色代码分割成红色、绿色和蓝色部分
    const r = parseInt(hex.slice(0, 2), 16);
    const g = parseInt(hex.slice(2, 4), 16);
    const b = parseInt(hex.slice(4, 6), 16);

    // 返回一个包含 RGB 值的对象
    return {
        r: r,
        g: g,
        b: b
    };
}
const colormap = this.colormap.map((d)=>hexToRgb(d))
console.log(colormap)


const colorControlPoints = [
    { value: max*255, color: { r: colormap[0].r, g: colormap[0].g, b: colormap[0].b }, label:'max' },   // 蓝色
    { value: q3*255, color: { r: colormap[1].r, g: colormap[1].g, b: colormap[1].b }, label:'75%'},  // 绿色
    { value: q2*255, color: { r: colormap[2].r, g: colormap[2].g, b: colormap[2].b }, label:'median'}, // 黄色
    { value: q1*255, color: { r: colormap[3].r, g: colormap[3].g, b: colormap[3].b }, label:'25%' }, // 橙色
    { value: min*255, color: { r: colormap[4].r, g: colormap[4].g, b: colormap[4].b }, label:'min' },  // 红色s
];

// 生成100x100的随机数据

const controlPoints = [
    { value: 0.0, color: "#0000FF", label: "Min" },
    { value: 0.25, color: "#00FF00", label: "25th Percentile" },
    { value: 0.5, color: "#FF0000", label: "Median" },
    { value: 0.75, color: "#FFFF00", label: "75th Percentile" },
    { value: 1.0, color: "#FF00FF", label: "Max" }
];

// 获取用于绘制图例的容器元素
const legendContainer = document.getElementById('legendContainer');

// 创建图例
function createLegend() {
  // 遍历控制点，为每个控制点创建一个图例项
  controlPoints.forEach((point) => {
    const legendItem = document.createElement('div');
    legendItem.classList.add('legend-item');

    // 创建颜色块
    const colorBlock = document.createElement('div');
    colorBlock.classList.add('color-block');
    colorBlock.style.backgroundColor = point.color;

    // 创建标签
    const label = document.createElement('span');
    label.classList.add('label');
    label.textContent = point.label;

    // 将颜色块和标签添加到图例项中
    legendItem.appendChild(colorBlock);
    legendItem.appendChild(label);

    // 将图例项添加到图例容器中
    legendContainer.appendChild(legendItem);
  });
}


// 调用创建图例函数
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
        const text = point.label; // 要显示的文字
        // console.log(point)
        colorbarContext.arc(x, y, 8, 0, Math.PI * 2);
        colorbarContext.fillStyle = 'white';
        // colorbarContext.fillStyle = 'black'; // 文字颜色
        colorbarContext.font = '12px Arial'; // 文字样式
        colorbarContext.fillText(text, x - 4, y + 6 + 12); 
        colorbarContext.fill();
    }
}

// // 在colorbar上绘制控制点
// drawColorbar();
// drawControlPoints();

// 在colorbar上绘制控制点
drawColorbar();
drawControlPoints();
createLegend();




// 定义拖动状态
let isDragging = false;
let selectedControlPoint = null;

// 添加鼠标事件监听器
colorbarCanvas.addEventListener('mousedown', (e) => {
    var bbox = colorbarCanvas.getBoundingClientRect();
    const mouseX = (e.clientX - colorbarCanvas.getBoundingClientRect().left)* (colorbarCanvas.width / bbox.width)
    const mouseY = (e.clientY - colorbarCanvas.getBoundingClientRect().top)* (colorbarCanvas.height / bbox.height)
    console.log('点击',mouseX,mouseY)
    
    for (const point of colorControlPoints) {
        const x = (point.value / 255) * colorbarWidth;
        const y = colorbarHeight / 2;
        console.log(x,y)
    }
    // 检查是否点击了控制点
    for (const point of colorControlPoints) {
        const x = (point.value / 255) * colorbarWidth;
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
    defaultcolormap:function(){
        const defaultColormaps = {
            Rainbow: 'linear-gradient(to right, violet, blue, cyan, green, yellow, red)',
            Viridis: 'linear-gradient(to right, #440154, #48186a, #472d7b, #424086, #3b528b, #33638d, #2c728e, #26828e, #21918e, #1e9e8e, #28ae8e, #3bbc8e, #51cc8f, #69db8f, #80ea8f, #98f999)',
            Plasma: 'linear-gradient(to right, #0d0887, #46039f, #7201a8, #9c179e, #bd3786, #d85763, #ed7953, #fca636, #f0f921)',
            Inferno: 'linear-gradient(to right, #000004, #160b39, #420a68, #6a176e, #932667, #bb3654, #dd513a, #f3771d, #fdb724)',
        };
        const colormapSelect = document.getElementById('colormapSelect');
        for (const colormapName in defaultColormaps) {
    const option = document.createElement('option');
    option.value = colormapName;
    option.text = colormapName;
    colormapSelect.appendChild(option);
}

// 默认colormap选择事件监听器
colormapSelect.addEventListener('change', () => {
    const selectedColormap = colormapSelect.value;
    if (defaultColormaps[selectedColormap]) {
        // 应用选择的默认colormap
        // console.log(defaultColormaps[selectedColormap].split(', ').slice(1,-1))
        this.colormap = defaultColormaps[selectedColormap].split(', ').slice(1,-1)
        this.draw()
    }
});

    },
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
#colormapSelect{
    position:absolute;
    left:10px; 
    top:10px;
    width:25%
}
.legend-item {
  display: flex;
  align-items: center;
  margin-bottom: 5px;
}

/* 颜色块样式 */
.color-block {
  width: 20px;
  height: 20px;
  margin-right: 10px;
  border: 1px solid #000;
}

/* 标签样式 */
.label {
  font-size: 14px; /* 根据需要进行设置 */
}
#legendContainer{
    position:absolute;
    left:10px; 
    /* top:350px; */
    width:25%
}

</style>