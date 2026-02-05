import json
import os
import shutil
import subprocess
import time
import urllib.request
from datetime import datetime

from config import Config, PROFILES

try:
    import boto3
except Exception:
    boto3 = None


ERR_VALIDATION = "ERR_VALIDATION"
ERR_INPUT_DOWNLOAD = "ERR_INPUT_DOWNLOAD"
ERR_INPUT_PROBE = "ERR_INPUT_PROBE"
ERR_DEINTERLACE = "ERR_DEINTERLACE"
ERR_EXPOSURE = "ERR_EXPOSURE"
ERR_DENOISE = "ERR_DENOISE"
ERR_UPSCALE = "ERR_UPSCALE"
ERR_ENCODE = "ERR_ENCODE"
ERR_UPLOAD = "ERR_UPLOAD"
ERR_TIMEOUT = "ERR_TIMEOUT"
ERR_INTERNAL = "ERR_INTERNAL"


def _ts():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")


def log_line(logs, message):
    logs.append("[%s] %s" % (_ts(), message))


def run_cmd(cmd, timeout, logs, stage, err_code):
    log_line(logs, "Running %s" % stage)
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except subprocess.TimeoutExpired:
        log_line(logs, "Timeout in %s" % stage)
        raise PipelineError(err_code, "Stage timeout", logs)
    if result.returncode != 0:
        log_line(logs, "%s failed: %s" % (stage, result.stderr.decode("utf-8", errors="ignore")))
        raise PipelineError(err_code, "Processing failed", logs)
    return result


class PipelineError(Exception):
    def __init__(self, code, message, logs):
        super(PipelineError, self).__init__(message)
        self.code = code
        self.message = message
        self.logs = logs


def parse_target_resolution(value):
    if not value or "x" not in value:
        return None
    parts = value.lower().split("x")
    if len(parts) != 2:
        return None
    try:
        w = int(parts[0])
        h = int(parts[1])
        if w <= 0 or h <= 0:
            return None
        return w, h
    except Exception:
        return None


def apply_profile(request):
    profile = request.get("profile")
    if not profile:
        return request
    if profile not in PROFILES:
        return request
    merged = {}
    merged.update(PROFILES[profile])
    merged.update(request)
    merged["profile"] = profile
    return merged


def validate_request(request, logs):
    errors = []
    input_url = request.get("input_url")
    if not input_url:
        errors.append("input_url required")
    if input_url:
        if not (input_url.startswith("https://") or input_url.startswith("http://")):
            errors.append("input_url must be http(s)")
        if not Config.ALLOW_HTTP_INPUT and input_url.startswith("http://"):
            errors.append("http input not allowed")

    ext_ok = True
    if input_url and "." in input_url.split("?")[0]:
        ext = input_url.split("?")[0].split(".")[-1].lower()
        if Config.ALLOWED_EXTENSIONS and ext not in Config.ALLOWED_EXTENSIONS:
            ext_ok = False
    if not ext_ok:
        errors.append("extension not allowed")

    def _range(name, v, lo, hi):
        if v is None:
            return
        try:
            fv = float(v)
        except Exception:
            errors.append("%s must be number" % name)
            return
        if fv < lo or fv > hi:
            errors.append("%s out of range" % name)

    _range("denoise_strength", request.get("denoise_strength"), 0, 100)
    _range("sharpen_strength", request.get("sharpen_strength"), 0, 100)
    _range("brightness", request.get("brightness"), -1.0, 1.0)
    _range("gamma", request.get("gamma"), 0.6, 1.8)
    _range("contrast", request.get("contrast"), 0.5, 1.5)

    if request.get("auto_exposure") is not None and not isinstance(request.get("auto_exposure"), bool):
        errors.append("auto_exposure must be boolean")

    if request.get("deinterlace") and request.get("deinterlace") not in ("auto", "on", "off"):
        errors.append("deinterlace must be auto|on|off")

    if request.get("codec") and request.get("codec") not in ("h264", "h265"):
        errors.append("codec must be h264|h265")

    if request.get("container") and request.get("container") not in ("mp4", "mkv"):
        errors.append("container must be mp4|mkv")

    if request.get("target_resolution"):
        if parse_target_resolution(request.get("target_resolution")) is None:
            errors.append("target_resolution must be WIDTHxHEIGHT")

    if request.get("profile") and request.get("profile") not in PROFILES:
        errors.append("profile must be fast_preview|balanced|max_cleanup|dark_footage")

    if errors:
        for e in errors:
            log_line(logs, "Validation error: %s" % e)
        raise PipelineError(ERR_VALIDATION, "Invalid request", logs)


