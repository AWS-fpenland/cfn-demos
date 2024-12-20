### Domain Join Automation Execution CLI

```
aws ssm start-automation-execution --document-name "DomainJoinAutomation" --document-version "\$DEFAULT" --parameters '{"AutomationAssumeRole":["arn:aws:iam::056689112963:role/AWS-SystemsManager-AutomationExecutionRole"],"InstanceId":["i-0d8dabf6099739369"],"DomainJoinActivity":["Join"]}' --region us-east-1
```