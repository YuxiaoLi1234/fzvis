<template>
    <t-button id="compressor" v-on:click="update">cmp_compare</t-button>
    <t-button id="getvis" v-on:click="draw">draw</t-button>
    <div id="stat">
    </div>
    <p id="temp" ></p>
</template>
<style scoped>
@import "@/assets/StatA.css";
</style>
<script>
import * as d3 from 'd3' 
import * as echarts from 'echarts'

import emitter from './eventBus';
export default {
name:'StatA',
data(){
    return{
        doubleclick:{},
        name:'',
        stats:'',
        compare_data:'',
        parameters:'',
        parameters_copy:'',
        svg:'',
        checked_c:[],
        compare_mode:false,
        option:{
            tooltip: {
                trigger: 'axis',
                axisPointer: {            
                    type: 'shadow'        
                },
                label: {
                    show: true,
                    backgroundColor: '#fff',
                    color: 'red',
                    borderColor: 'rgba(0,0,0,0)',
                    shadowColor: 'rgba(0,0,0,0)',
                    shadowOffsetY: 0,
                },
                formatter: function (params) {
                var htmlStr = '';
                for(var i=0;i<params.length;i++){
                    var param = params[i];
                    var xName = param.name;//x轴的名称
                    var seriesName = param.seriesName;//图例名称
                    var value = param.value;//y轴值
                    var color = param.color;//图例颜色
                                if(i===0){
                                htmlStr += xName + '<br/>';//x轴的名称
                                }
                                htmlStr +='<div>';
                                if(seriesName === '联盟广告'){
                                    htmlStr += '<div style="border: 1px solid #FFEB3B"></div>';
                                    htmlStr += 'xxxx联盟广告：' + value +'单位（%）';
                                    htmlStr += '<div style="border: 1px solid #FFEB3B"></div>';
                                }else{
                                    htmlStr += '<span style="margin-right:5px;display:inline-block;width:10px;height:10px;border-radius:5px;background-color:'+color+';"></span>';
                                    htmlStr += seriesName + '：' + value + 'W';
                                }
                                
                                htmlStr += '</div>';
                            }
                            return htmlStr;
                            }
            },
            title: {
                top:20,
                left: 'center',
                textStyle:{
                    fontSize: 25
                }
            },
            grid: {
                left: '3%',
                right: '4%',
                bottom: '3%',
                containLabel: true
            },
            xAxis: [
                {
                    type: 'category',
                    triggerEvent: true,
                    axisLabel:{'interval':0},
                    data: '',
                    textStyle: {
                        color: function (value) {
                        return this.checked_c != [] && this.checked_c.includes(value)
                            ? "red"
                            : "black";
                        },
                    },
                    axisPointer: {
                        label: {
                            width: '100%',
                        }
                    }
                }
            ],
            yAxis: [
                {
                    type: 'value'
                }
            ],
            series: '',
            legend: {
                show: true,
                data: '',
                selected:''
            }
        },
        myChart:null
    } 
},
mounted() {
    emitter.on('myEvent', (data) => {
        console.log("data is:", data)
        this.name = data['compressor_id'].map((item)=>{
            return {
            value:item,
            textStyle : {
                            color: 'black'
                        }
        }
        })
        const size = data['compressor_id'].length
        const temp = []
        for(let i =0;i<size;i++){
            data['metrics'][i]['compressor_id'] = data['compressor_id'][i]
            temp.push(data['metrics'][i])
        }
        this.parameters = temp
        if(!this.myChart == null) {
            this.myChart.dispose()
            this.myChart = null
        }
    }); 
},
computed: {
},
methods:{
    
    draw_levels:function(){
        
        function normalize(data) {
            const max = Math.max(...data);
            const min = Math.min(...data);
            
            return min==max?data.map((d)=>0.5*d/d):data.map(value => (value - min) / (max - min))
        }
        const that = this
        const parameters = this.parameters
        this.name = Array.from(new Set(parameters.map(item=>item['compressor_id']))).map((item)=>{
            return {
                value:item,
                textStyle : {
                                color: 'black'
                            }
            }
        })
        this.option.xAxis[0].data = this.name
        let series = []
        
        that.stats = parameters.map(item=>Object.keys(item))[0].filter(d=>d!='compressor_id').map(d=>d.split(':')[1])
        

        let selected = {}
        let record = {}
        this.name.forEach((i)=>{
            record[i.value] = []
        })
        that.stats.forEach((item,i)=>{
            const u = normalize(parameters.filter(item=>Object.keys(item)!='compressor_id').map((j)=>j[Object.keys(parameters[0])[i]]).map(item=>parseFloat(item)))
            if(!u.includes(NaN)){
            this.doubleclick[item] = 0
            let obj = 
                {
                type: 'bar',
                data: u,
                stack: that.name[i],
                barWidth:1,
                
                barCategoryGap:'50%',
                name: item,
                itemStyle: {
                        normal: {
                            label: {
                                show: true, 
                                position: 'top', 
                                textStyle: { 
                                    color: 'black',
                                    fontSize: 2
                                }
                            }
                        }}
                }
            series.push(obj)
            selected.item=false
            }
        })
        this.option.series = series
        const va =series.map(d=>d.name)
        this.parameters.forEach((item)=>{
            const value = []
            Object.keys(item).forEach((q)=>{
                
                if(va.includes(q.split(':')[1])){
                    value.push(item[q])
                }
            })
            record[item['compressor_id']] = value
            
        })

        this.option.legend.selected = selected       
        this.option.tooltip.formatter = function (params) {
                var htmlStr = '';
                for(var i=0;i<params.length;i++){
                    
                    var param = params[i];
                    
                    var xName = param.name;
                    var seriesName = param.seriesName;
                    var value = record[param.name][i];
                    var color = param.color;
                    if(i===0){
                    htmlStr += xName + '<br/>';
                    }
                    htmlStr +='<div>';
                    if(seriesName === '联盟广告'){
                        htmlStr += '<div style="border: 1px solid #FFEB3B"></div>';
                        htmlStr += 'xxxx联盟广告：' + value +'单位（%）';
                        htmlStr += '<div style="border: 1px solid #FFEB3B"></div>';
                    }else{
                        htmlStr += '<span style="margin-right:5px;display:inline-block;width:10px;height:10px;border-radius:5px;background-color:'+color+';"></span>';
                        htmlStr += seriesName + ':' + value;
                    }
                    
                    htmlStr += '</div>';
                }
                return htmlStr;
                }

        var chartDom = document.getElementById('stat');
        echarts.init(document.getElementById('stat')).dispose(); 
        let myChart = echarts.init(chartDom);
        var option = that.option
        option && myChart.setOption(option);
        that.myChart = myChart
        myChart.on("click",function(params){
            
            // that.draw_parallel_c(that.parameters)
            if(params.componentType =="xAxis" || params.componentType =="yAxis"){
                if(!that.checked_c.includes(params.value)){
                    that.checked_c.push(params.value)
                    
                }
                else{
                    that.checked_c = that.checked_c.filter(item=>item!=params.value)
                }
                console.log(that.checked_c,that.name)
                that.name.forEach((item,i)=>{
                    if(that.checked_c.includes(item.value)){
                        that.name[i].textStyle.color =
                                '#00ff7f'
                            
                    }
                    else{
                        that.name[i].textStyle.color =
                                'black'
                    }
                })
                option.xAxis.data = JSON.parse(JSON.stringify(that.name))
                myChart.setOption(option)
            }
        })
        myChart.on('legendselectchanged', function(params) {
            
            let option = this.getOption();
            let select_key = Object.keys(params.selected);
            let select_value = Object.values(params.selected)
            
            
            select_value.forEach((item,i)=>{
                if(params.name==select_key[i]){
                    option.legend[0].selected[select_key[i]] = !that.doubleclick[select_key[i]]
                    that.doubleclick[select_key[i]] = !that.doubleclick[select_key[i]]
                }
                else{
                    option.legend[0].selected[select_key[i]] = that.doubleclick[select_key[i]]
                }
            })
            let temp = Object.values(that.doubleclick)
            if(!temp.includes(true)){
                Object.values(that.doubleclick).forEach((item,i)=>{
                    option.legend[0].selected[select_key[i]] = true
                    option.series[i].barWidth=1
                })
            }
            this.setOption(option)
            
            myChart.setOption(option,true);
    })
    
        
        
    },
    draw:function(){
        this.checked_c = []
        if(!this.myChart == null) {
            echarts.init(document.getElementById('stat')).dispose(); 
            this.myChart.dispose()
            this.myChart = null
        }
        this.draw_levels()
    },
    draw_parallel_c: function(data){
        

        function generateUniqueColors(n) {
            let color = []
            
            const lent = d3.schemeSet2.length
            for(let i =0;i<n;i++){
                
                color.push(d3.schemeSet3[i%lent])
            }
            return color
        }
        let data1 = data.filter(item=>this.checked_c.includes(item.compressor_id))

        const svg = this.svg
        let width = (document.getElementById('stat').clientWidth*0.8)
        let height = (document.getElementById('stat').clientHeight*0.8)
        let margin = 40;
        let species = this.checked_c;
        let group = svg.append("g");
        let legend = svg.append("g");
        let dimensions = Object.keys(data1[0]).filter(item=>item!='compressor_id' && typeof(data1[0][item])!='string' && data1[0][item]!=null)
        let color = generateUniqueColors(this.checked_c.length)
        let colorScale = d3.scaleOrdinal()
            .domain(this.checked_c)
            .range(color);
        let scaleX = d3.scalePoint()
            .domain(dimensions)
            .range([- 0.5*margin, width - 0.5*margin]);
        let scaleY = {}
        
        dimensions.forEach(function (d) {
            if(typeof(data1.map(e => e[d])[0])!='string'){
                scaleY[d] = d3.scaleLinear()
                .domain([d3.min(data1.map(e => eval(e[d]))), d3.max(data1.map(e => eval(e[d])))])
                .range([height-0.5*margin,0.5*margin])
            }
            
        });
        let lineGenerator = d3.line();
        group
            .append("g")
            .selectAll() 
            .data(data1)
            .enter()
            .append("path")
            .attr("d", d => lineGenerator(  
                dimensions.map(function (p) { 
                    return [scaleX(p), scaleY[p](d[p])];
                })
            ))
            .attr("fill", "none")
            .attr("class", d => d['compressor_id']) // bound class
            .attr("stroke", d => colorScale(d['compressor_id']))
            .attr("stroke-width", 2)
            .attr("opacity",1)
            .on("mouseover", function () { // hightlight
                d3.select(this).attr('stroke-width', 5).attr('opacity', 1)
            })
            .on("mouseout", function () { 
                d3.select(this).transition().attr('stroke-width', 1.5).attr('opacity', .5)
            });
        
        let Ys = group
            .selectAll(".dimension")
            .data(dimensions)
            .enter()
            .append('g')
            .attr("class", '1')
            .attr("transform", d => `translate(${scaleX(d)},0)`);
        
        
        
        Ys.append("g")
            .each(function (d) {
                d3.select(this).call(d3.axisLeft(scaleY[d]).ticks(5).tickFormat(d=>eval(d).toExponential()))
        });

        
        Ys.append("text")
            .attr("x", 0.05*width) 
            .attr("y", 0)
            .attr('font-size', 10)
            .text(d => { 
                return d.split(':').length==1?d.split(':')[0]:d.split(':')[1]})
            

        
        Ys.selectAll("text")
            .clone(true)
            .lower()
            .attr("fill", "none")
            .attr("stroke-width", 5)
            .attr("stroke-linejoin", "round")
            .attr("stroke", "white");

            
        
        
        group.attr("transform", `translate(100, 10)`);

        // ******************** legend ********************

        let flag = {  };
        this.checked_c.forEach((item)=>{
            flag[item] = true
        })

        
        // 
        // console.log(species[0])
        legend.selectAll(".circles")
            .data(species)
            .enter()
            .append("circle")
            .attr("fill", d => colorScale(d))
            .attr('cx', 10)
            .attr('cy', (d, i) => i * 25 + 30)
            .attr('r', 8)
            .on("mouseover", function () { // 突出显示鼠标滑过的图标
                d3.select(this).transition().attr('r', 12)
            })
            .on("mouseout", function () { // 还原
                d3.select(this).transition().attr('r', 8)
            })
            .on("click", function (event, d) { 
                // console.log(d)
                // console.log(d3.select(this))// 
                if (flag[d]) { // 
                    d3.select(this).attr('fill', 'lightgrey') // 
                    d3.selectAll(`.${d}`).attr('stroke', 'lightgrey') // 
                    flag[d] = !flag[d] // 
                }
                else { // 
                    d3.select(this).attr('fill', e => colorScale(e))
                    d3.selectAll(`.${d}`).attr('stroke', e => colorScale(e['compressor_id']))
                    flag[d] = !flag[d]
                }
            });

        // 

        legend.selectAll(".texts")
            .data(species)
            .enter()
            .append("text")
            
            .attr('x', 30)
            .attr('y', (d, i) => i * 25 + 35)
            
            .text(d => d);
        this.svg.attr("transform", `translate(20, 50)`);
        // 
        
        
        
    },
    update:function(){

        this.compare_mode = !this.compare_mode
        if(this.compare_mode){
            
            document.getElementById('temp').innerHTML = String(this.checked_c)
            emitter.emit('checkevent', {'checked_c':this.checked_c,'parameter':this.parameters});

            document.getElementById('compressor').innerHTML='all_compressors'
            
            let width = (document.getElementById('stat').clientWidth*0.9)
            let height = (document.getElementById('stat').clientHeight*0.8)
            this.myChart.dispose()
            this.myChart = null
            
            this.svg = d3.select("#stat").append('svg').attr('id','SVG')
            .attr("width", width )
            .attr("height", height);

            this.draw_parallel_c(this.parameters)
        }
        else{
            document.getElementById('compressor').innerHTML='compressor_compare'
            const that = this
            
            var chartDom = document.getElementById('stat');
            echarts.init(document.getElementById('stat')).dispose(); 
            let myChart = echarts.init(chartDom);

            var option = that.option
            option && myChart.setOption(option);
            that.myChart = myChart;

            myChart.on("click",function(params){
            
            if(params.componentType =="xAxis" || params.componentType =="yAxis"){
                if(!that.checked_c.includes(params.value)){
                    that.checked_c.push(params.value)
                }
                else{
                    that.checked_c = that.checked_c.filter(item=>item!=params.value)
                }
                console.log(that.checked_c)
                console.log(that.name)
                that.name.forEach((item,i)=>{
                    if(that.checked_c.includes(item.value)){
                        that.name[i].textStyle.color = '#00ff7f' 
                    }
                    else{
                        that.name[i].textStyle.color = 'black'
                    }
                })
                option.xAxis.data = JSON.parse(JSON.stringify(that.name))
                myChart.setOption(option)
            }
        })
        myChart.on('legendselectchanged', function(params) {
            let option = this.getOption();
            let select_key = Object.keys(params.selected);
            let select_value = Object.values(params.selected)
            select_value.forEach((item,i)=>{
                if(params.name==select_key[i]){
                    option.legend[0].selected[select_key[i]] = !that.doubleclick[select_key[i]]
                    that.doubleclick[select_key[i]] = !that.doubleclick[select_key[i]]
                }
                else{
                    option.legend[0].selected[select_key[i]] = that.doubleclick[select_key[i]]
                }
            })
            let temp = Object.values(that.doubleclick)
            if(!temp.includes(true)){
                Object.values(that.doubleclick).forEach((item,i)=>{
                    option.legend[0].selected[select_key[i]] = true
                    option.series[i].barWidth=1
                })
            }
            this.setOption(option)
            myChart.setOption(option,true);
    })
        }
    }
},

}
</script>

