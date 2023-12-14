import * as d3 from 'd3'
let parameters
async function data() {
    return d3.csv("./data/result.csv").then((d)=>{
        parameters = d
        parameters.forEach((item,i)=>{
          let index
          index =  parseInt(i/2)
          console.log(index)
          item.compressor_id+='_'+String(index)
      })
        console.log(parameters)
    })
  }
await data()
console.log('d',parameters)
// setTimeout(() => {
//     console.log(parameters)
    
// }, 1000)

export default parameters