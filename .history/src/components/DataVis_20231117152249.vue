<template>
    <div id="data_vis">
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
  
import '@kitware/vtk.js/favicon';


import '@kitware/vtk.js/Rendering/Profiles/Geometry';

import vtkFullScreenRenderWindow from '@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow';

// import vtkActor           from '@kitware/vtk.js/Rendering/Core/Actor';
// import vtkMapper          from '@kitware/vtk.js/Rendering/Core/Mapper';
// import vtkConeSource      from '@kitware/vtk.js/Filters/Sources/ConeSource';
// Load the rendering pieces we want to use (for both WebGL and WebGPU)
import '@kitware/vtk.js/Rendering/Profiles/Geometry';
import vtkVolume from '@kitware/vtk.js/Rendering/Core/Volume';
import vtkVolumeMapper from '@kitware/vtk.js/Rendering/Core/VolumeMapper';
import vtkColorTransferFunction from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction';
import vtkDataArray from '@kitware/vtk.js/Common/Core/DataArray'
// import vtkPlaneSource from '@kitware/vtk.js/Filters/Sources/PlaneSource';


// import vtkColorMaps from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction/ColorMaps';
// import vtkColorTransferFunction from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction';

// import vtkTexture from '@kitware/vtk.js/Rendering/Core/Texture';
// import vtkRTAnalyticSource from '@kitware/vtk.js/Filters/Sources/RTAnalyticSource';
// import vtkImageSliceFilter from '@kitware/vtk.js/Filters/General/ImageSliceFilter';
// import vtkScalarToRGBA from '@kitware/vtk.js/Filters/General/ScalarToRGBA';
import vtkImageData from '@kitware/vtk.js/Common/DataModel/ImageData'
// import vtkPlaneSource from '@kitware/vtk.js/Filters/Sources/PlaneSource';
import vtkPiecewiseFunction from '@kitware/vtk.js/Common/DataModel/PiecewiseFunction';

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
    // this.colormap()
  },
  methods:{
    data_vis:function(){

        
        const that = this
        d3.json('./data/inputdata.json').then((d)=>{
            that.input_data = d[23].reduce(function (a, b) { 
    return a.concat(b)
});
            that.colormap()
        })

        
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
    colormap:function(){
    const fullScreenRenderWindow = vtkFullScreenRenderWindow.newInstance(
        {background: [.5, .5, .5],
            rootContainer:document.getElementById('data_vis'),
            containerStyle: {'width':'70%','height':"70%"}
        }
    );
    const renderer = fullScreenRenderWindow.getRenderer();
    const renderWindow = fullScreenRenderWindow.getRenderWindow();

    const dimensions = [100, 100, 1];
    const imageData = vtkImageData.newInstance();
    imageData.setDimensions(...dimensions);

// 假设dataArray是您的100x100二维数组
    const dataArray = [...this.input_data]// Your 100x100 array data
    const scalars = vtkDataArray.newInstance({
        numberOfComponents: 1,
        values: Float32Array.from(dataArray.flat()),
    });
    imageData.getPointData().setScalars(scalars);
    const colorTransferFunction = vtkColorTransferFunction.newInstance();
const opacityFunction = vtkPiecewiseFunction.newInstance();

// 配置初始颜色和不透明度
// 这里需要根据您的数据范围和视觉需求来调整
colorTransferFunction.addRGBPoint(0, 0, 0, 1); // 蓝色
colorTransferFunction.addRGBPoint(1, 1, 0, 0); // 红色

opacityFunction.addPoint(0, 0.0);
opacityFunction.addPoint(1, 1.0);
const volumeMapper = vtkVolumeMapper.newInstance();
volumeMapper.setInputData(imageData);

const volume = vtkVolume.newInstance();
volume.setMapper(volumeMapper);
volume.getProperty().setRGBTransferFunction(0, colorTransferFunction);
volume.getProperty().setScalarOpacity(0, opacityFunction);

renderer.addVolume(volume);
renderer.resetCamera();
renderWindow.render();

}}
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