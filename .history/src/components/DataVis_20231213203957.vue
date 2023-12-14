<template>
    <div id="data_vis">
        <div id="legendContainer"></div>
            
            <canvas id="canvas1" width="200" height="200"></canvas>
            <canvas id="colorbarCanvas" width="400" height="30"></canvas>
            
            <t-switch id="switch" size="large" v-model="checked" :label="['add point', 'use current points']"></t-switch>
            <t-input id='slice_id' label="slice_id:" v-model="slice_id" placeholder=23  @enter="onChange" autoWidth/>

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
import emitter from './eventBus.js';


export default {
  name:'DataVis',
  data(){
      return{
          parameters:parameters,
          checked:true,
          colormap:'',
          canvas:'',
          context:'',
          input_data:'',
          value1: 23,
          slice_id:23,
          inputNumberProps: { theme: 'column'},
          svg:'',
          margin:40,
          input_data_path:'',
          width:(window.innerWidth*0.28)/1.05,
          height:(window.innerHeight)*0.7/1.05,
          color1: '#FFA500',
          color2: '#006400',
          rects:null,
          
      };
  },
  async mounted(){
    this.canvas = document.getElementById('canvas1');
    this.context = this.canvas.getContext('2d');
    await emitter.on('myEvent', (data) => {
        if(this.input_data_path != data['input_data']){
            this.input_data_path = data['input_data']

            this.data_vis()
            this.defaultcolormap()
            // this.draw()
        }
        
          
            })
    
    
  },
  methods:{

    data_vis:function(){

        
        const that = this
        
        const path = String(this.input_data_path)
        console.log(path)
        d3.json(path).then((d)=>{
            that.input_data = d[this.slice_id]
            const min1 = d3.min(that.input_data.flat())
            const max1 = d3.max(that.input_data.flat())
            this.input_data = this.input_data.map((d)=>d.map(i=>(i-min1)/(max1-min1)))
            
            // this.canvas.width = 200;
            // this.canvas.height = 200;
            // this.canvas.id = 'canvas1'
            // document.body.appendChild(this.canvas);
            
            // document.getElemntById("#dataCanvas").setAttribute("width","75px")
            
            // this.draw(min,max,q1,q2,q3)
            // console.log(min,max,q1,q2,q3)
            
        })

        
    },
    draw:function(){
        // console.log(document.getElementById('input4').value)
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
        let color1 = []
        for(let i=0;i<5;i++){
            const min1 = colormap[0]
            const max1 = colormap[colormap.length-1]
            const r = min1.r + (i/5)*(max1.r-min1.r)
            const b = min1.b + (i/5)*(max1.b-min1.b)
            const g = min1.r + (i/5)*(max1.g-min1.g)
            let obj = {
                r:r,b:b,g:g
            }
            color1.push(obj)
        }

        const colorControlPoints = [
            { value: max*255, color: color1[0], label:'max' },   // 蓝色
            { value: q3*255, color: color1[1], label:'75%'},  // 绿色
            { value: q2*255, color: color1[2], label:'median'}, // 黄色
            { value: q1*255, color: color1[3], label:'25%' }, // 橙色
            { value: min*255, color: color1[4], label:'min' },  // 红色s
        ];



// 获取用于绘制图例的容器元素
// const legendContainer = document.getElementById('legendContainer');

// 创建图例
        function createLegend() {
        // 遍历控制点，为每个控制点创建一个图例项
        
        console.log('kk')
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
        const colorbarWidth = 350; // colorbar的宽度
        const colorbarHeight = 40; // colorbar的高度

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
            colorbarContext.strokeStyle = 'black'; // 例如，设置为黑色
            colorbarContext.lineWidth = 5;
            colorbarContext.strokeRect(0, 0, colorbarWidth, colorbarHeight);
        }

// 绘制控制点
        function isPointInsideCircle(mouseX, mouseY, point) {
            const x = (point.value / 255) * colorbarWidth;
            const y = colorbarHeight / 2;
            const distance = Math.sqrt((x - mouseX) ** 2 + (y - mouseY) ** 2);
        return distance<=10
        }

        function onCanvasDblClick(e) {
        console.log('dianji')
        
        var bbox = colorbarCanvas.getBoundingClientRect();
        const clickX = (e.clientX - colorbarCanvas.getBoundingClientRect().left)* (colorbarCanvas.width / bbox.width)
        const clickY = (e.clientY - colorbarCanvas.getBoundingClientRect().top)* (colorbarCanvas.height / bbox.height)
        

        // 查找并删除被双击的圆
        for (let i = 0; i < colorControlPoints.length; i++) {
            if (isPointInsideCircle(clickX, clickY, colorControlPoints[i])) {
            // 删除该圆
            
            colorControlPoints.splice(i, 1);
            // 重绘Canvas
            drawColorbar()
            drawControlPoints();
            
            break;
            }
        }
        }


        function drawControlPoints() {
            
            
            for (const point of colorControlPoints) {
                
                let x = point.value / 255 * colorbarWidth;
                if(x==0) x = 3.5
                
                const y = colorbarHeight / 2 - 3.5;
                
                // 绘制小圆表示控制点
                colorbarContext.beginPath();
                const text = point.label; // 要显示的文字
                // console.log(point)
                colorbarContext.arc(x, y, 7, 0, Math.PI * 2);
                colorbarContext.fillStyle = 'white';
                // colorbarContext.fillStyle = 'black'; // 文字颜色
                colorbarContext.font = '5px Arial'; // 文字样式
                colorbarContext.fillText(text, x - 4, y + 6 + 12); 
                colorbarContext.fill();
            }
            // drawColorbar();
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



        colorbarCanvas.addEventListener('mousedown', (e) => {
            var bbox = colorbarCanvas.getBoundingClientRect();
            if(!this.checked){

            
            
            const mouseX = (e.clientX - colorbarCanvas.getBoundingClientRect().left)* (colorbarCanvas.width / bbox.width)
            const mouseY = (e.clientY - colorbarCanvas.getBoundingClientRect().top)* (colorbarCanvas.height / bbox.height)
            console.log('点击',mouseX,mouseY)

            // 检查是否点击了控制点
            for (const point of colorControlPoints) {
                const x = (point.value / 255) * colorbarWidth;
                const y = colorbarHeight / 2;
                const distance = Math.sqrt((x - mouseX) ** 2 + (y - mouseY) ** 2);
                if (distance <= 10) {
                    isDragging = true;
                    selectedControlPoint = point;
                    // console.log(selectedControlPoint)
                    break;
                }
            }
        }
            else{
            
            const clickX = (e.clientX - colorbarCanvas.getBoundingClientRect().left)* (colorbarCanvas.width / bbox.width)
            const clickY = (e.clientY - colorbarCanvas.getBoundingClientRect().top)* (colorbarCanvas.height / bbox.height)
            


        // 检查点击位置是否在色条的垂直中心区域，您可以根据需要调整y坐标的检测范围
        if (clickY > colorbarHeight / 2 - 10 && clickY < colorbarHeight / 2 + 10) {
            // 创建一个新的圆形数据对象
            const value = (clickX/colorbarWidth)*255
            const lista = colorControlPoints.map((d)=>d.value)
            lista.push(value)
            
            const colormap = this.colormap.map((d)=>hexToRgb(d))
            const min1 = colormap[0]
            const max1 = colormap[colormap.length-1]
            const r = min1.r + clickX/colorbarWidth*(max1.r-min1.r)
            const b = min1.b + clickX/colorbarWidth*(max1.b-min1.b)
            const g = min1.r + clickX/colorbarWidth*(max1.g-min1.g)
            const newPoint = {
            value: value,
            
            radius: 7, // 圆的半径，可以根据需要进行调整
            color: {r: r, g: g, b: b} // 圆的颜色，可以根据需要进行调整
            };

            // 将新的圆形数据对象添加到数组中
            colorControlPoints.push(newPoint);
            // console.log(colorControlPoints)
            // 重绘色条和所有圆形
            // drawColorbar(); // 假设这是您绘制色条背景的函数
            context.clearRect(0, 0, canvas.width, canvas.height);
            drawColorbar()
            drawControlPoints();
            redrawDataVisualization(); // 这是绘制所有控制点圆形的函数
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
        colorbarCanvas.addEventListener('dblclick',onCanvasDblClick)
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
    onChange:function(){
        this.data_vis()
        const colormapSelect = document.getElementById('colormapSelect');
        const defaultColormaps = {
            Rainbow: 'linear-gradient(to right, #8B00FF, #0000FF, #00FFFF, #008000, #FFFF00, #FF0000)',

            Viridis: 'linear-gradient(to right, #440154, #48186a, #472d7b, #424086, #3b528b, #33638d, #2c728e, #26828e, #21918e, #1e9e8e, #28ae8e, #3bbc8e, #51cc8f, #69db8f, #80ea8f, #98f999)',
            Plasma: 'linear-gradient(to right, #0d0887, #46039f, #7201a8, #9c179e, #bd3786, #d85763, #ed7953, #fca636, #f0f921)',
            Inferno: 'linear-gradient(to right, #000004, #160b39, #420a68, #6a176e, #932667, #bb3654, #dd513a, #f3771d, #fdb724)',
        };
        const selectedColormap = colormapSelect.value;
    if (defaultColormaps[selectedColormap]) {
        // 应用选择的默认colormap
        // console.log(defaultColormaps[selectedColormap].split(', ').slice(1,-1))
        this.colormap = defaultColormaps[selectedColormap].split(', ').slice(1,-1)
        this.draw()
    }
        // this.defaultcolormap()
        // this.draw()
    },
    defaultcolormap:function(){
        const defaultColormaps = {
            Rainbow: 'linear-gradient(to right, #8B00FF, #0000FF, #00FFFF, #008000, #FFFF00, #FF0000)',

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
    background-color:'lightgrey'
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
#switch{
    position: absolute;
    top:10%;
    left:70%;
    z-index:101
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
    top:80%;
    left:7%;
    
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
    top:150px;
    width:60%
    
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
    display: block;
    /* top:350px; */
    width:25%
}
#slice_id{
    position: absolute;
    top:2%;
    left:30%
}
</style>