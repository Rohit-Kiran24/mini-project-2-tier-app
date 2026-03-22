@Library("Shared") _
pipeline{

    agent { label "dev" }

    environment {
        IMAGE_NAME = "two-tier-flask-app"
        DOCKER_USER = "rohitkiran24"
    }

    stages{
        stage("Code Clone"){
            steps{
               script{
                   clone("https://github.com/Rohit-Kiran24/mini-project-2-tier-app.git", "dev")
               }
            }
        }

        stage("Trivy File System Scan"){
            steps{
                script{
                    trivy_fs()
                }
            }
        }

        stage("Build"){
            steps{
                sh "docker build -t ${IMAGE_NAME}:${GIT_COMMIT} -t ${IMAGE_NAME}:latest ."
            }
        }

        stage("Test"){
            steps{
                sh "pip install -r requirements.txt"
                sh "pytest tests/ -v"
            }
        }

        stage("Trivy Image Scan"){
            steps{
                sh "trivy image ${IMAGE_NAME}:${GIT_COMMIT} --severity HIGH,CRITICAL"
            }
        }

        stage("Push to Docker Hub"){
            steps{
                script{
                    docker_push("dockerHubCreds", "${IMAGE_NAME}:${GIT_COMMIT}")
                    docker_push("dockerHubCreds", "${IMAGE_NAME}:latest")
                }
            }
        }

        stage("Deploy"){
            steps{
                sh "docker compose up -d --build flask-app"
            }
        }
    }

    post{
        success{
            script{
                emailext from: 'mentor@trainwithshubham.com',
                to: 'mentor@trainwithshubham.com',
                body: "Build success for Mini Project 2-Tier App — commit: ${GIT_COMMIT}",
                subject: 'Build success for Mini Project 2-Tier App'
            }
        }
        failure{
            script{
                emailext from: 'mentor@trainwithshubham.com',
                to: 'mentor@trainwithshubham.com',
                body: "Build failed for Mini Project 2-Tier App — commit: ${GIT_COMMIT}",
                subject: 'Build failed for Mini Project 2-Tier App'
            }
        }
    }
}