import threading


def run_async(app, func, *args, **kwargs):
    """
    Runs a function in a background thread with the provided Flask app context.
    """
    def wrapper(app_context, *f_args, **f_kwargs):
        with app_context:
            try:
                func(*f_args, **f_kwargs)
            except Exception as e:
                app.logger.error(f"❌ Async task error in {func.__name__}: {e}")

    # Use app_context() to create a context that can be passed to the thread
    ctx = app.app_context()
    thread = threading.Thread(target=wrapper, args=(ctx, *args), kwargs=kwargs)
    thread.daemon = True
    thread.start()
    return thread
