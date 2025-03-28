<template>
    
    <div id="parameter">
        <t-space  id='check' direction="vertical">
            <t-cascader  v-model="value1" :options="options" placeholder='select compressor' multiple value-mode="parentFirst" />
            <t-cascader  v-model="value2" :options="options1" placeholder='select parameter' multiple value-mode="parentFirst" />
            
        </t-space>
        <t-button id="button" v-on:click="update">Redraw</t-button>
    </div>
</template>
<style scoped>
@import "@/assets/ParaMeter.css";
</style>
<script>
import { ref } from 'vue';
import * as d3 from 'd3';
// import parameters from '../../js/get_data.js'
import emitter from './eventBus.js';
export default {
    name:'ParaMeter',
    data(){
        return{     
            // selection for stat parameters
            options :[{
                            label: 'compressor',
                            value: 'compressor',
                            children: [
                                
                            ],
                        }],
            options1:[{
                                    label: 'stat_selection',
                                    value: 'stat_selection',
                                    children:[
                                    ]
            }],
            value1:ref([]),
            value2:ref([]),
            checked_c:'',
            redraw:false,
            //svg
            parameters:'',
            // alert
            msg:'',
            name:''
            }
    
    },
    mounted(){
        emitter.on('checkevent',(data)=>{
            console.log("data is:", data)
            this.name = data['checked_c']
            this.checked_c = data['checked_c']
            this.parameters = data['parameter']
            this.get_value()
        })
        
        
    },
    methods:{    
        get_value:function(){
              let name = this.name
                let temp = []
                name.forEach((i)=>{
                    temp.push({
                                label:i,
                                value:i,
                                })
                })
                this.options[0].children = temp
                temp = []
                
                // set_selection bounding for compressor's stat parameters
                let labels = new Set(this.parameters.map(i=>Object.keys(i))[0].slice(1).map(j=>j.split(':')[0]))
                // console.log(this.options)
                
                labels.forEach((item)=>{
                    temp.push({
                                            label:item,
                                            value:item,
                                            children:[]
                                            })
                })
                this.options1[0].children = temp
                
                    this.parameters.map(i=>Object.keys(i))[0].filter(item=>item!='compressor_id').forEach((item)=>{
                    let key = item.split(':')[0]
                    let value = item.split(':')[1]
                    let i = Array.from(labels).indexOf(key)
                    
                    this.options1[0].children[i].children.push({
                                                    label: value,
                                                    value: key+':'+value,

                                                    })
                    })

            console.log(this.parameters)

        },
        // click fucntion
        update:function(){

            let data = this.value1[0]=='compressor'?this.parameters:this.parameters.filter(item=>this.value1.indexOf(item['compressor_id'])!=-1)
            
            
            let data1 = this.value2=='stat_selection'?data:data.map((item)=>{
                let temp = {'compressor_id':item['compressor_id']}
                
                Object.keys(item).forEach((i)=>{
                    if(this.value2.indexOf(i.split(':')[0])!=-1) temp[i] = item[i]
                    if(this.value2.indexOf(i)!=-1) temp[i] = item[i]
                })
                return temp
                })
                
            if(data1.length==0){
                this.msg = this.$message.info({
                    content: 'No parameter is selected',
                    theme:"warning",
                    duration: 1000,
                    
                    zIndex: 1001,
                    
                    attach: document.body,
                });
            }
            else{
                d3.select('#SVG').selectAll('*').remove();    
            
                this.draw_parallel_c(data1)
            }
            
        },
        getRandomColor:function() {
                    const letters = '0123456789ABCDEF';
                    let color = '#';
                    for (let i = 0; i < 6; i++) {
                        color += letters[Math.floor(Math.random() * 16)];
                    }
                    return color;
            },

        generateUniqueColors:   function (n) {
                    const uniqueColors = new Set();
                    while (uniqueColors.size < n) {
                        const color = this.getRandomColor();
                        uniqueColors.add(color);
                    }
                    return Array.from(uniqueColors);
        },
        draw_parallel_c: function(data){
        //     // const that = this
        //     // if(data1.length==0) 
            
        //     let width = (window.innerWidth)/1.05;
        //     let height = (window.innerHeight)*0.6/1.05;
        //     let margin = 40;
        //     // console.log(document.getElementById('stat').clientHeight)

        //     let species = this.name
            
        //     let svg = d3.select("#SVG")
        //         .attr("width", width *1.05 )
        //         .attr("height", height*1.2);

            
        //     let group = svg.append("g");
        //     let legend = svg.append("g");

        //     let dimensions = data1.map((d)=>Object.keys(d))[0].slice(1);
            
            
        //     // console.log(data.map(d=>d['compressor_id']))
        //     // build colorscale
        //     let color = this.generateUniqueColors(this.name.length)
        //     let colorScale = d3.scaleOrdinal()
        //         .domain(this.name)
        //         .range(color);

        //     // build xaxis to help make yaxis
        //     let scaleX = d3.scalePoint()
        //         .domain(dimensions)
        //         .range([0.5*margin, width - 2*margin]);

        //     // build yscale for every dimension.
        //     let scaleY = {}
        //     // console.log(dimensions)
        //     dimensions.forEach(function (d) {
                
        //         const this_min = d3.min(data1.map(e => eval(e[d])))
        //         const this_max = d3.max(data1.map(e => eval(e[d])))
        //         // console.log(d,this_min,this_max)
        //         scaleY[d] = d3.scaleLinear()
        //             .domain([this_min, this_max])
        //             .range([height-0.5*margin,0])
        //     });

        //     // build a path generator
        //     let lineGenerator = d3.line();
        //     // console.log(scaleY["composite:compression_rate"].range())
        //     // draw the line
            
        //     group
        //         .append("g")
        //         .selectAll() // make path 
        //         .data(data1)
        //         .enter()
        //         .append("path")
        //         .attr("d", d => lineGenerator(  
        //             dimensions.map(function (p) { 
        //                 // if(d[p]>scaleY[p].domain()[1] || d[p]<scaleY[p].domain()[0]) console.log(p,(d[p]),scaleY[p].domain())
        //                 return [scaleX(p), scaleY[p](d[p])];
        //             })
        //         ))
        //         .attr("fill", "none")
        //         .attr("class", d => d['compressor_id']) // bound class
        //         .attr("stroke", d => colorScale(d['compressor_id']))
        //         .attr("stroke-width", 2)
        //         .attr("opacity",1)
        //         .on("mouseover", function () { // hightlight
        //             d3.select(this).attr('stroke-width', 5).attr('opacity', 1)
        //         })
        //         .on("mouseout", function () { 
        //             d3.select(this).transition().attr('stroke-width', 1.5).attr('opacity', .5)
        //         });

        //     let Ys = group
        //         .selectAll(".dimension")
        //         .data(dimensions)
        //         .enter()
        //         .append("g")
        //         .attr("class", (d,i)=>dimensions[i])
        //         .attr("transform", d => `translate(${scaleX(d)},0)`);
            
        //     // console.log(Ys)
            
        //     Ys.append("g")
        //         .each(function (d) {
        //             d3.select(this).call(d3.axisLeft(scaleY[d]).ticks(5).tickFormat(d=>eval(d).toExponential(2)))
        //     });

            
        //     Ys.append("text")
        //         .attr("x", -0.05 * width) 
        //         .attr("y", -0.05 * height)
        //         .attr('font-size', 10)
        //         .text(d => { 
        //             return d.split(':').length==1?d.split(':')[0]:d.split(':')[1]});

            
        //     Ys.selectAll("text")
        //         .clone(true)
        //         .lower()
        //         .attr("fill", "none")
        //         .attr("stroke-width", 5)
        //         .attr("stroke-linejoin", "round")
        //         .attr("stroke", "white");

            
        //     group.attr("transform", `translate(100, 80)`);


        //     // ******************** legend ********************

        //     let flag = { 'sz': true, 'zfp': true };

            
        //     // 
        //     // console.log(species[0])
        //     legend.selectAll(".circles")
        //         .data(species)
        //         .enter()
        //         .append("circle")
        //         .attr("fill", d => colorScale(d))
        //         .attr('cx', 10)
        //         .attr('cy', (d, i) => i * 25 + 30)
        //         .attr('r', 8)
        //         .on("mouseover", function () { // 突出显示鼠标滑过的图标
        //             d3.select(this).transition().attr('r', 12)
        //         })
        //         .on("mouseout", function () { // 还原
        //             d3.select(this).transition().attr('r', 8)
        //         })
        //         .on("click", function (event, d) { 
        //             // console.log(d)
        //             // console.log(d3.select(this))// 
        //             if (flag[d]) { // 
        //                 d3.select(this).attr('fill', 'lightgrey') // 
        //                 d3.selectAll(`.${d}`).attr('stroke', 'lightgrey') // 
        //                 flag[d] = !flag[d] // 
        //             }
        //             else { // 
        //                 d3.select(this).attr('fill', e => colorScale(e))
        //                 d3.selectAll(`.${d}`).attr('stroke', e => colorScale(e['compressor_id']))
        //                 flag[d] = !flag[d]
        //             }
        //         });

        //     // 
        //     legend.selectAll(".texts")
        //         .data(species)
        //         .enter()
        //         .append("text")
        //         .attr('x', 30)
        //         .attr('y', (d, i) => i * 25 + 35)
        //         .text(d => d);

        //     // 
        //     legend.attr('transform', `translate(5,20)`);
        // }
        function generateUniqueColors(n) {
                let color = []
                
                const lent = d3.schemeSet2.length
                for(let i =0;i<n;i++){
                    
                    color.push(d3.schemeSet3[i%lent])
                }
                return color
            }
            // this.compare_mode = !this.compare_mode
            // let tem = document.getElementById('temp').innerHTML
            // this.checked_c = document.getElementById('temp').innerHTML.split(',')
            
            
            let data1 = data.filter(item=>this.checked_c.includes(item.compressor_id))
            
            let width = (document.getElementById('stat').clientWidth*0.6)
            let height = (document.getElementById('stat').clientHeight*0.6)
            let margin = 40;
            const svg  = d3.select("#SVG")
                
            
            // console.log(document.getElementById('stat').clientHeight)

            let species = this.checked_c;
            let group = svg.append("g");
            let legend = svg.append("g");

            let dimensions = Object.keys(data1[0]).filter(item=>item!='compressor_id' && typeof(data1[0][item])!='string' && data1[0][item]!=null)
            
            
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
                        console.log([scaleX(p), scaleY[p](d[p])])
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
            console.log('-----',this.checked_c)
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
        }
    },
    
}
</script>
