# AWS Deployment Guide: LoA App Insights Reporter

Deploy this automation as a scheduled ECS Fargate task triggered by EventBridge Scheduler. The container runs for ~30-60 seconds on weekday mornings, then shuts down. You only pay for the compute time used.

## Architecture

```
EventBridge Scheduler (cron: 8:30 AM EST, Mon-Fri)
        │
        ▼
ECS Fargate Task (runs container)
        │
        ├── Fetches from Azure App Insights API
        ├── Queries Redshift (warehouse)
        ├── Queries MySQL (cirk-prod)
        │
        ▼
Posts report to Slack → exits
```

**AWS Services Used:**
- **ECR** — Store the Docker image
- **ECS Fargate** — Run the container (no EC2 instances to manage)
- **EventBridge Scheduler** — Trigger the task on a cron schedule
- **Secrets Manager** — Store credentials securely
- **CloudWatch Logs** — Capture container output
- **IAM** — Roles for ECS task execution and EventBridge

---

## Prerequisites

- AWS CLI installed and configured (`aws configure`)
- Docker installed locally
- An AWS account with permissions to create ECR, ECS, EventBridge, Secrets Manager, and IAM resources

---

## Step 1: Store Secrets in AWS Secrets Manager

Store all sensitive env vars in Secrets Manager. Do this once.

```bash
aws secretsmanager create-secret \
  --name app-insights-reporter/prod \
  --secret-string '{
    "AZURE_APP_INSIGHTS_WORKSPACE_ID": "245ca4b3-2249-4a42-a983-8ec6904f2514",
    "AZURE_ACCESS_TOKEN": "placeholder-will-be-refreshed",
    "SLACK_BOT_TOKEN": "xoxb-your-token-here",
    "REDSHIFT_HOST": "redshift.circleklift.com",
    "REDSHIFT_PORT": "5439",
    "REDSHIFT_DATABASE": "warehouse",
    "REDSHIFT_USER": "liftreadyonly",
    "REDSHIFT_PASSWORD": "your-password",
    "MYSQL_HOST": "cirk-prod.cluster-ro-cwmhmb7mi9yp.us-east-1.rds.amazonaws.com",
    "MYSQL_PORT": "3306",
    "MYSQL_DATABASE": "lift",
    "MYSQL_USER": "lift-ro",
    "MYSQL_PASSWORD": "your-password"
  }'
```

Note the ARN returned — you'll need it in Step 4.

---

## Step 2: Create an ECR Repository and Push the Image

```bash
# Set variables
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=us-east-1
ECR_REPO=app-insights-reporter

# Create the repository
aws ecr create-repository --repository-name $ECR_REPO --region $AWS_REGION

# Authenticate Docker to ECR
aws ecr get-login-password --region $AWS_REGION \
  | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build and push (run from the bot directory)
cd bots/app-insights-reporter

docker build --platform linux/amd64 -t $ECR_REPO .

docker tag $ECR_REPO:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest

docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest
```

> **Apple Silicon note:** The `--platform linux/amd64` flag is required if you're building on an M-series Mac. Fargate runs on x86_64.

---

## Step 3: Create IAM Roles

### 3a. ECS Task Execution Role (pulls image, reads secrets, writes logs)

```bash
# Create the role
aws iam create-role \
  --role-name app-insights-reporter-execution-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ecs-tasks.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

# Attach the managed ECS execution policy
aws iam attach-role-policy \
  --role-name app-insights-reporter-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# Add Secrets Manager read access
aws iam put-role-policy \
  --role-name app-insights-reporter-execution-role \
  --policy-name SecretsAccess \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:app-insights-reporter/prod-*"
    }]
  }'
```

### 3b. ECS Task Role (what the running container can do)

Only needed if your container calls other AWS services. For now the bot only talks to Azure, Slack, Redshift, and MySQL — so an empty role is fine:

```bash
aws iam create-role \
  --role-name app-insights-reporter-task-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ecs-tasks.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'
```

### 3c. EventBridge Scheduler Role (runs ECS tasks)

```bash
aws iam create-role \
  --role-name app-insights-reporter-scheduler-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "scheduler.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

aws iam put-role-policy \
  --role-name app-insights-reporter-scheduler-role \
  --policy-name RunECSTask \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": ["ecs:RunTask"],
        "Resource": "arn:aws:ecs:us-east-1:YOUR_ACCOUNT_ID:task-definition/app-insights-reporter:*"
      },
      {
        "Effect": "Allow",
        "Action": ["iam:PassRole"],
        "Resource": [
          "arn:aws:iam::YOUR_ACCOUNT_ID:role/app-insights-reporter-execution-role",
          "arn:aws:iam::YOUR_ACCOUNT_ID:role/app-insights-reporter-task-role"
        ]
      }
    ]
  }'
```