def estimate_input_size_gb(url, logs):
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=30) as resp:
            length = resp.headers.get("Content-Length")
            if length:
                size_gb = float(length) / (1024 ** 3)
                log_line(logs, "Estimated input size: %.2f GB" % size_gb)
                return size_gb
    except Exception as exc:
        log_line(logs, "HEAD size check failed: %s" % exc)
    return None


def download_input(url, out_path, logs):
    log_line(logs, "Downloading input")
    try:
        with urllib.request.urlopen(url, timeout=Config.STAGE_TIMEOUT_DOWNLOAD) as resp:
            with open(out_path, "wb") as f:
                shutil.copyfileobj(resp, f, length=1024 * 1024)
    except Exception as exc:
        log_line(logs, "Download error: %s" % exc)
        raise PipelineError(ERR_INPUT_DOWNLOAD, "Input download failed", logs)


def ffprobe_metadata(path, logs):
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", "-show_format", path
    ]
    try:
        result = run_cmd(cmd, 120, logs, "probe", ERR_INPUT_PROBE)
        data = json.loads(result.stdout.decode("utf-8", errors="ignore"))
        return data
    except PipelineError:
        raise
    except Exception as exc:
        log_line(logs, "Probe error: %s" % exc)
        raise PipelineError(ERR_INPUT_PROBE, "Input probe failed", logs)


def detect_interlace(path, logs):
    log_line(logs, "Detecting interlace")
    cmd = [
        "ffmpeg", "-i", path,
        "-filter:v", "idet",
        "-frames:v", "300",
        "-an", "-f", "rawvideo", "-y", os.devnull
    ]
    try:
        result = run_cmd(cmd, 300, logs, "interlace_detect", ERR_DEINTERLACE)
        stderr = result.stderr.decode("utf-8", errors="ignore")
        # Heuristic: consider interlaced if TFF/BFF counts present
        return ("TFF" in stderr) or ("BFF" in stderr)
    except PipelineError:
        raise


def build_exposure_filter(brightness, gamma, contrast, auto_exposure, logs):
    # Conservative auto exposure adjustment using eq
    b = brightness
    g = gamma
    c = contrast
    if auto_exposure:
        b = min(1.0, max(-1.0, b + Config.AUTO_EXPOSURE_STRENGTH * Config.SHADOW_LIFT_LIMIT))
        g = min(1.8, max(0.6, g + (Config.AUTO_EXPOSURE_STRENGTH * 0.3)))
        c = min(1.5, max(0.5, c * (1.0 + (1.0 - Config.HIGHLIGHT_PROTECT) * 0.1)))
        log_line(logs, "Auto exposure applied: b=%.3f g=%.3f c=%.3f" % (b, g, c))
    return "eq=brightness=%.3f:gamma=%.3f:contrast=%.3f" % (b, g, c), b, g, c


def build_sharpen_filter(sharpen_strength):
    # Map 0..100 to unsharp amount (0..1.5)
    amount = max(0.0, min(1.5, (sharpen_strength / 100.0) * 1.5))
    if amount <= 0.01:
        return None
    return "unsharp=7:7:%.2f:7:7:%.2f" % (amount, amount)


def enforce_max_job_seconds(start_time, logs):
    elapsed = time.time() - start_time
    if elapsed > Config.MAX_JOB_SECONDS:
        log_line(logs, "Max job time exceeded")
        raise PipelineError(ERR_TIMEOUT, "Job timeout", logs)


def log_realesrgan_info(logs):
    path = shutil.which("realesrgan-ncnn-vulkan")
    log_line(logs, "which realesrgan-ncnn-vulkan: %s" % (path if path else "NOT FOUND"))
    if not path:
        return
    try:
        out = subprocess.check_output([path, "-h"], stderr=subprocess.STDOUT, timeout=5)
        text = out.decode("utf-8", errors="ignore").strip()
        if len(text) > 400:
            text = text[:400] + "..."
        log_line(logs, "realesrgan-ncnn-vulkan -h: %s" % text)
    except Exception as exc:
        log_line(logs, "realesrgan-ncnn-vulkan -h failed: %s" % exc)


