const path = require("path");
const HtmlWebpackPlugin = require("html-webpack-plugin");
const CopyWebpackPlugin = require("copy-webpack-plugin");
const devCerts = require("office-addin-dev-certs");

module.exports = async (env, options) => {
  const dev = options.mode === "development";
  const httpsOptions = dev ? await devCerts.getHttpsServerOptions() : undefined;

  return {
    entry: {
      taskpane: "./src/taskpane/taskpane.ts",
    },
    output: {
      path: path.resolve(__dirname, "dist"),
      filename: "[name].js",
      clean: true,
    },
    resolve: {
      extensions: [".ts", ".js"],
    },
    module: {
      rules: [
        {
          test: /\.ts$/,
          use: "ts-loader",
          exclude: /node_modules/,
        },
      ],
    },
    plugins: [
      new HtmlWebpackPlugin({
        template: "./src/taskpane/taskpane.html",
        filename: "taskpane.html",
        inject: true,
      }),
      new CopyWebpackPlugin({
        patterns: [
          {
            from: "manifest.xml",
            to: "manifest.xml",
          },
          {
            from: "assets",
            to: "assets",
            noErrorOnMissing: true,
          },
        ],
      }),
    ],
    devServer: {
      port: 3000,
      https: httpsOptions,
      hot: true,
      headers: {
        "Access-Control-Allow-Origin": "*",
      },
    },
    devtool: dev ? "source-map" : false,
  };
};
