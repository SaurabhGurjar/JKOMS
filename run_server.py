# run_server.py

import os

from waitress import serve

from config.wsgi import application


def main():
    host = os.getenv(
        "LTPOMS_HOST",
        "0.0.0.0",
    )

    port = int(
        os.getenv(
            "LTPOMS_PORT",
            "8000",
        )
    )

    threads = int(
        os.getenv(
            "LTPOMS_THREADS",
            "8",
        )
    )

    print(
        f"Starting LTPOMS on "
        f"http://{host}:{port}"
    )

    serve(
        application,
        host=host,
        port=port,
        threads=threads,
        channel_timeout=120,
        cleanup_interval=30,
        ident="LTPOMS",
    )


if __name__ == "__main__":
    main()