def pipeline(request):
    logs = []
    start_time = time.time()
    log_line(logs, "Job started")
    log_realesrgan_info(logs)

    request = apply_profile(request)
    validate_request(request, logs)

    input_url = request.get("input_url")
    size_gb = estimate_input_size_gb(input_url, logs)
    if size_gb is not None and size_gb > Config.MAX_INPUT_GB:
        log_line(logs, "Input too large: %.2f GB" % size_gb)
        raise PipelineError(ERR_VALIDATION, "Input too large", logs)

    os.makedirs(Config.WORK_DIR, exist_ok=True)
    os.makedirs(Config.TMP_DIR, exist_ok=True)

    job_id = str(int(time.time()))
    work_dir = os.path.join(Config.WORK_DIR, job_id)
    tmp_dir = os.path.join(Config.TMP_DIR, job_id)
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(tmp_dir, exist_ok=True)

    input_path = os.path.join(tmp_dir, "input")
    download_input(input_url, input_path, logs)
    try:
        file_size = os.path.getsize(input_path)
        size_gb = float(file_size) / (1024 ** 3)
        log_line(logs, "Downloaded size: %.2f GB" % size_gb)
        if size_gb > Config.MAX_INPUT_GB:
            raise PipelineError(ERR_VALIDATION, "Input too large", logs)
    except PipelineError:
        raise
    except Exception:
        pass
    enforce_max_job_seconds(start_time, logs)

    meta = ffprobe_metadata(input_path, logs)
    interlaced = detect_interlace(input_path, logs)
    enforce_max_job_seconds(start_time, logs)

    deinterlace = request.get("deinterlace", Config.DEFAULT_DEINTERLACE)
    denoise_strength = int(request.get("denoise_strength", Config.DEFAULT_DENOISE))
    sharpen_strength = int(request.get("sharpen_strength", Config.DEFAULT_SHARPEN))
    brightness = float(request.get("brightness", Config.DEFAULT_BRIGHTNESS))
    gamma = float(request.get("gamma", Config.DEFAULT_GAMMA))
    contrast = float(request.get("contrast", Config.DEFAULT_CONTRAST))
    auto_exposure = bool(request.get("auto_exposure", Config.DEFAULT_AUTO_EXPOSURE))
    model = request.get("model", Config.DEFAULT_MODEL)
    target_res = request.get("target_resolution", Config.DEFAULT_TARGET_RES)
    codec = request.get("codec", Config.DEFAULT_CODEC)
    container = request.get("container", Config.DEFAULT_CONTAINER)
    keep_audio = bool(request.get("keep_audio", Config.KEEP_AUDIO))
    preset = request.get("preset", Config.DEFAULT_PRESET)

    crf = request.get("crf")
    if crf is None:
        crf = Config.DEFAULT_CRF_H265 if codec == "h265" else Config.DEFAULT_CRF_H264

    target_wh = parse_target_resolution(target_res)
    if target_wh is None:
        raise PipelineError(ERR_VALIDATION, "Invalid target resolution", logs)

    # Stage 3-5: preprocess (deinterlace + exposure + denoise + sharpen)
    filters = []
    if deinterlace == "on" or (deinterlace == "auto" and interlaced):
        filters.append("bwdif")
    elif deinterlace == "off":
        pass

    # Stage 4: exposure
    exposure_filter, applied_b, applied_g, applied_c = build_exposure_filter(brightness, gamma, contrast, auto_exposure, logs)
    filters.append(exposure_filter)

    # Stage 5: denoise
    # Map 0..100 to hqdn3d luma/chroma values
    luma = max(0.0, min(4.0, denoise_strength / 25.0))
    chroma = max(0.0, min(3.0, denoise_strength / 35.0))
    filters.append("hqdn3d=%.2f:%.2f:%.2f:%.2f" % (luma, chroma, luma, chroma))

    sharpen_filter = build_sharpen_filter(sharpen_strength)
    if sharpen_filter:
        filters.append(sharpen_filter)

    # Stage 6/7: upscale + resize
    # Real-ESRGAN expected to output upscaled frames; here we call a wrapper command
    stage4_path = os.path.join(tmp_dir, "stage4_exposed.mp4")
    filter_chain = ",".join(filters) if filters else "null"

    vf_cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", filter_chain,
        "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
        "-an", stage4_path
    ]
    try:
        run_cmd(vf_cmd, Config.STAGE_TIMEOUT_PROCESS, logs, "preprocess", ERR_EXPOSURE)
    except PipelineError as pe:
        # If bwdif failed, retry with yadif
        if "bwdif" in filter_chain:
            log_line(logs, "bwdif failed; retrying with yadif")
            filter_chain_retry = filter_chain.replace("bwdif", "yadif")
            vf_cmd[5] = filter_chain_retry
            run_cmd(vf_cmd, Config.STAGE_TIMEOUT_PROCESS, logs, "preprocess_yadif", ERR_DEINTERLACE)
        else:
            raise pe
    enforce_max_job_seconds(start_time, logs)

    stage6_path = os.path.join(tmp_dir, "stage6_upscaled.mp4")
    re_cmd = [
        "realesrgan-ncnn-vulkan", "-i", stage4_path,
        "-o", stage6_path,
        "-n", model,
        "-s", str(Config.UPSCALE_FACTOR)
    ]
    try:
        run_cmd(re_cmd, Config.STAGE_TIMEOUT_PROCESS, logs, "upscale", ERR_UPSCALE)
    except PipelineError:
        raise
    enforce_max_job_seconds(start_time, logs)

    # Stage 7/8: resize + encode
    output_path = os.path.join(work_dir, "final.%s" % container)
    w, h = target_wh
    audio_args = []
    audio_input = None
    if keep_audio:
        audio_input = os.path.join(tmp_dir, "audio.m4a")
        audio_cmd = ["ffmpeg", "-y", "-i", input_path, "-vn", "-c:a", Config.AUDIO_CODEC, "-b:a", Config.AUDIO_BITRATE, audio_input]
        try:
            run_cmd(audio_cmd, 300, logs, "extract_audio", ERR_ENCODE)
        except PipelineError:
            log_line(logs, "Audio extraction failed; continuing without audio")
            audio_input = None
    if audio_input:
        audio_args = ["-i", audio_input, "-map", "0:v:0", "-map", "1:a:0", "-c:a", Config.AUDIO_CODEC, "-b:a", Config.AUDIO_BITRATE]

    vcodec = "libx265" if codec == "h265" else "libx264"
    encode_cmd = [
        "ffmpeg", "-y", "-i", stage6_path,
        "-vf", "scale=%d:%d" % (w, h),
        "-c:v", vcodec, "-crf", str(crf), "-preset", preset
    ] + audio_args + [output_path]

    try:
        run_cmd(encode_cmd, Config.STAGE_TIMEOUT_PROCESS, logs, "encode", ERR_ENCODE)
    except PipelineError:
        raise
    enforce_max_job_seconds(start_time, logs)

    # Stage 9/10: upload (S3 via aws-cli if available)
    output_url = None
    if Config.S3_ENDPOINT and Config.S3_BUCKET:
        if boto3 is None:
            log_line(logs, "boto3 not available for S3 upload")
            raise PipelineError(ERR_UPLOAD, "Upload failed", logs)
        key = "%s%s" % (Config.S3_OUTPUT_PREFIX, os.path.basename(output_path))
        try:
            session = boto3.session.Session(
                aws_access_key_id=Config.S3_ACCESS_KEY_ID,
                aws_secret_access_key=Config.S3_SECRET_ACCESS_KEY,
                region_name=Config.S3_REGION or None,
            )
            s3 = session.client(
                "s3",
                endpoint_url=Config.S3_ENDPOINT,
                use_ssl=bool(Config.S3_USE_SSL),
            )
            log_line(logs, "Uploading output to S3")
            s3.upload_file(output_path, Config.S3_BUCKET, key)
            output_url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": Config.S3_BUCKET, "Key": key},
                ExpiresIn=Config.S3_SIGNED_URL_TTL_SEC,
            )
        except Exception as exc:
            log_line(logs, "S3 upload error: %s" % exc)
            raise PipelineError(ERR_UPLOAD, "Upload failed", logs)
    else:
        output_url = "file://" + output_path

    elapsed = int(time.time() - start_time)
    log_line(logs, "Job finished in %ss" % elapsed)

    if Config.CLEANUP_TEMP and not Config.KEEP_INTERMEDIATES:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    duration_sec = 0
    input_resolution = ""
    try:
        fmt = meta.get("format", {})
        if "duration" in fmt:
            duration_sec = float(fmt["duration"])
        for stream in meta.get("streams", []):
            if stream.get("codec_type") == "video":
                w_in = stream.get("width")
                h_in = stream.get("height")
                if w_in and h_in:
                    input_resolution = "%dx%d" % (w_in, h_in)
                break
    except Exception:
        pass

    metadata = {
        "duration_sec": duration_sec,
        "input_resolution": input_resolution,
        "output_resolution": "%dx%d" % (w, h),
        "interlace_detected": bool(interlaced),
        "applied_exposure": {
            "brightness": applied_b,
            "gamma": applied_g,
            "contrast": applied_c,
            "auto_exposure": bool(auto_exposure),
        },
    }

    return {
        "status": "completed",
        "output_url": output_url,
        "metadata": metadata,
        "logs": logs,
    }
