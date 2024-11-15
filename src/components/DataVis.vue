<template>
    <div id="data_vis">
        <div id="legendContainer"></div>
        <div>
    <button id='file' @click="showMessage">DataVis</button>
  </div>
            <canvas id="canvas1" width="200" height="200"></canvas>
            <canvas id="colorbarCanvas" width="400" height="30"></canvas>
            <t-switch id="switch" size="large" v-model="checked" :label="['add point', 'use current points']"></t-switch>
            <t-input id='slice_id' label="slice_id:" v-model="slice_id" placeholder=23  @enter="onChange" autoWidth/>
            <select id="colormapSelect"></select>
            <svg id="data_svg"></svg>
    </div>
</template>
<script>
import * as d3 from 'd3'
import emitter from './eventBus.js';
import config from '../../config.json';
export default {
  name:'DataVis',
  data(){
      return{
            uploadMethod: 'requestSuccessMethod',
          parameters:'',
          checked:true,
          host:config.API_HOST,
          port:config.API_PORT,
          file: null,
          colormap:'',
          canvas:'',
          context:'',
          loaddata:0,
          whole_input_data:'',
          value1: null,
          slice_id:null,
          width:null,
          height:null,
          depth:null,
          inputNumberProps: { theme: 'column'},
          svg:'',
          margin:40,
          input_data_path:'',
          width1:(window.innerWidth*0.28)/1.05,
          height1:(window.innerHeight)*0.7/1.05,
          color1: '#FFA500',
          color2: '#006400',
          rects:null,
          
      };
  },
  async mounted(){
    this.canvas = document.getElementById('canvas1');
    this.context = this.canvas.getContext('2d');
    await emitter.on('inputdata', (data) => {
        this.width = data['width'];
        this.height = data['height'];
        this.depth = data['depth'];
        this.input_data = Object.values(data["input_data"]);  
    })
  },
  computed: {
    requestMethod() {
      return this[this.uploadMethod];
    },
  },
  watch: {
    uploadMethod() {
      this.files = [];
    },
  },
  methods:{
    requestSuccessMethod(file) {
      console.log(file, file.raw);
      return new Promise((resolve) => {
        let percent = 0;
        const percentTimer = setInterval(() => {
          if (percent + 10 < 99) {
            percent += 10;
            this.$refs.uploadRef.uploadFilePercent({ file, percent });
          } else {
            clearInterval(percentTimer);
          }
        }, 100);

        const timer = setTimeout(() => {
          
          resolve({ status: 'success', response: { url: 'https://tdesign.gtimg.com/site/avatar.jpg' } });

          clearTimeout(timer);
          clearInterval(percentTimer);
        }, 800);
      });
    },

    convertTo3DArray(arr, x, y, z) {
    if (arr.length !== x * y * z) {
        console.log(arr.length, x, y, z);
        throw new Error('The size of the input array does not match the specified dimensions.');
    }

    const array3D = [];
    let index = 0;

    for (let i = 0; i < x; i++) {
        const array2D = [];
        for (let j = 0; j < y; j++) {
            const array1D = [];
            for (let k = 0; k < z; k++) {
                array1D.push(arr[index++]); 
            }
            array2D.push(array1D); 
        }
        array3D.push(array2D); 
    }

    return array3D;
    },
    requestFailMethod(file) {
      console.log(file);
      return new Promise((resolve) => {
        resolve({ status: 'fail', error: '上传失败，请检查文件是否符合规范' });
      });
    },
    
    showMessage(){
        this.loaddata = 1
                this.data_vis()
                this.defaultcolormap()
                this.draw()
        
    },
    
    data_vis:function(){        
        const that = this
        console.log(this.input_data)
	this.draw_data = that.input_data.flat().flat().slice(this.slice_id * this.width * this.height, (this.slice_id + 1) * this.width * this.height)
        const min1 = d3.min(this.draw_data)
        const max1 = d3.max(this.draw_data)
        //this.input_data = this.input_data.map((d)=>d.map(i=>(i-min1)/(max1-min1))) 
        this.draw_data = this.draw_data.map(i=>(i-min1)/(max1-min1))
    },
    draw:function(){
        function calculatePercentile(array, percentile) {
            const sortedArray = array.flat().sort((a, b) => a - b);
            const index = Math.floor((percentile / 100) * sortedArray.length);
            return sortedArray[index];
        }
        const that = this
        const canvas = that.canvas
        const context = that.context
        const data = that.draw_data;

        const min = d3.min(data)
        const max = d3.max(data)
        const q1 = calculatePercentile(data, 25);
        const q2 = calculatePercentile(data, 50);
        const q3 = calculatePercentile(data, 75);

        function hexToRgb(hex) {
            hex = hex.replace(/^#/, '');
            const r = parseInt(hex.slice(0, 2), 16);
            const g = parseInt(hex.slice(2, 4), 16);
            const b = parseInt(hex.slice(4, 6), 16);
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
            { value: max*255, color: color1[0], label:'max' },   
            { value: q3*255, color: color1[1], label:'75%'}, 
            { value: q2*255, color: color1[2], label:'median'}, 
            { value: q1*255, color: color1[3], label:'25%' }, 
            { value: min*255, color: color1[4], label:'min' },
        ];

        function createLegend() {
        
        console.log('kk')
        }

        function interpolateColor(value) {
            let lower = colorControlPoints[0];
            let upper = colorControlPoints[colorControlPoints.length - 1];

            for (let i = 0; i < colorControlPoints.length - 1; i++) {
                if (value >= colorControlPoints[i].value/255 && value < colorControlPoints[i + 1].value/255) {
                    lower = colorControlPoints[i];
                    upper = colorControlPoints[i + 1];
                    break;
                }
            }

            const t = (value - lower.value/255) / (upper.value/255 - lower.value/255);

            return {
                r: lower.color.r + (upper.color.r - lower.color.r) * t,
                g: lower.color.g + (upper.color.g - lower.color.g) * t,
                b: lower.color.b + (upper.color.b - lower.color.b) * t
            };
        }

        function mapDataToColor(data) {
            return data.map(value => interpolateColor(value));
        }

        function drawData(data) {
            const colorData = mapDataToColor(data);
            var blockSize = canvas.width/(that.width)
            var blockSize1 = canvas.height/(that.height)
            context.clearRect(0, 0, canvas.width, canvas.height);

            for (let i = 0; i < that.height; i++) {
                for (let j = 0; j < that.width; j++) {
                    const color = colorData[i * that.width + j];
                    context.fillStyle = `rgb(${color.r}, ${color.g}, ${color.b})`;
                    context.fillRect(j*blockSize, i*blockSize1, blockSize, blockSize1);
                }
            }
            
        }
        drawData(data);

        const colorbarCanvas = document.getElementById('colorbarCanvas');
        const colorbarContext = colorbarCanvas.getContext('2d');
        const colorbarWidth = 350;
        const colorbarHeight = 40; 

        function drawColorbar() {
            const gradient = colorbarContext.createLinearGradient(0, 0, colorbarWidth, 0);
            for (const point of colorControlPoints) {
                gradient.addColorStop(point.value/255, `rgb(${point.color.r}, ${point.color.g}, ${point.color.b})`);
            }
            colorbarContext.fillStyle = gradient;
        
            colorbarContext.fillRect(0, 0, colorbarWidth, colorbarHeight);
            colorbarContext.strokeStyle = 'black'; 
            colorbarContext.lineWidth = 5;
            colorbarContext.strokeRect(0, 0, colorbarWidth, colorbarHeight);
        }

        function isPointInsideCircle(mouseX, mouseY, point) {
            const x = (point.value / 255) * colorbarWidth;
            const y = colorbarHeight / 2;
            const distance = Math.sqrt((x - mouseX) ** 2 + (y - mouseY) ** 2);
        return distance<=10
        }

        function onCanvasDblClick(e) {
        //console.log('dianji')
        
        var bbox = colorbarCanvas.getBoundingClientRect();
        const clickX = (e.clientX - colorbarCanvas.getBoundingClientRect().left)* (colorbarCanvas.width / bbox.width)
        const clickY = (e.clientY - colorbarCanvas.getBoundingClientRect().top)* (colorbarCanvas.height / bbox.height)
        
        for (let i = 0; i < colorControlPoints.length; i++) {
            if (isPointInsideCircle(clickX, clickY, colorControlPoints[i])) {
            colorControlPoints.splice(i, 1);
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
                colorbarContext.beginPath();
                const text = point.label; 
                colorbarContext.arc(x, y, 7, 0, Math.PI * 2);
                colorbarContext.fillStyle = 'white';
                colorbarContext.font = '5px Arial';
                colorbarContext.fillText(text, x - 4, y + 6 + 12); 
                colorbarContext.fill();
            }
        }
        drawColorbar();
        drawControlPoints();
        createLegend();
        let isDragging = false;
        let selectedControlPoint = null;
        colorbarCanvas.addEventListener('mousedown', (e) => {
            var bbox = colorbarCanvas.getBoundingClientRect();
            if(!this.checked){
            const mouseX = (e.clientX - colorbarCanvas.getBoundingClientRect().left)* (colorbarCanvas.width / bbox.width)
            const mouseY = (e.clientY - colorbarCanvas.getBoundingClientRect().top)* (colorbarCanvas.height / bbox.height)
            console.log('点击',mouseX,mouseY)
            for (const point of colorControlPoints) {
                const x = (point.value / 255) * colorbarWidth;
                const y = colorbarHeight / 2;
                const distance = Math.sqrt((x - mouseX) ** 2 + (y - mouseY) ** 2);
                if (distance <= 10) {
                    isDragging = true;
                    selectedControlPoint = point;
                    break;
                }
            }
        }
            else{
            const clickX = (e.clientX - colorbarCanvas.getBoundingClientRect().left)* (colorbarCanvas.width / bbox.width)
            const clickY = (e.clientY - colorbarCanvas.getBoundingClientRect().top)* (colorbarCanvas.height / bbox.height)
            


        
        if (clickY > colorbarHeight / 2 - 10 && clickY < colorbarHeight / 2 + 10) {

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
                
                radius: 7, 
                color: {r: r, g: g, b: b} 
            };

            
            if (value>0 && value<=255){
                colorControlPoints.push(newPoint)
            }
                
            
            
            
            context.clearRect(0, 0, canvas.width, canvas.height);
            drawColorbar()
            drawControlPoints();
            redrawDataVisualization(); 
        }

            }
        });

            colorbarCanvas.addEventListener('mousemove', (e) => {
                if (isDragging && selectedControlPoint) {
                    const mouseX = e.clientX - colorbarCanvas.getBoundingClientRect().left;
                    const newX = Math.min(Math.max(mouseX, 0), colorbarWidth);
                    selectedControlPoint.value = (newX / colorbarWidth) * 255;
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
        
        function redrawDataVisualization() {
            
            const colorData = mapDataToColor(data);

            
            var blockSize = canvas.width/(that.width)
            var blockSize1 = canvas.height/(that.height)
            context.clearRect(0, 0, canvas.width, canvas.height);

            for (let i = 0; i < that.height; i++) {
                for (let j = 0; j < that.width; j++) {
                    const color = colorData[i * that.width + j];
                    context.fillStyle = `rgb(${color.r}, ${color.g}, ${color.b})`;
                    context.fillRect(j*blockSize, i*blockSize1, blockSize, blockSize1);
                }
            }
        }

       
        function initVisualization() {
            
            drawData(data);
        }

        
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
        
        this.colormap = defaultColormaps[selectedColormap].split(', ').slice(1,-1)
        this.draw()
    }
    },
    defaultcolormap:function(){
        const defaultColormaps = {
            Rainbow: 'linear-gradient(to right, #8B00FF, #0000FF, #00FFFF, #008000, #FFFF00, #FF0000)',

            Viridis: 'linear-gradient(to right, #440154, #48186a, #472d7b, #424086, #3b528b, #33638d, #2c728e, #26828e, #21918e, #1e9e8e, #28ae8e, #3bbc8e, #51cc8f, #69db8f, #80ea8f, #98f999)',
            Plasma: 'linear-gradient(to right, #0d0887, #46039f, #7201a8, #9c179e, #bd3786, #d85763, #ed7953, #fca636, #f0f921)',
            Inferno: 'linear-gradient(to right, #000004, #160b39, #420a68, #6a176e, #932667, #bb3654, #dd513a, #f3771d, #fdb724)',
        };
        
        const colormapSelect = document.getElementById('colormapSelect');
        const selectedColormap = colormapSelect.value?colormapSelect.value:"Rainbow"
        this.colormap = defaultColormaps[selectedColormap].split(', ').slice(1,-1)
            for (const colormapName in defaultColormaps) {
        const option = document.createElement('option');
        option.value = colormapName;
        option.text = colormapName;
        colormapSelect.appendChild(option);
    }


colormapSelect.addEventListener('change', () => {
    const selectedColormap = colormapSelect.value;
    if (defaultColormaps[selectedColormap]) {
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
    border: 2px solid lightseagreen;
    border-radius: 10px;
    position:absolute;
    top:48%;
    left:.7%;
    width: 28%;
    height: 50%;
    background-color:'lightgrey';
}
.input-section {
  margin-top: 43px;
  gap: 10px; /* Add space between the textboxes */
  display: flex;
  position: absolute;
}
.input-field {
    max-width: 150px;
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
    top:3%;
    left:80%;
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
    top:90%;
    left:7%;
    
    z-index:101
}
#dataCanvas{
    position:absolute;
    left:120px; 
    top:100px;
    /* z-index:101; */
}
#canvas1{
    position:absolute;
    left:80px; 
    top:80px;
    width:60%
    
}
#file{
    position:absolute;
    top:3%;
    left:59%
}
#colormapSelect{
    position:absolute;
    left:10px; 
    top:2%;
    width:25%;
    height:8%;
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
    left:30%;
    z-index:101
}
#fileloader{
    position: absolute;
    top:2%;
    left:2%;
}
</style>
