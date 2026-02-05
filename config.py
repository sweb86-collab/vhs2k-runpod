import os


def _get_bool(key, default=False):
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "y", "on")


def _get_int(key, default=0):
    val = os.getenv(key)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except Exception:
        return default


def _get_float(key, default=0.0):
    val = os.getenv(key)
    if val is None or val == "":
        return default
    try:
        return float(val)
    except Exception:
        return default


def _get_str(key, default=""):
    val = os.getenv(key)
    if val is None:
        return default
    return val


class Config(object):
    APP_ENV = _get_str("APP_ENV", "production")
    LOG_LEVEL = _get_str("LOG_LEVEL", "info")
    WORK_DIR = _get_str("WORK_DIR", "/workspace/jobs")
    TMP_DIR = _get_str("TMP_DIR", "/workspace/tmp")

    MAX_JOB_SECONDS = _get_int("MAX_JOB_SECONDS", 28800)
    STAGE_TIMEOUT_DOWNLOAD = _get_int("STAGE_TIMEOUT_DOWNLOAD", 1800)
    STAGE_TIMEOUT_PROCESS = _get_int("STAGE_TIMEOUT_PROCESS", 25200)
    STAGE_TIMEOUT_UPLOAD = _get_int("STAGE_TIMEOUT_UPLOAD", 1800)
    CLEANUP_TEMP = _get_bool("CLEANUP_TEMP", True)
    KEEP_INTERMEDIATES = _get_bool("KEEP_INTERMEDIATES", False)

    MAX_INPUT_GB = _get_int("MAX_INPUT_GB", 20)
    ALLOW_HTTP_INPUT = _get_bool("ALLOW_HTTP_INPUT", False)
    ALLOWED_EXTENSIONS = [e.strip().lower() for e in _get_str("ALLOWED_EXTENSIONS", "mp4,mov,mkv,avi,mpeg,mpg,m4v").split(",") if e.strip()]

    DEFAULT_TARGET_RES = _get_str("DEFAULT_TARGET_RES", "2048x1080")
    DEFAULT_CODEC = _get_str("DEFAULT_CODEC", "h265")
    DEFAULT_CONTAINER = _get_str("DEFAULT_CONTAINER", "mp4")
    DEFAULT_CRF_H265 = _get_int("DEFAULT_CRF_H265", 20)
    DEFAULT_CRF_H264 = _get_int("DEFAULT_CRF_H264", 18)
    DEFAULT_PRESET = _get_str("DEFAULT_PRESET", "medium")
    KEEP_AUDIO = _get_bool("KEEP_AUDIO", True)
    AUDIO_CODEC = _get_str("AUDIO_CODEC", "aac")
    AUDIO_BITRATE = _get_str("AUDIO_BITRATE", "192k")

    DEFAULT_DEINTERLACE = _get_str("DEFAULT_DEINTERLACE", "auto")
    DEFAULT_DENOISE = _get_int("DEFAULT_DENOISE", 35)
    DEFAULT_SHARPEN = _get_int("DEFAULT_SHARPEN", 20)
    DEFAULT_MODEL = _get_str("DEFAULT_MODEL", "realesrgan-x2plus")
    UPSCALE_FACTOR = _get_int("UPSCALE_FACTOR", 2)

    DEFAULT_BRIGHTNESS = _get_float("DEFAULT_BRIGHTNESS", 0.0)
    DEFAULT_GAMMA = _get_float("DEFAULT_GAMMA", 1.0)
    DEFAULT_CONTRAST = _get_float("DEFAULT_CONTRAST", 1.0)
    DEFAULT_AUTO_EXPOSURE = _get_bool("DEFAULT_AUTO_EXPOSURE", False)
    AUTO_EXPOSURE_STRENGTH = _get_float("AUTO_EXPOSURE_STRENGTH", 0.35)
    HIGHLIGHT_PROTECT = _get_float("HIGHLIGHT_PROTECT", 0.85)
    SHADOW_LIFT_LIMIT = _get_float("SHADOW_LIFT_LIMIT", 0.25)

    S3_ENDPOINT = _get_str("S3_ENDPOINT", "")
    S3_REGION = _get_str("S3_REGION", "")
    S3_BUCKET = _get_str("S3_BUCKET", "")
    S3_ACCESS_KEY_ID = _get_str("S3_ACCESS_KEY_ID", "")
    S3_SECRET_ACCESS_KEY = _get_str("S3_SECRET_ACCESS_KEY", "")
    S3_OUTPUT_PREFIX = _get_str("S3_OUTPUT_PREFIX", "vhs2k/")
    S3_USE_SSL = _get_bool("S3_USE_SSL", True)
    S3_SIGNED_URL_TTL_SEC = _get_int("S3_SIGNED_URL_TTL_SEC", 604800)

    WEBHOOK_URL = _get_str("WEBHOOK_URL", "")
    WEBHOOK_SECRET = _get_str("WEBHOOK_SECRET", "")


PROFILES = {
    "fast_preview": {
        "deinterlace": "auto",
        "denoise_strength": 25,
        "sharpen_strength": 10,
        "brightness": 0.03,
        "gamma": 1.03,
        "contrast": 1.00,
        "auto_exposure": False,
        "codec": "h264",
        "crf": 20,
        "preset": "faster",
    },
    "balanced": {
        "deinterlace": "auto",
        "denoise_strength": 35,
        "sharpen_strength": 20,
        "brightness": 0.00,
        "gamma": 1.00,
        "contrast": 1.00,
        "auto_exposure": False,
        "codec": "h265",
        "crf": 20,
        "preset": "medium",
    },
    "max_cleanup": {
        "deinterlace": "on",
        "denoise_strength": 45,
        "sharpen_strength": 15,
        "brightness": 0.00,
        "gamma": 1.00,
        "contrast": 1.00,
        "auto_exposure": False,
        "codec": "h265",
        "crf": 18,
        "preset": "slow",
    },
    "dark_footage": {
        "deinterlace": "auto",
        "denoise_strength": 35,
        "sharpen_strength": 15,
        "brightness": 0.08,
        "gamma": 1.10,
        "contrast": 1.04,
        "auto_exposure": True,
        "codec": "h265",
        "crf": 20,
        "preset": "medium",
    },
}
