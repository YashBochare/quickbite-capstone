#!/bin/bash
# One-time bootstrap: CloudFormation deployment role, Jenkins permissions, initial stack (0 tasks).
set -euo pipefail
export AWS_REGION=ap-southeast-2 AWS_PAGER=""
ACCT=$(aws sts get-caller-identity --query Account --output text)
HERE=$(cd "$(dirname "$0")" && pwd)

# CloudFormation service role: CloudFormation (not Jenkins) holds the rights to change infrastructure.
aws iam get-role --role-name quickbite-cfn-deploy-role >/dev/null 2>&1 || {
  aws iam create-role --role-name quickbite-cfn-deploy-role --assume-role-policy-document \
    '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"cloudformation.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
  aws iam attach-role-policy --role-name quickbite-cfn-deploy-role --policy-arn arn:aws:iam::aws:policy/PowerUserAccess
  aws iam put-role-policy --role-name quickbite-cfn-deploy-role --policy-name quickbite-iam --policy-document "{
    \"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":\"iam:*\",\"Resource\":\"arn:aws:iam::$ACCT:role/quickbite-*\"}]}"
  sleep 10
}
CFN_ROLE=arn:aws:iam::$ACCT:role/quickbite-cfn-deploy-role

# Jenkins (from Experiment 4) may only update this stack, through the CloudFormation role.
aws iam put-role-policy --role-name taskboard-jenkins-role --policy-name quickbite-deploy --policy-document "{
  \"Version\":\"2012-10-17\",\"Statement\":[
   {\"Effect\":\"Allow\",\"Action\":[\"cloudformation:CreateChangeSet\",\"cloudformation:ExecuteChangeSet\",\"cloudformation:DescribeChangeSet\",
     \"cloudformation:DescribeStacks\",\"cloudformation:DescribeStackEvents\",\"cloudformation:GetTemplateSummary\",\"cloudformation:UpdateStack\"],
     \"Resource\":\"arn:aws:cloudformation:$AWS_REGION:$ACCT:stack/quickbite/*\"},
   {\"Effect\":\"Allow\",\"Action\":\"cloudformation:ValidateTemplate\",\"Resource\":\"*\"},
   {\"Effect\":\"Allow\",\"Action\":\"iam:PassRole\",\"Resource\":\"$CFN_ROLE\"}]}"

aws cloudformation deploy --stack-name quickbite --template-file "$HERE/quickbite.yaml" --role-arn "$CFN_ROLE" \
  --capabilities CAPABILITY_IAM --parameter-overrides ImageTag=bootstrap DesiredCount=0 --tags Project=quickbite
aws cloudformation describe-stacks --stack-name quickbite --query 'Stacks[0].Outputs' --output table
