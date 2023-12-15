const { defineConfig } = require('@vue/cli-service')
module.exports = defineConfig({
  transpileDependencies: true,
  transpileDependencies: ["@kitware/vtk.js"],
  devServer: {
    proxy: "http://127.0.0.1:5000"
  }
})
