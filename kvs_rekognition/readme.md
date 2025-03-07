# Deploying the Nested CloudFormation Stack Solution

This guide walks you through deploying our modular Rekognition Real-time Object Detection solution using nested CloudFormation stacks.

## Prerequisites

1. AWS CLI installed and configured with appropriate permissions
2. An S3 bucket to store the CloudFormation templates
3. A text editor to save the template files

## Step 1: Save Template Files

Save each stack template to its own file with the following names:
- `main-stack.yaml` - Main/parent stack
- `video-processing.yaml` - Video processing stack
- `backend.yaml` - Backend infrastructure stack
- `websocket.yaml` - WebSocket API stack
- `frontend.yaml` - Frontend hosting stack
- `integration.yaml` - Integration stack

## Step 2: Create an S3 Bucket for Templates (if needed)

If you don't already have an S3 bucket for CloudFormation templates:

```bash
aws s3 mb s3://my-cloudformation-templates --region us-east-1
```

Replace `my-cloudformation-templates` with your preferred bucket name.

## Step 3: Upload Nested Stack Templates

Upload all the nested stack templates to your S3 bucket:

```bash
aws s3 cp video-processing.yaml s3://my-cloudformation-templates/nested-stacks/
aws s3 cp backend.yaml s3://my-cloudformation-templates/nested-stacks/
aws s3 cp websocket.yaml s3://my-cloudformation-templates/nested-stacks/
aws s3 cp frontend.yaml s3://my-cloudformation-templates/nested-stacks/
aws s3 cp integration.yaml s3://my-cloudformation-templates/nested-stacks/
```

## Step 4: Deploy the Main Stack

Deploy the main stack which will orchestrate all the nested stacks:

```bash
aws cloudformation create-stack \
  --stack-name rekognition-demo \
  --template-body file://main-stack.yaml \
  --parameters \
    ParameterKey=S3BucketForTemplates,ParameterValue=fp-cfn-demos \
    ParameterKey=S3KeyPrefix,ParameterValue=kvs_rekognition/ \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

## Step 5: Monitor Deployment Progress

Check the status of the stack creation:

```bash
aws cloudformation describe-stacks \
  --stack-name rekognition-demo \
  --query "Stacks[0].StackStatus" \
  --region us-east-1
```

You can also monitor the stack creation process in the AWS Management Console under CloudFormation.

## Step 6: Get Stack Outputs

Once the stack is in `CREATE_COMPLETE` status, get the output values:

```bash
aws cloudformation describe-stacks \
  --stack-name rekognition-demo \
  --query "Stacks[0].Outputs" \
  --output table \
  --region us-east-1
```

This will display key information including:
- `VideoStreamName` - The name of your Kinesis Video Stream
- `WebSocketApiEndpoint` - The WebSocket API endpoint
- `CloudFrontURL` - The URL for your frontend application

## Step 7: Generate HLS Streaming URL

Generate an HLS URL for video playback (valid for 12 hours):

```bash
aws kinesisvideo get-hls-streaming-session-url \
  --stream-name rekognition-demo-video-stream \
  --playback-mode LIVE \
  --expires 43200 \
  --query 'HLSStreamingSessionURL' \
  --output text \
  --region us-east-1
```

## Step 8: Set Up OBS Studio

1. Install OBS Studio if not already installed
2. Install the AWS Kinesis Video Streams plugin for OBS
3. Configure your AWS credentials in OBS
4. Configure your video sources in OBS
5. Stream to your Kinesis Video Stream using the plugin:
   - Stream name: `rekognition-demo-video-stream`
   - Region: Your AWS region (e.g., `us-east-1`)

## Step 9: Access the Web Application

1. Open the CloudFront URL in your browser (from the stack outputs)
2. The WebSocket URL should be pre-filled 
3. Enter the HLS Streaming URL you generated in Step 7
4. Click "Start" to begin viewing the stream with object detection

## Troubleshooting

### WebSocket Connection Issues
If you're having issues with WebSocket connections:
```bash
# Check the API Gateway logs
aws logs describe-log-groups \
  --log-group-name-prefix "/aws/apigateway/rekognition-demo" \
  --region us-east-1
```

### Rekognition Stream Processor Issues
Verify that the stream processor is running:
```bash
aws rekognition describe-stream-processor \
  --name rekognition-demo-processor \
  --region us-east-1
```

### OBS Streaming Issues
Check the KVS stream status:
```bash
aws kinesisvideo describe-stream \
  --stream-name rekognition-demo-video-stream \
  --region us-east-1
```

## Updating the Stack

If you need to make changes to any of the templates:

1. Upload the updated template files to S3
2. Update the stack:
```bash
aws cloudformation update-stack \
  --stack-name rekognition-demo \
  --template-body file://main-stack.yaml \
  --parameters \
    ParameterKey=S3BucketForTemplates,ParameterValue=my-cloudformation-templates \
    ParameterKey=S3KeyPrefix,ParameterValue=nested-stacks/ \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

## Cleanup

To remove all resources created by this stack:

```bash
aws cloudformation delete-stack \
  --stack-name rekognition-demo \
  --region us-east-1
```

This will delete all nested stacks and their resources automatically.