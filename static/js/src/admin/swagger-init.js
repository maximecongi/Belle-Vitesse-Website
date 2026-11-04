window.onload = function () {
    if (typeof SwaggerUIBundle !== 'undefined') {
        const ui = SwaggerUIBundle({
            url: "/static/docs/openapi.yaml",
            dom_id: '#swagger-ui',
            deepLinking: true,
            presets: [
                SwaggerUIBundle.presets.apis,
                SwaggerUIStandalonePreset
            ],
            plugins: [
                SwaggerUIBundle.plugins.DownloadUrl
            ],
            layout: "StandaloneLayout"
        });
        window.ui = ui;
    }
};

