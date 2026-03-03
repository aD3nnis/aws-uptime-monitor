#This file defines an AWS Lambda function that regularly checks one or more websites and sends alerts if they are down or responding slowly.
import urllib.request
import urllib.error
import os
import json
import boto3 # Used to interact with AWS services.
import time
from datetime import datetime

# AWS clients
sns_client = boto3.client('sns') # Used to send messages (alerts) via Amazon SNS. (simple notification service)
cloudwatch = boto3.client('cloudwatch') # Used to publish metrics to Amazon CloudWatch.

# These variables are set in Lambda > Configuration > Environment Variables
URLS            = os.environ.get('URLS', 'https://example.com').split(',')
SNS_TOPIC_ARN   = os.environ.get('SNS_TOPIC_ARN', '')
TIMEOUT_SECONDS = int(os.environ.get('TIMEOUT_SECONDS', '10'))
SLOW_THRESHOLD  = int(os.environ.get('SLOW_THRESHOLD_MS', '3000'))


# Check a single URL
def check_url(url):
    url = url.strip()
    result = {
        'url': url,
        'timestamp': datetime.utcnow().isoformat(),
        'status': 'unknown',
        'status_code': None,
        'response_time_ms': None,
        'error': None,
    }
    start = time.time()
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'UptimeMonitor/1.0'})
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            elapsed = int((time.time() - start) * 1000)
            result['status_code']      = resp.status
            result['response_time_ms'] = elapsed
            result['status'] = 'slow' if elapsed > SLOW_THRESHOLD else 'up'

    except urllib.error.HTTPError as e:
        result.update(status='down', status_code=e.code,
                      response_time_ms=int((time.time()-start)*1000),
                      error=f'HTTP {e.code} {e.reason}')
    except urllib.error.URLError as e:
        result.update(status='down', error=f'URLError: {e.reason}')
    except Exception as e:
        result.update(status='down', error=str(e))

    return result


# Send email alert via SNS
def send_alert(results):
    if not SNS_TOPIC_ARN:
        print("SNS_TOPIC_ARN not set -- skipping alert")
        return

    issues = [r for r in results if r['status'] in ('down', 'slow')]
    if not issues:
        return

    lines = [f"Uptime Alert: {len(issues)} site(s) need attention\n"]
    for r in issues:
        tag = 'DOWN' if r['status'] == 'down' else 'SLOW'
        lines.append(f"{tag}: {r['url']}")
        if r['status_code']:      lines.append(f"  Status code   : {r['status_code']}")
        if r['response_time_ms']: lines.append(f"  Response time : {r['response_time_ms']} ms")
        if r['error']:            lines.append(f"  Error         : {r['error']}")
        lines.append(f"  Checked at    : {r['timestamp']} UTC\n")

    sns_client.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=f"Uptime Alert: {len(issues)} issue(s) detected",
        Message='\n'.join(lines),
    )
    print(f"Alert sent for {len(issues)} issue(s)")


# Push metrics to CloudWatch
def publish_metrics(r):
    label = r['url'].replace('https://', '').replace('http://', '').rstrip('/')
    metrics = [{
        'MetricName': 'SiteUp',
        'Dimensions': [{'Name': 'URL', 'Value': label}],
        'Value': 1 if r['status'] == 'up' else 0,
        'Unit': 'Count',
    }]
    if r['response_time_ms'] is not None:
        metrics.append({
            'MetricName': 'ResponseTimeMs',
            'Dimensions': [{'Name': 'URL', 'Value': label}],
            'Value': r['response_time_ms'],
            'Unit': 'Milliseconds',
        })
    cloudwatch.put_metric_data(Namespace='UptimeMonitor', MetricData=metrics)


# Lambda entry point (triggered every 5 min by EventBridge)
def lambda_handler(event, context):
    print(f"Checking {len(URLS)} URL(s): {URLS}")
    results = []

    for url in URLS:
        r = check_url(url)
        results.append(r)
        print(json.dumps(r))
        try:
            publish_metrics(r)
        except Exception as e:
            print(f"Metric publish failed for {url}: {e}")

    try:
        send_alert(results)
    except Exception as e:
        print(f"Alert failed: {e}")

    summary = {
        'total': len(results),
        'up':   sum(1 for r in results if r['status'] == 'up'),
        'slow': sum(1 for r in results if r['status'] == 'slow'),
        'down': sum(1 for r in results if r['status'] == 'down'),
    }
    print("Summary:", json.dumps(summary))
    return {**summary, 'results': results}