# Video Downloader API - AWS Deployment Runbook

**Stack:** Amazon Linux 2023 | Docker | Python 3.12 | FastAPI | S3

---

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Client    │─────▶│  EC2 (API)   │─────▶│  S3 Bucket  │
└─────────────┘      └──────────────┘      └─────────────┘
                            │                      │
                            │                      │
                            ▼                      ▼
                     ┌──────────────┐      ┌─────────────┐
                     │ IAM Instance │      │   Videos    │
                     │   Profile    │      │  (Public)   │
                     └──────────────┘      └─────────────┘
```

**Data Flow:**
1. API receives download request (YouTube/X/Facebook)
2. yt-dlp downloads to `/tmp/downloads/` on EC2
3. Upload to S3 with retry logic (3 attempts, exponential backoff)
4. Delete local copy, return S3 presigned URL
5. Client downloads directly from S3 (bypasses EC2 bandwidth)

**Resources:**
- EC2: t3.micro (1 vCPU, 1GB RAM, 8GB EBS)
- S3: Standard storage, public-read bucket policy
- IAM: EC2 instance profile with S3 write permissions
- SG: Ports 22 (SSH), 8000 (API)

---

## Prerequisites

- An AWS account with console access
- YouTube cookies for authentication (see Cookie Configuration section)

### Values Reference

Keep these handy as you go through the console steps:

| Value | What to use |
|-------|-------------|
| Region | `ap-south-1` (Mumbai) |
| Bucket name | `video-downloader-<any-unique-number>` e.g. `video-downloader-1741500000` |
| Key pair name | `video-downloader-key` |
| IAM Role | Use your existing EC2 IAM role (see Step 1) |
| GitHub repo | `https://github.com/nyxsky404/Video-Downloader.git` |

> Note your **bucket name** and **EC2 public IP** after launch — you will need them for the terminal steps.

---

## Infrastructure Provisioning (AWS Console)

### S3 Bucket

**Console path:** `S3 → Create bucket`

1. **Bucket name:** `video-downloader-<unique-number>` (must be globally unique, e.g. `video-downloader-1741500000`)
2. **AWS Region:** `ap-south-1`
3. **Block Public Access settings:** uncheck **"Block all public access"** → check the acknowledgement warning
4. Leave all other settings as default → click **Create bucket**

**Add public-read bucket policy:**