> Replace `YOUR_ACCOUNT_ID` with your actual AWS account ID in all commands above.

---

## Step 4: Create ECS Cluster and Task Definition

### 4a. Create the cluster

```bash
aws ecs create-cluster --cluster-name automations
```

### 4b. Create a CloudWatch log group

```bash
aws logs create-log-group --log-group-name /ecs/app-insights-reporter
```

### 4c. Register the task definition

Create a file called `task-definition.json`:

```json
{
  "family": "app-insights-reporter",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::YOUR_ACCOUNT_ID:role/app-insights-reporter-execution-role",
  "taskRoleArn": "arn:aws:iam::YOUR_ACCOUNT_ID:role/app-insights-reporter-task-role",
  "containerDefinitions": [
    {
      "name": "app-insights-reporter",
      "image": "YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/app-insights-reporter:latest",
      "essential": true,
      "logConfiguration": {
        "logType": "awslogs",
        "options": {
          "awslogs-group": "/ecs/app-insights-reporter",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "secrets": [
        {"name": "AZURE_APP_INSIGHTS_WORKSPACE_ID", "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:app-insights-reporter/prod:AZURE_APP_INSIGHTS_WORKSPACE_ID::"},
        {"name": "AZURE_ACCESS_TOKEN",              "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:app-insights-reporter/prod:AZURE_ACCESS_TOKEN::"},
        {"name": "SLACK_BOT_TOKEN",                 "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:app-insights-reporter/prod:SLACK_BOT_TOKEN::"},
        {"name": "REDSHIFT_HOST",                   "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:app-insights-reporter/prod:REDSHIFT_HOST::"},
        {"name": "REDSHIFT_PORT",                   "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:app-insights-reporter/prod:REDSHIFT_PORT::"},
        {"name": "REDSHIFT_DATABASE",               "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:app-insights-reporter/prod:REDSHIFT_DATABASE::"},
        {"name": "REDSHIFT_USER",                   "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:app-insights-reporter/prod:REDSHIFT_USER::"},
        {"name": "REDSHIFT_PASSWORD",               "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:app-insights-reporter/prod:REDSHIFT_PASSWORD::"},
        {"name": "MYSQL_HOST",                      "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:app-insights-reporter/prod:MYSQL_HOST::"},
        {"name": "MYSQL_PORT",                      "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:app-insights-reporter/prod:MYSQL_PORT::"},
        {"name": "MYSQL_DATABASE",                  "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:app-insights-reporter/prod:MYSQL_DATABASE::"},
        {"name": "MYSQL_USER",                      "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:app-insights-reporter/prod:MYSQL_USER::"},
        {"name": "MYSQL_PASSWORD",                  "valueFrom": "arn:aws:secretsmanager:us-east-1:YOUR_ACCOUNT_ID:secret:app-insights-reporter/prod:MYSQL_PASSWORD::"}
      ],
      "environment": [
        {"name": "SLACK_CHANNEL", "value": "#int-lift-loa-app-insights"}
      ]
    }
  ]
}
```

Register it:

```bash
aws ecs register-task-definition --cli-input-json file://task-definition.json
```

---

## Step 5: Create the EventBridge Schedule

This is what makes it automatic — runs every weekday at 8:30 AM Eastern.

You'll need a subnet ID and security group ID from your VPC. The security group must allow outbound HTTPS (443) and outbound access to Redshift (5439) and MySQL (3306).

```bash
# Find your default VPC subnets
aws ec2 describe-subnets --filters "Name=default-for-az,Values=true" \
  --query "Subnets[].SubnetId" --output text

# Find or create a security group with the right outbound rules
aws ec2 describe-security-groups --filters "Name=group-name,Values=default" \
  --query "SecurityGroups[0].GroupId" --output text
```

Then create the schedule:

