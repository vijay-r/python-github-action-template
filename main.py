import logging
import logging.handlers
import sys

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# === File handler (rotating log) ===
file_handler = logging.handlers.RotatingFileHandler(
    "status.log",
    maxBytes=1024 * 1024,
    backupCount=1,
    encoding="utf8",
)

# === Console handler (shows in GitHub Actions logs) ===
console_handler = logging.StreamHandler(sys.stdout)

# === Formatter ===
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers
logger.addHandler(file_handler)
logger.addHandler(console_handler)

if __name__ == "__main__":
    logger.info("Token value: Vj......")
    logger.info("Weather in Singapore: XXX")
