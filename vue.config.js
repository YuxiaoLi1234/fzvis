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
  transpileDependencies: true,
  devServer: {
    host: '0.0.0.0',
    allowedHosts: 'all',
    port: 10001,
    proxy: {
      '/api': {
        target: 'http://localhost:10080',
        changeOrigin: true,
        ws: true
      }
    }
  }
});