```bash
aws scheduler create-schedule \
  --name app-insights-reporter-daily \
  --schedule-expression "cron(30 13 ? * MON-FRI *)" \
  --schedule-expression-timezone "UTC" \
  --flexible-time-window '{"Mode": "OFF"}' \
  --target '{
    "Arn": "arn:aws:ecs:us-east-1:YOUR_ACCOUNT_ID:cluster/automations",
    "RoleArn": "arn:aws:iam::YOUR_ACCOUNT_ID:role/app-insights-reporter-scheduler-role",
    "EcsParameters": {
      "TaskDefinitionArn": "arn:aws:ecs:us-east-1:YOUR_ACCOUNT_ID:task-definition/app-insights-reporter",
      "TaskCount": 1,
      "LaunchType": "FARGATE",
      "NetworkConfiguration": {
        "AwsvpcConfiguration": {
          "Subnets": ["subnet-XXXXX"],
          "SecurityGroups": ["sg-XXXXX"],
          "AssignPublicIp": "ENABLED"
        }
      }
    },
    "RetryPolicy": {
      "MaximumRetryAttempts": 2,
      "MaximumEventAgeInSeconds": 300
    }
  }'
```

> `cron(30 13 ? * MON-FRI *)` = 8:30 AM EST (13:30 UTC). Adjust if you're in a different timezone or during daylight saving time. Alternatively, use `--schedule-expression-timezone "America/New_York"` with `cron(30 8 ? * MON-FRI *)`.

---

## Step 6: Test It

### Run the task manually

```bash
aws ecs run-task \
  --cluster automations \
  --task-definition app-insights-reporter \
  --launch-type FARGATE \
  --network-configuration '{
    "awsvpcConfiguration": {
      "subnets": ["subnet-XXXXX"],
      "securityGroups": ["sg-XXXXX"],
      "assignPublicIp": "ENABLED"
    }
  }'
```

### Check the logs

```bash
# List recent log streams
aws logs describe-log-streams \
  --log-group-name /ecs/app-insights-reporter \
  --order-by LastEventTime --descending --limit 1

# Tail the latest logs
aws logs get-log-events \
  --log-group-name /ecs/app-insights-reporter \
  --log-stream-name "ecs/app-insights-reporter/TASK_ID"
```

Or just check CloudWatch Logs in the AWS Console.

---

## Updating the Bot

When you make code changes:

```bash
cd bots/app-insights-reporter

# Rebuild and push
docker build --platform linux/amd64 -t app-insights-reporter .
docker tag app-insights-reporter:latest YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/app-insights-reporter:latest
docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/app-insights-reporter:latest

# Force ECS to pick up the new image on the next run
# (Fargate pulls :latest each time by default, so usually no action needed)
```

If you want to force a new task definition revision (e.g., after changing env vars):

```bash
aws ecs register-task-definition --cli-input-json file://task-definition.json
```

---

## Updating Secrets

```bash
aws secretsmanager update-secret \
  --secret-id app-insights-reporter/prod \
  --secret-string '{ ... updated JSON ... }'
```

The next task run will pick up the new values automatically.

---

## Cost Estimate

This job runs ~60 seconds per weekday = ~22 runs/month.

| Resource | Monthly Cost |
|----------|-------------|
| Fargate (0.5 vCPU, 1 GB, ~22 min/month) | ~$0.01 |
| ECR storage (~500 MB image) | ~$0.05 |
| Secrets Manager (1 secret) | ~$0.40 |
| CloudWatch Logs | ~$0.01 |
| EventBridge Scheduler | Free |
| **Total** | **~$0.50/month** |

---

## Azure Token Refresh Consideration

The current bot refreshes the Azure access token using `az CLI` or a service principal at the start of each run. For AWS deployment, you have two options:

1. **Azure Service Principal (recommended):** Store the service principal credentials (`AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`) in Secrets Manager and have the `run.sh` script use them to get a fresh token on each run. The Dockerfile already includes Azure CLI.

2. **Pre-generated long-lived token:** Not recommended — tokens expire frequently.

If you go with option 1, add these to your Secrets Manager secret and update `run.sh` to call:

```bash
az login --service-principal \
  -u "$AZURE_CLIENT_ID" \
  -p "$AZURE_CLIENT_SECRET" \
  --tenant "$AZURE_TENANT_ID"

export AZURE_ACCESS_TOKEN=$(az account get-access-token \
  --resource https://api.applicationinsights.io \
  --query accessToken -o tsv)
```

---

## Networking Checklist

- [ ] Security group allows **outbound** on port 443 (Azure API, Slack API, QuickChart.io)
- [ ] Security group allows **outbound** on port 5439 (Redshift)
- [ ] Security group allows **outbound** on port 3306 (MySQL)
- [ ] Redshift cluster's security group allows **inbound** from the Fargate task's security group or subnet
- [ ] MySQL/RDS cluster's security group allows **inbound** from the Fargate task's security group or subnet
- [ ] Subnet has internet access (public subnet with IGW, or private subnet with NAT gateway)
