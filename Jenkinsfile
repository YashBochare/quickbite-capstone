// QuickBite CI/CD: test -> build image -> push to ECR -> deploy via CloudFormation -> verify.
pipeline {
  agent any
  options { timestamps(); timeout(time: 30, unit: 'MINUTES'); disableConcurrentBuilds() }
  environment {
    AWS_REGION = 'ap-southeast-2'
    REPO       = "${env.ECR_REGISTRY}/quickbite"
    TAG        = "${env.BUILD_NUMBER}"
  }
  stages {
    stage('Checkout') {
      steps {
        checkout scm
        script { env.GIT_SHORT = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim() }
        echo "Commit ${env.GIT_SHORT}"
      }
    }
    stage('Unit Tests (in container)') {
      steps {
        sh 'docker build --target test -t quickbite-test:${TAG} .'
        sh 'docker create --name qb-results-${TAG} quickbite-test:${TAG} && docker cp qb-results-${TAG}:/srv/test-results.xml test-results.xml; docker rm qb-results-${TAG}'
      }
      post { always { junit 'test-results.xml' } }
    }
    stage('Validate IaC Template') {
      steps { sh 'aws cloudformation validate-template --template-body file://infra/quickbite.yaml --region $AWS_REGION > /dev/null && echo "template valid"' }
    }
    stage('Build Image') {
      steps { sh 'docker build --build-arg APP_VERSION=1.${TAG} -t ${REPO}:${TAG} .' }
    }
    stage('Push to Amazon ECR') {
      steps {
        sh '''
          aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY
          docker push ${REPO}:${TAG}
        '''
      }
    }
    stage('Deploy (CloudFormation)') {
      steps {
        sh '''
          aws cloudformation deploy --region $AWS_REGION --stack-name quickbite \
            --template-file infra/quickbite.yaml --capabilities CAPABILITY_IAM \
            --parameter-overrides ImageTag=${TAG} DesiredCount=2 --no-fail-on-empty-changeset
        '''
      }
    }
    stage('Verify') {
      steps {
        sh '''
          URL=$(aws cloudformation describe-stacks --region $AWS_REGION --stack-name quickbite \
                --query "Stacks[0].Outputs[?OutputKey=='AppURL'].OutputValue" --output text)
          for i in $(seq 1 30); do
            BODY=$(curl -fs $URL/health || true); echo "$BODY"
            echo "$BODY" | grep -q "\\"build\\":\\"${TAG}\\"" && { echo "Live: build ${TAG} at $URL"; exit 0; }
            sleep 5
          done
          exit 1
        '''
      }
    }
  }
  post {
    always { sh 'docker image rm ${REPO}:${TAG} quickbite-test:${TAG} >/dev/null 2>&1 || true' }
    failure { echo 'Deployment failed; CloudFormation/ECS circuit breaker keeps the previous version running.' }
  }
}