1. Open the bucket → **Permissions tab**
2. Scroll to **Bucket policy** → click **Edit**
3. Paste the following (replace `YOUR-BUCKET-NAME`):

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "PublicReadGetObject",
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME/*"
  }]
}
```

4. Click **Save changes**

### 3. EC2 Key Pair

**Console path:** `EC2 → Network & Security → Key Pairs → Create key pair`

1. **Name:** `video-downloader-key`
2. **Key pair type:** RSA
3. **Private key file format:** `.pem`
4. Click **Create key pair** — the `.pem` file downloads automatically to your machine

After downloading, set permissions in your terminal:
```bash
chmod 400 ~/Downloads/video-downloader-key.pem
```

---

### 4. Security Group

**Console path:** `EC2 → Network & Security → Security Groups → Create security group`

1. **Security group name:** `video-downloader-sg`
2. **Description:** `Video Downloader API`
3. **VPC:** leave as default VPC
4. Under **Inbound rules**, click **Add rule** twice:

| Type | Protocol | Port | Source |
|------|----------|------|--------|
| SSH | TCP | 22 | `0.0.0.0/0` |
| Custom TCP | TCP | 8000 | `0.0.0.0/0` |

5. Click **Create security group**

---

### 5. Launch EC2 Instance

**Console path:** `EC2 → Instances → Launch instances`

| Setting | Value |
|---------|-------|
| Name | `video-downloader` |
| AMI | Amazon Linux 2023 AMI (64-bit x86) |
| Instance type | `t3.micro` |
| Key pair | `video-downloader-key` |
| Security group | `video-downloader-sg` (select existing) |
| Storage | 8 GiB gp3 |

Click **Launch instance**.

**Wait ~2 minutes** for the instance state to show "Running", then copy the **Public IPv4 address** from the instance details page.

**Configure IMDS (required for Docker to access IAM credentials):**

1. Select your instance → **Actions → Instance settings → Modify instance metadata options**
2. Set **IMDSv2** to `Optional`
3. Set **Metadata response hop limit** to `2`
4. Click **Save**

---

## Application Deployment (Terminal Required)

> Replace `<PUBLIC_IP>` with your EC2 instance's Public IPv4 address and `<BUCKET_NAME>` with your S3 bucket name throughout this section.

### Install Docker & Dependencies

```bash
ssh -i ~/Downloads/video-downloader-key.pem ec2-user@<PUBLIC_IP> <<'ENDSSH'
sudo yum update -y && \
sudo yum install -y docker git && \
sudo systemctl enable --now docker && \
sudo usermod -aG docker ec2-user
ENDSSH
```

### Build & Run Container

```bash
ssh -i ~/Downloads/video-downloader-key.pem ec2-user@<PUBLIC_IP> "
git clone https://github.com/nyxsky404/Video-Downloader.git ~/video-downloader
cd ~/video-downloader
docker build -t video-downloader:latest .
docker run -d \
  --name video-downloader \
  --restart unless-stopped \
  --network host \
  -e USE_S3=true \
  -e S3_BUCKET_NAME=<BUCKET_NAME> \
  -e AWS_REGION=ap-south-1 \
  video-downloader:latest
"
```

### Verify Deployment

```bash
curl http://<PUBLIC_IP>:8000/health
# Expected: {"status":"healthy","cookies":{"status":"missing",...}}
```

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `USE_S3` | Yes | `true` | Enable S3 storage (set `false` for local) |
| `S3_BUCKET_NAME` | Yes | - | S3 bucket for video storage |
| `AWS_REGION` | Yes | `ap-south-1` | AWS region |
| `LOCAL_DOWNLOAD_DIR` | No | `/tmp/downloads` | Temp dir when using S3 |
| `API_HOST` | No | `0.0.0.0` | API bind address |
| `API_PORT` | No | `8000` | API port |
| `YT_DLP_COOKIES_FILE` | No | - | YouTube auth cookies path |
| `DOWNLOAD_TIMEOUT` | No | `300` | Download timeout (seconds) |
| `YT_DLP_MAX_RETRIES` | No | `3` | yt-dlp retry attempts |
| `YT_DLP_MAX_FILESIZE` | No | `500` | Max file size (MB) |

### YouTube Cookies

For YouTube downloads, configure cookies:

1. Export `cookies.txt` from your browser using the **"Get cookies.txt LOCALLY"** Chrome/Firefox extension
2. Upload the file and restart the container:

```bash
# Upload cookies to EC2
scp -i ~/Downloads/video-downloader-key.pem cookies.txt ec2-user@<PUBLIC_IP>:~/video-downloader/

# Restart container with cookies mounted
ssh -i ~/Downloads/video-downloader-key.pem ec2-user@<PUBLIC_IP> "
docker stop video-downloader && docker rm video-downloader
docker run -d \
  --name video-downloader \
  --restart unless-stopped \
  --network host \
  -v ~/video-downloader/cookies.txt:/app/cookies.txt \
  -e USE_S3=true \
  -e S3_BUCKET_NAME=<BUCKET_NAME> \
  -e AWS_REGION=ap-south-1 \
  -e YT_DLP_COOKIES_FILE=/app/cookies.txt \
  video-downloader:latest
"

# Verify
curl http://<PUBLIC_IP>:8000/cookies/status
```

---

## Operations

### Logging

```bash
# View live logs
ssh -i ~/Downloads/video-downloader-key.pem ec2-user@<PUBLIC_IP> "docker logs -f --tail 100 video-downloader"

# Export logs locally
ssh -i ~/Downloads/video-downloader-key.pem ec2-user@<PUBLIC_IP> "docker logs video-downloader" > app.log
```

### Container Management

```bash
# Restart container
ssh -i ~/Downloads/video-downloader-key.pem ec2-user@<PUBLIC_IP> "docker restart video-downloader"

# Update application
ssh -i ~/Downloads/video-downloader-key.pem ec2-user@<PUBLIC_IP> "
cd ~/video-downloader
git pull
docker build -t video-downloader:latest .
docker stop video-downloader
docker rm video-downloader
# Re-run the docker run command from the Application Deployment section
"

# Health check
curl http://<PUBLIC_IP>:8000/health
```

### Monitoring

**Key Metrics:**
- Container status: `docker ps`
- CPU/Memory: `docker stats video-downloader`
- S3 uploads: CloudWatch S3 metrics
- API response times: Application logs
- Disk usage (EC2): `df -h /tmp`

**Recommended Alerts:**
- Container stopped unexpectedly
- S3 upload failures > 5% 
- EC2 CPU > 80% sustained
- Disk usage > 90%

---

## API Reference

### Endpoints

**POST /download**
```bash
curl -X POST http://<PUBLIC_IP>:8000/download \
  -H "Content-Type: application/json" \
  -d '{"url":"https://youtube.com/watch?v=xxx"}'
```
Response: `{"status":"success","data":{"filename":"...","download_url":"https://...s3..."}}`

**GET /video/{filename}**
```bash
curl http://<PUBLIC_IP>:8000/video/video_xxx.mp4
```
Response (S3): `{"url":"https://bucket.s3.region.amazonaws.com/videos/video_xxx.mp4"}`

**GET /health**
```bash
curl http://<PUBLIC_IP>:8000/health
```

**GET /cookies/status**
```bash
curl http://<PUBLIC_IP>:8000/cookies/status
```

### Flow Diagram

```
Client → POST /download → EC2 (yt-dlp) → /tmp/downloads/video.mp4
                              ↓
                          Upload to S3 (retry 3x)
                              ↓
                          Delete local file
                              ↓
Client ← JSON response ← Return S3 URL
         ↓
Client → Download directly from S3 (not via EC2)
```

---

## Additional Resources

- **Dockerfile**: Multi-stage build with FFmpeg + Node.js + Python
- **storage.py**: Retry logic with exponential backoff (3 attempts: 1s, 2s, 4s)
- **config.py**: Environment-based configuration using pydantic-settings
- **Error handling**: S3Storage validates bucket access on init, catches NoCredentialsError

**Supported platforms**: YouTube, YouTube Shorts, Twitter/X, Facebook

**Dependencies**: yt-dlp, FastAPI, boto3, ffmpeg, nodejs
