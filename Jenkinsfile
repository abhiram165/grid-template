pipeline {
   agent {
    docker {
      image 'alpine/helm:3.14.3' // You can change to another version if needed
      args '-v /var/run/docker.sock:/var/run/docker.sock' // Optional, useful if you're using DinD
    }
  }

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
  post {
    always {
      echo "Cleaning up Helm release..."
      sh '''
        helm uninstall selenium-grid --namespace selenium || true
        kubectl delete namespace selenium --ignore-not-found
      '''
    }
  }
}
