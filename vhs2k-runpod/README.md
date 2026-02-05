# VHS2K Runpod Serverless Endpoint

## 1. Overview
This serverless endpoint performs VHS cleanup and AI upscale to 2K using ffmpeg/ffprobe + Real-ESRGAN. It accepts a video URL, processes via staged pipeline, and returns an `output_url` plus metadata and logs suitable for a desktop client.

## 2. Environment Variables
| Key | Description | Default |
|---|---|---|
| APP_ENV | Environment name | production |
| LOG_LEVEL | Log verbosity | info |
| WORK_DIR | Job output directory | /workspace/jobs |
| TMP_DIR | Temp working directory | /workspace/tmp |
| MAX_JOB_SECONDS | Max total job time | 28800 |
| STAGE_TIMEOUT_DOWNLOAD | Download stage timeout | 1800 |
| STAGE_TIMEOUT_PROCESS | Processing stage timeout | 25200 |
| STAGE_TIMEOUT_UPLOAD | Upload stage timeout | 1800 |
| CLEANUP_TEMP | Remove temp files | true |
| KEEP_INTERMEDIATES | Preserve intermediates | false |
| MAX_INPUT_GB | Max input size | 20 |
| ALLOW_HTTP_INPUT | Allow http (non-https) | false |
| ALLOWED_EXTENSIONS | Comma list | mp4,mov,mkv,avi,mpeg,mpg,m4v |
| DEFAULT_TARGET_RES | Target resolution | 2048x1080 |
| DEFAULT_CODEC | h264/h265 | h265 |
| DEFAULT_CONTAINER | mp4/mkv | mp4 |
| DEFAULT_CRF_H265 | CRF for h265 | 20 |
| DEFAULT_CRF_H264 | CRF for h264 | 18 |
| DEFAULT_PRESET | ffmpeg preset | medium |
| KEEP_AUDIO | Keep audio stream | true |
| AUDIO_CODEC | Audio codec | aac |
| AUDIO_BITRATE | Audio bitrate | 192k |
| DEFAULT_DEINTERLACE | auto/on/off | auto |
| DEFAULT_DENOISE | 0-100 | 35 |
| DEFAULT_SHARPEN | 0-100 | 20 |
| DEFAULT_MODEL | Real-ESRGAN model | realesrgan-x2plus |
| UPSCALE_FACTOR | Upscale factor | 2 |
| DEFAULT_BRIGHTNESS | -1.0..1.0 | 0.0 |
| DEFAULT_GAMMA | 0.6..1.8 | 1.0 |
| DEFAULT_CONTRAST | 0.5..1.5 | 1.0 |
| DEFAULT_AUTO_EXPOSURE | Auto exposure | false |
| AUTO_EXPOSURE_STRENGTH | Auto exposure strength | 0.35 |
| HIGHLIGHT_PROTECT | Protect highlights | 0.85 |
| SHADOW_LIFT_LIMIT | Shadow lift cap | 0.25 |
| S3_ENDPOINT | S3 endpoint | (required for upload) |
| S3_REGION | S3 region |  |
| S3_BUCKET | S3 bucket |  |
| S3_ACCESS_KEY_ID | S3 access key |  |
| S3_SECRET_ACCESS_KEY | S3 secret |  |
| S3_OUTPUT_PREFIX | Output prefix | vhs2k/ |
| S3_USE_SSL | Use SSL | true |
| S3_SIGNED_URL_TTL_SEC | Signed URL TTL | 604800 |
| WEBHOOK_URL | Optional webhook |  |
| WEBHOOK_SECRET | Optional webhook secret |  |

## 3. Profiles
- `fast_preview`: Faster encode and lighter cleanup.
- `balanced`: Default; good tradeoff.
- `max_cleanup`: Stronger cleanup, slower.
- `dark_footage`: Adds exposure lift and auto exposure.

Profiles are applied first; explicit request fields override profile values.

## 4. Exposure Controls
- `brightness`: -1.0..1.0
- `gamma`: 0.6..1.8
- `contrast`: 0.5..1.5
- `auto_exposure`: enable for dark footage

Tips:
- Use `dark_footage` profile for dim sources.
- Avoid large brightness increases to prevent washed highlights.
- Use small gamma boosts first, then brightness.

## 5. API Contract
### Request
```json
{
  "input_url": "https://...",
  "target_resolution": "2048x1080",
  "deinterlace": "auto|on|off",
  "denoise_strength": 0-100,
  "sharpen_strength": 0-100,
  "brightness": -1.0,
  "gamma": 1.0,
  "contrast": 1.0,
  "auto_exposure": false,
  "model": "realesrgan-x2plus",
  "codec": "h264|h265",
  "container": "mp4|mkv",
  "keep_audio": true,
  "profile": "fast_preview|balanced|max_cleanup|dark_footage",
  "job_name": "optional"
}
```

### Success
```json
{
  "status": "completed",
  "output_url": "https://.../final.mp4",
  "metadata": {
    "duration_sec": 0,
    "input_resolution": "WxH",
    "output_resolution": "2048x1080",
    "interlace_detected": true,
    "applied_exposure": {
      "brightness": 0.0,
      "gamma": 1.0,
      "contrast": 1.0,
      "auto_exposure": false
    }
  },
  "logs": ["timestamped stage messages"]
}
```

### Failure
```json
{
  "status": "failed",
  "error_code": "ERR_*",
  "error_message": "human readable",
  "logs": ["timestamped stage messages"]
}
```

## 6. Deployment Steps
1. Build the image (provide Real-ESRGAN binary URL):\n   `docker build -t vhs2k-endpoint --build-arg REALESRGAN_URL=<zip_url> .`\n2. Push to registry: `docker tag/push` to your registry.\n3. Create Runpod serverless endpoint from the image.\n4. Set environment variables from `.env.example`.\n5. Ensure `ffmpeg`, `ffprobe`, and `realesrgan-ncnn-vulkan` are present in the image.\n6. S3 uploads use `boto3` and pre-signed URLs; configure S3 env vars.

## 7. Testing
- Start with a 60–120s clip.
- Then test a full ~90-minute job.

## 8. Troubleshooting (by error code)
- `ERR_VALIDATION`: Request fields invalid or input too large.
- `ERR_INPUT_DOWNLOAD`: URL not reachable or blocked.
- `ERR_INPUT_PROBE`: ffprobe failure.
- `ERR_DEINTERLACE`: idet/deinterlace failure.
- `ERR_EXPOSURE`: exposure stage failed.
- `ERR_DENOISE`: denoise stage failed.
- `ERR_UPSCALE`: Real-ESRGAN failure.
- `ERR_ENCODE`: final encode failure.
- `ERR_UPLOAD`: upload failure.
- `ERR_TIMEOUT`: stage timeout.
- `ERR_INTERNAL`: unhandled error.

## 9. Swift Client Integration Notes
- Submit job with JSON matching request contract.
- Poll status and read `output_url` when completed.
- Display `logs` for progress messages.

## Docker Notes
- `REALESGAN_URL` should be a direct link to a zip containing `realesrgan-ncnn-vulkan` binary.
- If you keep the binary in your repo, copy it into `/opt/realesrgan` and remove the build arg.

## GitHub Actions (CI Build)
Required GitHub secrets:
- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`
- `REALESGAN_URL`

Run the workflow manually:
1) Go to Actions → “Build and Push Runpod Image”.  
2) Click “Run workflow” and set `tag` (default `latest`).

Resulting image tag format:
`docker.io/sweb86/vhs2k-endpoint:<tag>`

Next step:
Create a Runpod Serverless endpoint using the pushed image tag.
