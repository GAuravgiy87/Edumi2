const path = require('path');
module.exports = {
    mode: 'production',
    entry: './browser-entry.js',
    output: {
        filename: 'mediasoup-client.min.js',
        path: path.resolve(__dirname, '../static/js'),
    },
    resolve: {
        fallback: {
            crypto: false,
            stream: require.resolve('stream-browserify'),
            buffer: require.resolve('buffer/'),
            process: require.resolve('process/browser'),
        }
    },
    plugins: [
        new (require('webpack').ProvidePlugin)({
            process: 'process/browser',
            Buffer: ['buffer', 'Buffer'],
        }),
    ],
};
