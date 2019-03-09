/*
 * Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License").
 * You may not use this file except in compliance with the License.
 * A copy of the License is located at
 *
 *   http://aws.amazon.com/apache2.0/
 *
 * or in the "license" file accompanying this file. This file is distributed
 * on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
 * express or implied. See the License for the specific language governing
 * permissions and limitations under the License.
 */
const webpack = require('webpack');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');

const ENV = process.env.NODE_ENV || 'development';
let DEV_SERVER = '';
try {
  DEV_SERVER = require('./development_app_location.js');
} catch(err) {
  // May not be initialized yet by build script, which is only an issue for running webpack server
}

module.exports = {
  cache: true,

  devServer: {
    disableHostCheck: true,
    proxy: {
      // allows using local API endpoint when developing code
      '/api': {
        target: DEV_SERVER,
        changeOrigin: true,
        secure: true
      },
    },
    historyApiFallback: {
        rewrites: [
            // allows to render index.development.html when the developer
            // accesses the development server using following URL
            // http://<ip>:<port/
            { from: /^\/$/, to: '/static/index.development.html' },

            // in order to be able to support entry points to routes of the app
            // we need to render the same thing for whatever URL the developer
            // provides. Router will render 404 eventually if the Route does not
            // exist:
            { from: /./, to: '/static/index.development.html' },
        ],
    },
  },

  entry: {
    app: "./src/index.jsx"
  },

  output: {
    filename: "[name]." + ENV + ".js",
    path: __dirname + "/../build/static",
    publicPath: '/static/'
  },

  devtool: (ENV === "production") ? "source-map" : "eval-cheap-module-source-map",

  resolve: {
    extensions: [".jsx", ".js", ".json", ".css"]
  },

  module: {
    rules: [
      { test: /\.jsx?$/, exclude: /node_modules/, use: ['babel-loader']},
      { test: /\.html$/, use: ['html-loader'] },
      { test: /\.css$/,
      use: [
        {
            'loader': MiniCssExtractPlugin.loader
        },
        'css-loader'
      ]},
      { test: /\.(ttf|eot|otf|svg|woff(2)?)(\?[a-z0-9]+)?$/, use: {loader: 'file-loader'}},
      { test: /\.mp3$|\.ico$/, use: {loader: 'file-loader', query: {name: '[name].[ext]'}}}
    ],
  },

  plugins: [
      new HtmlWebpackPlugin({
          template: 'src/index.html',
          filename: `index.${ENV}.html`
      }),
      new MiniCssExtractPlugin({filename: '[contenthash].css'})
  ]
};
