import os


def make_url_fetcher(app):
    """
    Custom URL fetcher for WeasyPrint to resolve local paths directly.
    This prevents WeasyPrint from making HTTP requests back to the server,
    which can cause deadlocks in synchronous environments like Gunicorn.
    """
    from weasyprint import default_url_fetcher

    def url_fetcher(url):
        if url.startswith('file://'):
            return default_url_fetcher(url)

        # Handle static files
        static_url_path = app.static_url_path or '/static'
        if url.startswith(static_url_path):
            relative_path = url[len(static_url_path):].lstrip('/')
            file_path = os.path.join(app.static_folder, relative_path)
            return default_url_fetcher(f'file://{file_path}')

        # Handle 'files' (uploaded content)
        if '/files/' in url:
            # Extract path after /files/
            # This assumes files are stored in the output folder
            relative_path = url.split('/files/')[-1].split('?')[0]
            output_folder = app.config.get('OUTPUT_FOLDER')
            if output_folder:
                file_path = os.path.join(output_folder, relative_path)
                if os.path.exists(file_path):
                    return default_url_fetcher(f'file://{file_path}')

        return default_url_fetcher(url)

    return url_fetcher
