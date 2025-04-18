// // const { defineConfig } = require('@vue/cli-service')
// // module.exports = defineConfig({
// //   transpileDependencies: true,
// // 	devServer: {
// // 		host:'0.0.0.0',
// // 		port:8081
// // 	}
// // })



const { defineConfig } = require('@vue/cli-service')
module.exports = defineConfig({
  transpileDependencies: ["@kitware/vtk.js"],
  chainWebpack: config => {
    config.module
      .rule('glsl')
      .test(/\.(glsl|vs|fs)$/)
      .use('raw-loader')
      .loader('raw-loader')
      .end();
  }
})
