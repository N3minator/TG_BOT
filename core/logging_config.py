import logging
import sys


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    logging.getLogger("telegram.ext").setLevel(logging.INFO)
    logging.getLogger("telegram.bot").setLevel(logging.INFO)
