pipeline {
  agent any

  environment {
    KUBECONFIG = credentials('kubeconfig-selenium') // Jenkins credential containing your kubeconfig
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Helm Deploy') {
      steps {
        sh '''
          helm version
          kubectl config get-contexts
          helm upgrade --install selenium-grid ./selenium-grid \
            --namespace selenium \
            --create-namespace \
            -f values.yaml
        '''
      }
    }

    stage('Verify Deployment') {
      steps {
        sh 'kubectl get pods -n selenium'
        sh 'kubectl get svc -n selenium'
      }
    }
  }
}
