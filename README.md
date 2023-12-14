### Tutorial
## Prerequisites

1.  libpressio
2.  nodejs, vue
3.  python (flask, flask_cors, json, numpy)

## Project setup
```
cd to the path that you git clone the code
run `npm install`
```

### Compiles and hot-reloads for development
```
run `npm run serve` to start vue.
```

```
The dashboard should look like this figure.
```
<img width="1480" alt="image" src="https://github.com/YuxiaoLi1234/fzvis/assets/143280350/f2c1e547-3652-4b3b-a8a7-944e3242bca1">

### workflow
## upload data first:
```
  Upload the data you are going to compress in the bottom left view.
```
  <img width="425" alt="image" src="https://github.com/YuxiaoLi1234/fzvis/assets/143280350/42e2a6d0-9a52-4e7c-88a8-4e39e349e957">

## run compressor:
  enter the configuration and also the absolute path of your input file. After you have configured all the options, press the Enter key
  <img width="434" alt="image" src="https://github.com/YuxiaoLi1234/fzvis/assets/143280350/118e1975-5c44-4e41-9665-404b73f382c9">
  ```
  compresoor_id: Please enter the compressor that is supported by libpressio.
  ```
  ```
  early config: Please include your input with single quotation mark, if you are going to include a path in your configuration, please make sure you entered the absolute path.
  ```
  ```
  compressor_config: Please include your input with single quotation mark. 
  ```
  ```
  path_to_input_data: Please enter the absolute path of your input file. Include your input with single quotation mark.
  ```
  ```
  compressor_name: The name for this configuration of compressor.
  ```







