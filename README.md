# AWS Uptime Monitor

A serverless uptime monitoring tool built on AWS. It checks one or more websites every 5 minutes, logs results to CloudWatch, and sends an email alert via SNS if any site is down or responding slowly.

---

## Architecture

```
EventBridge (every 5 min)
        |
        v
  AWS Lambda (Python)
   |           |
   v           v
CloudWatch   SNS Topic
  Logs &      |
  Metrics     v
           Email Alert
```

**Flow:**
- EventBridge triggers the Lambda function on a 5-minute schedule
- Lambda loops through all configured URLs and pings each one
- Results (status, response time, status code) are logged to CloudWatch Logs
- `SiteUp` (1/0) and `ResponseTimeMs` metrics are pushed to CloudWatch Metrics
- If any site is `down` or `slow`, a single summary alert is sent via SNS to your email

---

## Services Used

| Service | Purpose |
|---|---|
| **AWS Lambda** | Runs the Python checker function — no server needed |
| **Amazon EventBridge** | Triggers Lambda on a cron schedule (every 5 minutes) |
| **Amazon SNS** | Sends email notifications when a site is down or slow |
| **Amazon CloudWatch Logs** | Stores every check result for debugging and history |
| **Amazon CloudWatch Metrics** | Tracks uptime and response time trends over time |
| **AWS IAM** | Grants Lambda permission to write to CloudWatch and publish to SNS |

All services used are within the **AWS Free Tier**.

---

## How to Deploy

### Prerequisites
- AWS account (free tier)
- AWS CLI installed and configured (`aws configure`)

### Step 1 — Create an SNS Topic for email alerts
1. Go to **AWS Console > SNS > Topics > Create topic**
2. Type: Standard, Name: `uptime-alerts`
3. Create a **subscription**: Protocol = Email, enter your email
4. Confirm the subscription from your inbox
5. Copy the **Topic ARN** (you'll need it in Step 3)

### Step 2 — Create an IAM Role for Lambda
1. Go to **IAM > Roles > Create role**
2. Trusted entity: AWS service > Lambda
3. Attach these policies:
   - `AWSLambdaBasicExecutionRole` (CloudWatch Logs)
   - `CloudWatchFullAccess` (custom metrics)
   - `AmazonSNSFullAccess` (send alerts)
4. Name it: `uptime-monitor-role`

### Step 3 — Create the Lambda Function
1. Go to **Lambda > Create function**
2. Name: `uptime-monitor`, Runtime: Python 3.12
3. Permissions: use existing role > `uptime-monitor-role`
4. Paste the contents of `lambda_function.py` into the code editor
5. Go to **Configuration > Environment Variables** and add:

| Key | Value |
|---|---|
| `URLS` | `https://yoursite.com,https://google.com` |
| `SNS_TOPIC_ARN` | `arn:aws:sns:us-east-1:xxxx:uptime-alerts` |
| `TIMEOUT_SECONDS` | `10` |
| `SLOW_THRESHOLD_MS` | `3000` |

6. Set timeout to **30 seconds** (Configuration > General)

### Step 4 — Add EventBridge Trigger
1. In your Lambda function, click **Add trigger**
2. Select **EventBridge (CloudWatch Events)**
3. Create a new rule:
   - Rule type: Schedule expression
   - Expression: `rate(5 minutes)`
4. Enable the trigger

### Step 5 — Test It
1. Click **Test** in the Lambda console
2. Use an empty JSON payload `{}`
3. Check the **Logs** tab to see results
4. To test alerting: temporarily set a URL to `https://thissitedoesnotexist12345.com`

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `URLS` | `https://example.com` | Comma-separated list of URLs to monitor |
| `SNS_TOPIC_ARN` | *(empty)* | ARN of your SNS topic for alerts |
| `TIMEOUT_SECONDS` | `10` | How long to wait before marking a site as down |
| `SLOW_THRESHOLD_MS` | `3000` | Response time (ms) above which a site is flagged as slow |

---

## What I Learned

- **Serverless architecture** — how Lambda functions run on demand without managing servers. Thats something AWS takes care of
- **Event-driven design** — using EventBridge to trigger workloads on a schedule, similar to a cron job but i used a fixed rate
- **Observability fundamentals** — the difference between logs (what happened) and metrics (trends over time). I can see how looking at trends can show site reliability.
- **Alerting systems** — how SNS decouples alert generation from delivery, and why that matters at scale. It matters because you can add and remove recipients without redeploying code and it goes to everyone on the list topic.
- **IAM and least-privilege** — why every AWS resource needs explicit permissions and how roles work. AWS is API-driven, and every API call is authorized against IAM/security policies to determine whether it’s allowed. 


---

## Project Structure

```
aws-uptime-monitor/
├── lambda_function.py   # Core Lambda handler
└── README.md            # This file
```

---

## Future Improvements

- Add Terraform to provision all infrastructure as code
- Store URL list in AWS SSM Parameter Store for easier updates without redeploying
- Add multi-region checks to detect regional outages
- Build a CloudWatch Dashboard to visualize uptime history
- Add SSL certificate expiry checks