<template>
    <!-- <div id="chart" style="height:100%;width:100%"></div> -->
    <t-button id="compressor" v-on:click="update">cmp_compare</t-button>
    <div id="stat">
        
    </div>
    <p id="temp" ></p>

</template>
  
  <script>
  import * as d3 from 'd3' 
  import * as echarts from 'echarts'
  import parameters from '../../js/get_data.js'
  export default {
    name:'StatA',
    data(){
        return{
            doubleclick:{},
            name:'',
            stats:'',
            parameters:parameters,
            svg:'',
            checked_c:[],
            compare_mode:false,
            option:{
                tooltip: {
                    trigger: 'axis',
                    axisPointer: {            // 坐标轴指示器，坐标轴触发有效
                        type: 'shadow'        // 默认为直线，可选为：'line' | 'shadow'
                    },
                    label: {
                        show: true,
                        backgroundColor: '#fff',
                        color: 'red',
                        borderColor: 'rgba(0,0,0,0)',
                        shadowColor: 'rgba(0,0,0,0)',
                        shadowOffsetY: 0,
                    },
                    // formatter: function (params, ticket, callback) {
                    // var htmlStr = '';
                    // for(var i=0;i<params.length;i++){
                    //     var param = params[i];
                    //     var xName = param.name;//x轴的名称
                    //     var seriesName = param.seriesName;//图例名称
                    //     var value = param.value;//y轴值
                    //     var color = param.color;//图例颜色
                    //                 if(i===0){
                    //                 htmlStr += xName + '<br/>';//x轴的名称
                    //                 }
                    //                 htmlStr +='<div>';
                    //                 // 具体显示的数据【字段名称：seriesName，值：value】
                    //                 // 这里判断一下name，如果是我们需要特殊处理的，就处理
                    //                 if(seriesName === '联盟广告'){
                    //                     // 前面一条线，后面一条线【具体样式自己写】
                    //                     htmlStr += '<div style="border: 1px solid #FFEB3B"></div>';
                    //                     htmlStr += 'xxxx联盟广告：' + value +'单位（%）';
                    //                     htmlStr += '<div style="border: 1px solid #FFEB3B"></div>';
                    //                 }else{
                    //                     // 正常显示的数据，走默认
                    //                     htmlStr += '<span style="margin-right:5px;display:inline-block;width:10px;height:10px;border-radius:5px;background-color:'+color+';"></span>';
                    //                     htmlStr += seriesName + '：' + value + 'W';
                    //                 }
                                    
                    //                 htmlStr += '</div>';
                    //             }
                    //             return htmlStr;
                    //             }
                },
                title: {
                    // text: '广东省每日确诊和累计出院人数变化趋势',
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
                // angleAxis: {
                //     type: 'category',
                //     data: ''
                // },
                // radiusAxis: {},
                // polar: {},
                
                series: '',
                legend: {
                    show: true,
                    data: '',
                    selected:''
                }
            },
            myChart:''
        }
        
        
    },
    mounted() {
        
        // this.get_data()
        
        setTimeout(()=>{
            this.draw_levels()
            // this.draw_parallel_c(this.parameters)
        },1000)
        
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
            // parameters.forEach((item,i)=>{
            //     let index
            //     index =  parseInt(i/2)
            //     console.log(index)
            //     item.compressor_id+='_'+String(index)
            // })
            this.name = Array.from(new Set(parameters.map(item=>item['compressor_id']))).map((item)=>{
                return {
                    value:item,
                    textStyle : {
                                    color: 'black'
                                }
                }
            })
            this.option.xAxis[0].data = this.name
            // this.option.angleAxis.data = parameters.map(item=>Object.keys(item))[0].filter(d=>d!='compressor_id').map(d=>d.split(':')[1])
            let series = []
            
            that.stats = parameters.map(item=>Object.keys(item))[0].filter(d=>d!='compressor_id').map(d=>d.split(':')[1])
            
            console.log(that.stats)
            let selected = {}
            
            
            
            that.stats.forEach((item,i)=>{
                // console.log(Object.keys(parameters[0]))
                // console.log(parameters.map((j)=>j[Object.keys(parameters[0])[i+1]]),)
                // console.log(Object.values(parameters[0]).filter((item,j)=>Object.keys(parameters[0])[j]!='compressor_id'))
                const u = normalize(parameters.map((j)=>j[Object.keys(parameters[0])[i+1]]).map(item=>parseFloat(item)))
                // console.log('v',parameters.map((j)=>j[Object.keys(parameters[0])[i+1]]).map(item=>parseFloat(item)))
                if(!u.includes(NaN)){

                this.doubleclick[item] = 0
                
                let obj = 
                    {
                    type: 'bar',
                    data: u,
                    stack: that.name[i],
                    barWidth:String((1/u.length)*100)/3+'%',
                    
                    barCategoryGap:'50%',
                    name: item,
                    itemStyle: {
							normal: {
								label: {
									show: true, //开启显示
									position: 'top', //在上方显示
									textStyle: { //数值样式
										color: 'black',
										fontSize: 2
									}
								}
							}}
                    // stack: 'a',
                    // emphasis: {
                    //     focus: 'series'
                    // }
                    }
                series.push(obj)
                selected.item=false
                }
            })
            this.option.series = series
            this.option.legend.selected = selected
            // const that = this
            // let width = (window.innerWidth*0.7)/1.05;
            // let height = (window.innerHeight)*0.6/1.05;
            
            
            var chartDom = document.getElementById('stat');
            let myChart = echarts.init(chartDom);
            var option = that.option
            option && myChart.setOption(option);
            that.myChart = myChart
            myChart.on("click",function(params){
                
                // that.draw_parallel_c(that.parameters)
                if(params.componentType =="xAxis" || params.componentType =="yAxis"){
                    if(that.checked_c.includes(params.value)){
                        that.checked_c = that.checked_c.filter(item=>item!=params.value)
                    }
                    else{
                        that.checked_c.push(params.value)
                    }
                    // console.log(that.checked_c)
                    // const yAxisName = params.value
                    // const yAxisItem = {
                    // value: yAxisName,
                    // textStyle: {
                    //     color: '#00ff7f'
                    // }
                    // }

                    // const index = name.findIndex(item => {
                    //     return that.checked_c.includes(item)
                    // })
                    // console.log(index)
                    that.name.forEach((item,i)=>{
                        // console.log(item)
                        if(that.checked_c.includes(item.value)){
                            that.name[i].textStyle.color =
                                    '#00ff7f'
                                
                        }
                        else{
                            that.name[i].textStyle.color =
                                    'black'
                        }
                    })
                    // that.checked_c.forEach((q)=>{
                    //     // console.log(q)
                    //     name[q].textStyle = {
                    //     color: '#00ff7f'
                    // }
                    // })
                    // name.splice(index, 1, yAxisItem)
                    // console.log(that.name)
                    option.xAxis.data = JSON.parse(JSON.stringify(that.name))
                    myChart.setOption(option)

                    
                    // console.log(option.xAxis[0].textStyle.color)
                }
            })
            console.log(myChart.options.tooltip)
            myChart.on('legendselectchanged', function(params) {
                
                let option = this.getOption();
                let select_key = Object.keys(params.selected);
                let select_value = Object.values(params.selected)
                
                
                select_value.forEach((item,i)=>{
                    if(params.name==select_key[i]){
                        // let n = that.stats.indexOf(params.name)
                        option.legend[0].selected[select_key[i]] = !that.doubleclick[select_key[i]]
                        that.doubleclick[select_key[i]] = !that.doubleclick[select_key[i]]
                        
                        // option.series[n].barWidth='5%'
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
                // else{
                //     // const m = temp.filter(item=>item==true).length
                //     const length = '5%'
                //     temp.forEach((item,i)=>{
                //         if(item){
                //             option.series[i].barWidth=length
                //         }
                        
                //     })
                // }
                this.setOption(option)
                
                myChart.setOption(option,true);
        })
        
            
            
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
            // this.compare_mode = !this.compare_mode
            
            let data1 = data.filter(item=>this.checked_c.includes(item.compressor_id))
            // console.log(data1)
            const svg = this.svg
            let width = (window.innerWidth)/1.05;
            let height = (window.innerHeight)*0.6/1.05;
            let margin = 40;
            // console.log(document.getElementById('stat').clientHeight)

            let species = this.checked_c;
            let group = svg.append("g");
            let legend = svg.append("g");

            let dimensions = Object.keys(data1[0]).slice(1);
            
            
            // console.log(data.map(d=>d['compressor_id']))
            // build colorscale
            
            let color = generateUniqueColors(this.checked_c.length)
            // console.log(document.getElementById('temp').innerHTML)
            // document.getElementById('temp').innerHTML = String(this.checked_c)
            console.log('n',color)
            let colorScale = d3.scaleOrdinal()
                .domain(this.checked_c)
                .range(color);

            // build xaxis to help make yaxis
            let scaleX = d3.scalePoint()
                .domain(dimensions)
                .range([0, width - 0.5*margin]);

            // build yscale for every dimension.
            let scaleY = {}
            
            dimensions.forEach(function (d) {
                // console.log(data1.map(e => eval(e[d])))
                scaleY[d] = d3.scaleLinear()
                    .domain([d3.min(data1.map(e => eval(e[d]))), d3.max(data1.map(e => eval(e[d])))])
                    .range([height-0.5*margin,0])
            });

            // build a path generator
            let lineGenerator = d3.line();

            // draw the line
            group
                .append("g")
                .selectAll() // make path 
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
                .attr("x", -0.05 * width) 
                .attr("y", -0.05 * height)
                .attr('font-size', 10)
                .text(d => { 
                    return d.split(':').length==1?d.split(':')[0]:d.split(':')[1]});

            
            Ys.selectAll("text")
                .clone(true)
                .lower()
                .attr("fill", "none")
                .attr("stroke-width", 5)
                .attr("stroke-linejoin", "round")
                .attr("stroke", "white");

            
            group.attr("transform", `translate(100, 80)`);


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

            // 
            legend.attr('transform', `translate(5,20)`);
        },
        update:function(){

            this.compare_mode = !this.compare_mode
            if(this.compare_mode){
                
                document.getElementById('temp').innerHTML = String(this.checked_c)
                document.getElementById('compressor').innerHTML='all_compressors'
                let width = (window.innerWidth)/1.05;
                let height = (window.innerHeight)*0.6/1.05;
                this.myChart.dispose()
                this.myChart = null
                
                this.svg = d3.select("#stat").append('svg').attr('id','SVG')
                .attr("width", width )
                .attr("height", height*1.2);

                this.draw_parallel_c(this.parameters)
            }
            else{
                document.getElementById('compressor').innerHTML='compressor_compare'
                const that = this
                // this.checked_c = []
                var chartDom = document.getElementById('stat');
                let myChart = echarts.init(chartDom);
                myChart.resize({
                    width: 70,
                    height: 400
                });


                var option = that.option
                option && myChart.setOption(option);
                that.myChart = myChart
                // that.myChart.width=70
                myChart.on("click",function(params){
                
                // that.draw_parallel_c(that.parameters)
                if(params.componentType =="xAxis" || params.componentType =="yAxis"){
                    if(that.checked_c.includes(params.value)){
                        that.checked_c = that.checked_c.filter(item=>item!=params.value)
                    }
                    else{
                        that.checked_c.push(params.value)
                    }
                    
                    that.name.forEach((item,i)=>{
                        // console.log(item)
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
                        // let n = that.stats.indexOf(params.name)
                        option.legend[0].selected[select_key[i]] = !that.doubleclick[select_key[i]]
                        that.doubleclick[select_key[i]] = !that.doubleclick[select_key[i]]
                        // option.series[n].barWidth=20
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
  
  <!-- Add "scoped" attribute to limit CSS to this component only -->
  <style scoped>
#stat{
      border:2px solid #a7b2ac;
      border-radius: 4px;
      position:absolute;
      top:28%;
      left:29.3%;
      width: 70%;
      height: 70%;
      background-color: #cccecebb
};
#chart{
    position:absolute;
    top:28%;
    left:29.3%;
    width: 70%;
    height: 70%;
    background-color:'grey'
}


/* #data_selection{
    border:2px solid #a7b2ac;
    border-radius: 4px;
    position:absolute;
    top:1%;
    left:.7%;
    width: 28%;
    height: 26%;
}

#parameter{
    border:2px solid #a7b2ac;
    border-radius: 4px;
    position:absolute;
    top:1%;
    left:29.3%;
    width: 70%;
    height: 26%;
}

#data_vis{
    border:2px solid #a7b2ac;
    border-radius: 4px;
    position:absolute;
    top:28%;
    left:.7%;
    width: 28%;
    height: 70%;
} */
#compressor{
    z-index:101;
    position:absolute;
    top:40%;
    left:92%;
    background-color:'lightgrey'
}
#temp{
    display:none
}
  </style>

