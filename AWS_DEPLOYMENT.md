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

- AWS CLI configured with appropriate credentials
- Git repository URL
- YouTube cookies for authentication (see Cookie Configuration section)

---

## Deployment Script

### Environment Variables

```bash
export AWS_REGION="ap-south-1"
export PROJECT_NAME="video-downloader"
export S3_BUCKET="video-downloader-$(date +%s)"
export KEY_NAME="video-downloader-key"
export GITHUB_REPO="https://github.com/nyxsky404/Video-Downloader.git"  # Update this
```

---

## Infrastructure Provisioning

### 1. IAM Resources

**EC2 Instance Role:**
```bash
# Trust policy
cat > /tmp/trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "ec2.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

# Create role
aws iam create-role \
  --role-name video-downloader-ec2-role \
  --assume-role-policy-document file:///tmp/trust-policy.json

# S3 access policy
cat > /tmp/s3-access-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:ListBucket"],
    "Resource": ["arn:aws:s3:::${S3_BUCKET}","arn:aws:s3:::${S3_BUCKET}/*"]
  }]
}
EOF

aws iam put-role-policy \
  --role-name video-downloader-ec2-role \
  --policy-name S3AccessPolicy \
  --policy-document file:///tmp/s3-access-policy.json

# Instance profile
aws iam create-instance-profile --instance-profile-name video-downloader-ec2-profile
aws iam add-role-to-instance-profile \
  --instance-profile-name video-downloader-ec2-profile \
  --role-name video-downloader-ec2-role

sleep 10  # IAM propagation
```

### 2. S3 Bucket

```bash
# Create bucket
aws s3api create-bucket \
  --bucket $S3_BUCKET \
  --region $AWS_REGION \
  --create-bucket-configuration LocationConstraint=$AWS_REGION

# Public access configuration
aws s3api put-public-access-block \
  --bucket $S3_BUCKET \
  --public-access-block-configuration \
    BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false

# Bucket policy (public read)
cat > /tmp/bucket-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "PublicReadGetObject",
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::${S3_BUCKET}/*"
  }]
}
EOF

aws s3api put-bucket-policy --bucket $S3_BUCKET --policy file:///tmp/bucket-policy.json
```

### 3. EC2 Infrastructure

```bash
# SSH keypair
aws ec2 create-key-pair \
  --key-name $KEY_NAME \
  --query 'KeyMaterial' \
  --output text \
  --region $AWS_REGION > ${KEY_NAME}.pem
chmod 400 ${KEY_NAME}.pem

# Security Group
SG_ID=$(aws ec2 create-security-group \
  --group-name video-downloader-sg \
  --description "Video Downloader API" \
  --region $AWS_REGION \
  --query 'GroupId' \
  --output text)

aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --ip-permissions \
    IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges='[{CidrIp=0.0.0.0/0}]' \
    IpProtocol=tcp,FromPort=8000,ToPort=8000,IpRanges='[{CidrIp=0.0.0.0/0}]' \
  --region $AWS_REGION

# Get latest Amazon Linux 2023 AMI
AMI_ID=$(aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023.*-x86_64" "Name=state,Values=available" \
  --query "sort_by(Images, &CreationDate)[-1].ImageId" \
  --output text \
  --region $AWS_REGION)

# Launch instance
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id $AMI_ID \
  --instance-type t3.micro \
  --key-name $KEY_NAME \
  --security-group-ids $SG_ID \
  --iam-instance-profile Name=video-downloader-ec2-profile \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=video-downloader}]' \
  --region $AWS_REGION \
  --query 'Instances[0].InstanceId' \
  --output text)

# Wait for instance ready
aws ec2 wait instance-running --instance-ids $INSTANCE_ID --region $AWS_REGION
PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids $INSTANCE_ID \
  --region $AWS_REGION \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)

# Configure metadata service for Docker IAM access
sleep 120  # Boot time
aws ec2 modify-instance-metadata-options \
  --instance-id $INSTANCE_ID \
  --http-tokens optional \
  --http-put-response-hop-limit 2 \
  --region $AWS_REGION

echo "Instance ID: $INSTANCE_ID"
echo "Public IP: $PUBLIC_IP"
```

---

## Application Deployment

### Install Docker & Dependencies

```bash
ssh -i ${KEY_NAME}.pem ec2-user@$PUBLIC_IP <<'ENDSSH'
sudo yum update -y && \
sudo yum install -y docker git && \
sudo systemctl enable --now docker && \
sudo usermod -aG docker ec2-user
ENDSSH
```

### Build & Run Container

```bash
ssh -i ${KEY_NAME}.pem ec2-user@$PUBLIC_IP "
git clone $GITHUB_REPO ~/video-downloader
cd ~/video-downloader
docker build -t video-downloader:latest .
docker run -d \
  --name video-downloader \
  --restart unless-stopped \
  --network host \
  -e USE_S3=true \
  -e S3_BUCKET_NAME=$S3_BUCKET \
  -e AWS_REGION=$AWS_REGION \
  video-downloader:latest
"
```

### Verify Deployment

```bash
curl http://$PUBLIC_IP:8000/health
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

### YouTube Cookies (Optional)

For YouTube downloads, configure cookies:

```bash
# Export cookies.txt from browser (use "Get cookies.txt LOCALLY" extension)
scp -i ${KEY_NAME}.pem cookies.txt ec2-user@$PUBLIC_IP:~/video-downloader/

# Restart with cookies mounted
ssh -i ${KEY_NAME}.pem ec2-user@$PUBLIC_IP "
docker stop video-downloader && docker rm video-downloader
docker run -d \
  --name video-downloader \
  --restart unless-stopped \
  --network host \
  -v ~/video-downloader/cookies.txt:/app/cookies.txt \
  -e USE_S3=true \
  -e S3_BUCKET_NAME=$S3_BUCKET \
  -e AWS_REGION=$AWS_REGION \
  -e YT_DLP_COOKIES_FILE=/app/cookies.txt \
  video-downloader:latest
"

# Verify
curl http://$PUBLIC_IP:8000/cookies/status
```

---

## Operations

### Logging

```bash
# View logs
ssh -i ${KEY_NAME}.pem ec2-user@$PUBLIC_IP "docker logs -f --tail 100 video-downloader"

# Export logs
ssh -i ${KEY_NAME}.pem ec2-user@$PUBLIC_IP "docker logs video-downloader" > app.log
```

### Container Management

```bash
# Restart
ssh -i ${KEY_NAME}.pem ec2-user@$PUBLIC_IP "docker restart video-downloader"

# Update application
ssh -i ${KEY_NAME}.pem ec2-user@$PUBLIC_IP "
cd ~/video-downloader
git pull
docker build -t video-downloader:latest .
docker stop video-downloader
docker rm video-downloader
# Re-run docker run command with same parameters
"

# Health check
curl http://$PUBLIC_IP:8000/health
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
curl -X POST http://$PUBLIC_IP:8000/download \
  -H "Content-Type: application/json" \
  -d '{"url":"https://youtube.com/watch?v=xxx"}'
```
Response: `{"status":"success","data":{"filename":"...","download_url":"https://...s3..."}}`

**GET /video/{filename}**
```bash
curl http://$PUBLIC_IP:8000/video/video_xxx.mp4
```
Response (S3): `{"url":"https://bucket.s3.region.amazonaws.com/videos/video_xxx.mp4"}`

**GET /health**
```bash
curl http://$PUBLIC_IP:8000/health
```

**GET /cookies/status**
```bash
curl http://$PUBLIC_IP:8000/cookies/status
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
